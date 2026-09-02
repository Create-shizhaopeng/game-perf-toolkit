"""Perfetto 抓取模块 — 服务层

纯同步逻辑，MUST NOT 包含 PyQt6 代码。
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from pathlib import Path

from toolkit.core.adb_manager import AdbCmdResult, AdbManager
from toolkit.core.app_paths import get_exe_dir, get_output_dir, get_user_data_dir, is_frozen

from .config_manager import load_config, save_config
from .pending_export_store import PENDING_EXPORT_FILENAME, PendingExportItem, PendingExportStore
from .models import (
    CaptureConfig,
    CaptureMode,
    CaptureSession,
    CaptureState,
    DeviceConnectionState,
    DeviceInfo,
    PerfettoCapabilities,
    RunningTrace,
    TraceItem,
    TraceKind,
)
from .strings_service import *
from .utils import (
    build_export_session_dirname,
    build_trace_filename,
    choose_non_conflicting_path,
    ensure_dir,
    ensure_fault_prefix,
    ensure_unique_dir,
    is_device_unavailable,
)

logger = logging.getLogger(__name__)

ProgressCallback = type(None) | type(lambda: None)


def _pbtxt_value(v: object) -> str:
    """将 Python 值格式化为 Perfetto pbtxt 字面量。"""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int | float):
        return str(v)
    if isinstance(v, str):
        return f'"{v}"'
    return str(v)


class PerfettoCaptureService:
    """Perfetto 抓取核心业务逻辑。"""

    def __init__(self, adb: AdbManager, data_dir: Path | None = None) -> None:
        self._adb = adb
        self._data_dir = data_dir or get_user_data_dir()
        self._cfg: CaptureConfig | None = None
        self._session: CaptureSession | None = None
        self._pending_store: PendingExportStore | None = None

    @property
    def pending_store(self) -> PendingExportStore:
        """待导出清单（位于 trace 输出目录下，延迟初始化）。"""
        if self._pending_store is None:
            self._pending_store = PendingExportStore(
                self.output_dir / PENDING_EXPORT_FILENAME
            )
            self._pending_store.load()
        return self._pending_store

    def get_service_info(self) -> dict:
        return {"name": "perfetto_capture", "display_name": SERVICE_DISPLAY_NAME, "version": "1.0.0"}

    @property
    def config(self) -> CaptureConfig:
        if self._cfg is None:
            self._cfg = load_config()
        return self._cfg

    @config.setter
    def config(self, cfg: CaptureConfig) -> None:
        self._cfg = cfg

    @property
    def session(self) -> CaptureSession | None:
        return self._session

    @property
    def output_dir(self) -> Path:
        # dev 模式或显式传入 data_dir 时基于 data_dir（保持可测试性）；
        # frozen 模式走 output 层（Documents，可配置）。
        if is_frozen():
            return get_output_dir("trace")
        return self._data_dir / self.config.output_dir / "trace"

    def reload_config(self, config_path: Path | None = None) -> CaptureConfig:
        self._cfg = load_config(config_path)
        return self._cfg

    def save_current_config(self) -> Path:
        return save_config(self.config)

    # ── Buffer 自动计算 ─────────────────────────────────────────
    # 校准目标：7 atrace / 15s / sf=1.2 → ~120 MB

    LIGHT_RATE_KB_PER_SEC = 6800
    HEAVY_PER_CAT_RATE_KB = 600
    LIGHT_CAT_THRESHOLD = 7
    MIN_BUFFER_KB = 91136       # 89 MB floor
    MAX_BUFFER_KB = 512000      # 500 MB ceiling

    def calculate_buffer_size(
        self,
        duration_sec: int | None = None,
        category_count: int | None = None,
        safety_factor: float | None = None,
        ftrace_count: int | None = None,
    ) -> int:
        """根据抓取时长、atrace category 和 ftrace event 数量自动计算 buffer（KB）。

        实测校准（游戏场景）:
        - 90 MB / 10s ≈ 9200 KB/s（7 categories 默认配置）
        - >7 tags: 每增加一个 tag 额外 +2600 KB/s（从 19-cat 实测数据等比缩放）
        """
        cfg = self.config
        dur = duration_sec if duration_sec is not None else cfg.duration_sec
        n_cats = category_count if category_count is not None else len(cfg.atrace_categories)
        n_ftrace = ftrace_count if ftrace_count is not None else len(cfg.advanced.ftrace_events)
        sf = safety_factor if safety_factor is not None else cfg.buffer_safety_factor

        total_tags = n_cats + n_ftrace
        if total_tags <= self.LIGHT_CAT_THRESHOLD:
            estimated_rate = self.LIGHT_RATE_KB_PER_SEC
        else:
            heavy_count = total_tags - self.LIGHT_CAT_THRESHOLD
            estimated_rate = self.LIGHT_RATE_KB_PER_SEC + heavy_count * self.HEAVY_PER_CAT_RATE_KB

        raw = int(estimated_rate * dur * sf)
        return max(self.MIN_BUFFER_KB, min(self.MAX_BUFFER_KB, raw))

    def get_effective_buffer_size(self) -> int:
        """获取当前生效的 buffer 大小：手动覆盖 → 固定值，否则自动计算。"""
        cfg = self.config
        if cfg.buffer_manual_override and cfg.buffer_size_kb is not None:
            return cfg.buffer_size_kb
        return self.calculate_buffer_size()

    # ── pbtxt 配置生成 ──────────────────────────────────────────

    def build_pbtxt_config(self, cfg: CaptureConfig | None = None) -> str:
        """生成 Perfetto TraceConfig (pbtxt) 文本。

        使用双缓冲区策略：
        - buffer 0: 主 ftrace 数据（RING_BUFFER，用户指定大小）
        - buffer 1: 进程名/包名等元数据（RING_BUFFER，固定 4MB，
          独立于主缓冲区以防被高频 ftrace 事件覆盖）

        builtin_data_sources 确保 clock snapshot 正确写入，
        解决 Perfetto UI 中各 slice 时间戳显示异常的问题。
        """
        cfg = cfg or self.config

        if cfg.target.mode == "packages":
            atrace_apps = cfg.target.packages
        else:
            atrace_apps = cfg.atrace_apps_global

        def q(s: str) -> str:
            return f'"{s.replace(chr(92), chr(92)*2).replace(chr(34), chr(92)+chr(34))}"'

        lines: list[str] = []

        effective_buffer = self.get_effective_buffer_size()
        lines.append("buffers {")
        lines.append(f"  size_kb: {effective_buffer}")
        lines.append("  fill_policy: RING_BUFFER")
        lines.append("}")

        lines.append("buffers {")
        lines.append(f"  size_kb: {cfg.metadata_buffer_size_kb}")
        lines.append("  fill_policy: RING_BUFFER")
        lines.append("}")

        lines.append(f"flush_period_ms: {cfg.flush_period_ms}")

        lines.append("incremental_state_config {")
        lines.append(f"  clear_period_ms: {cfg.clear_period_ms}")
        lines.append("}")

        lines.append("builtin_data_sources {")
        lines.append("  primary_trace_clock: BUILTIN_CLOCK_BOOTTIME")
        lines.append("}")

        lines.append("data_sources {")
        lines.append("  config {")
        lines.append('    name: "linux.ftrace"')
        lines.append("    target_buffer: 0")
        lines.append("    ftrace_config {")
        for cat in cfg.atrace_categories:
            lines.append(f"      atrace_categories: {q(cat)}")
        for app in atrace_apps:
            lines.append(f"      atrace_apps: {q(app)}")
        for evt in cfg.advanced.ftrace_events:
            lines.append(f"      ftrace_events: {q(evt)}")
        lines.append("      compact_sched {")
        lines.append(f"        enabled: {_pbtxt_value(cfg.compact_sched_enabled)}")
        lines.append("      }")
        lines.append("    }")
        lines.append("  }")
        lines.append("}")

        lines.append("data_sources {")
        lines.append("  config {")
        lines.append('    name: "linux.process_stats"')
        lines.append("    target_buffer: 1")
        lines.append("    process_stats_config {")
        lines.append(f"      scan_all_processes_on_start: {_pbtxt_value(cfg.scan_all_processes_on_start)}")
        lines.append(f"      record_thread_names: {_pbtxt_value(cfg.record_thread_names)}")
        lines.append(f"      proc_stats_poll_ms: {cfg.proc_stats_poll_ms}")
        lines.append("    }")
        lines.append("  }")
        lines.append("}")

        lines.append("data_sources {")
        lines.append("  config {")
        lines.append('    name: "android.packages_list"')
        lines.append("    target_buffer: 1")
        lines.append("    packages_list_config {")
        lines.append("    }")
        lines.append("  }")
        lines.append("}")

        # 额外 data sources（纯配置驱动，加新数据源只需改 JSON）
        for ds in cfg.data_sources:
            lines.append("data_sources {")
            lines.append("  config {")
            lines.append(f'    name: "{ds.name}"')
            if ds.target_buffer is not None:
                lines.append(f"    target_buffer: {ds.target_buffer}")
            if ds.config_block:
                lines.append(f"    {ds.config_block} {{")
                for k, v in ds.config_fields.items():
                    lines.append(f"      {k}: {_pbtxt_value(v)}")
                lines.append("    }")
            lines.append("  }")
            lines.append("}")

        return "\n".join(lines) + "\n"

    def build_pbtxt_config_detach(
        self, session_name: str, cfg: CaptureConfig | None = None,
    ) -> str:
        """生成支持 detach 模式的 pbtxt 配置。

        write_into_file 是 --detach 模式的强制要求，确保数据持续写入输出文件。
        """
        base = self.build_pbtxt_config(cfg)
        header = (
            f'unique_session_name: "{session_name}"\n'
            "write_into_file: true\n"
            f"file_write_period_ms: {cfg.file_write_period_ms}\n"
        )
        return header + base

    # ── 设备操作 ────────────────────────────────────────────────

    def get_device_info(self, serial: str) -> DeviceInfo:
        model = self._adb.get_prop("ro.product.model", serial).strip()
        soc = self._adb.get_prop("ro.soc.model", serial).strip()
        return DeviceInfo(serial=serial, model=model, soc=soc)

    def get_device_timestamp(self, serial: str) -> str:
        for cmd in ("date +%Y%m%d_%H%M%S", "toybox date +%Y%m%d_%H%M%S"):
            res = self._adb.shell_raw(serial, cmd)
            if res.returncode == 0:
                ts = (res.stdout or "").strip()
                if re.fullmatch(r"\d{8}_\d{6}", ts):
                    return ts
            elif is_device_unavailable(res):
                raise DeviceUnavailableError(
                    (res.stderr or "").strip() or (res.stdout or "").strip() or ERR_DEVICE_UNAVAILABLE
                )
        raise RuntimeError("读取设备时间失败")

    def probe_perfetto_capabilities(self, serial: str) -> PerfettoCapabilities:
        res = self._adb.shell_raw(serial, "perfetto --help")
        txt = (res.stdout or "") + "\n" + (res.stderr or "")
        return PerfettoCapabilities(help_text=txt)

    def ensure_device_trace_dir(self, serial: str, device_dir: str | None = None) -> str:
        """确保设备端 trace 目录可用，失败时尝试回退目录。返回实际使用的目录。"""
        device_dir = device_dir or self.config.device_trace_dir
        res = self._adb.shell_raw(serial, f"mkdir -p {device_dir}")
        if res.returncode == 0:
            return device_dir
        if is_device_unavailable(res):
            raise DeviceUnavailableError(
                (res.stderr or "").strip() or (res.stdout or "").strip() or "设备不可用"
            )
        if device_dir == "/data/local/tmp/perfetto-traces":
            fallback = "/data/misc/perfetto-traces"
            res2 = self._adb.shell_raw(serial, f"mkdir -p {fallback}")
            if res2.returncode == 0:
                logger.info("已回退 device_trace_dir 到 %s", fallback)
                return fallback
        raise RuntimeError(
            f"无法创建设备目录: {device_dir}\n"
            f"请确认该目录可写，推荐 /data/misc/perfetto-traces\n"
            f"详细: {(res.stderr or '').strip() or (res.stdout or '').strip()}"
        )

    # ── 抓取控制 ────────────────────────────────────────────────

    def start_tracing(
        self,
        serial: str,
        device_output_path: str,
        cfg: CaptureConfig | None = None,
    ) -> RunningTrace:
        """使用 detach 模式启动 perfetto，支持 clone 快照。"""
        cfg = cfg or self.config
        detach_key = f"lv_{uuid.uuid4().hex[:8]}"
        session_name = f"lv_capture_{detach_key}"

        if cfg.advanced.enable_raw_perfetto_config:
            pbtxt = cfg.advanced.raw_perfetto_config_text
        else:
            pbtxt = self.build_pbtxt_config_detach(session_name, cfg)

        res = self._adb.shell_raw(
            serial,
            f"perfetto --detach={detach_key} --txt -c - -o {device_output_path}",
            input_text=pbtxt,
            timeout=30,
        )
        combined = ((res.stderr or "") + " " + (res.stdout or "")).strip()
        if res.returncode != 0:
            if is_device_unavailable(res):
                raise DeviceUnavailableError(combined or "设备不可用")
            raise RuntimeError(f"启动 perfetto 失败: {combined}")

        logger.debug(
            "perfetto detach 启动 key=%s session=%s output=%s",
            detach_key, session_name, device_output_path,
        )
        return RunningTrace(
            device_output_path=device_output_path,
            mode=CaptureMode.SNAPSHOT,
            detach_key=detach_key,
            session_name=session_name,
        )

    def start_tracing_legacy(
        self,
        serial: str,
        device_output_path: str,
        cfg: CaptureConfig | None = None,
    ) -> RunningTrace:
        """传统 background 模式启动 perfetto，通过 PID 管理进程。"""
        cfg = cfg or self.config
        if cfg.advanced.enable_raw_perfetto_config:
            pbtxt = cfg.advanced.raw_perfetto_config_text
        else:
            pbtxt = self.build_pbtxt_config(cfg)

        res = self._adb.shell_raw(
            serial,
            f"perfetto --background --txt -c - -o {device_output_path}",
            input_text=pbtxt,
            timeout=30,
        )
        combined = ((res.stdout or "") + " " + (res.stderr or "")).strip()
        if res.returncode != 0:
            if is_device_unavailable(res):
                raise DeviceUnavailableError(combined or "设备不可用")
            raise RuntimeError(f"启动 perfetto 失败: {combined}")

        pid_match = re.search(r"\b(\d{2,})\b", combined)
        if not pid_match:
            raise RuntimeError(f"无法解析 perfetto PID: {combined}")
        pid = int(pid_match.group(1))

        logger.debug("perfetto background 启动 pid=%d output=%s", pid, device_output_path)
        return RunningTrace(
            device_output_path=device_output_path,
            mode=CaptureMode.AUTOBUFFER,
            pid=pid,
        )

    def snapshot_trace(
        self, serial: str, running: RunningTrace, snapshot_device_path: str,
    ) -> AdbCmdResult:
        """使用 --clone-by-name 创建 ring buffer 快照，不中断抓取。"""
        res = self._adb.shell_raw(
            serial,
            f"perfetto --clone-by-name {running.session_name} -o {snapshot_device_path}",
            timeout=60,
        )
        if res.returncode != 0:
            combined = ((res.stderr or "") + " " + (res.stdout or "")).strip()
            if is_device_unavailable(res):
                raise DeviceUnavailableError(combined or "设备不可用")
            raise RuntimeError(f"快照失败: {combined}")
        logger.debug("快照已创建: %s", snapshot_device_path)
        return res

    def stop_tracing(self, serial: str, running: RunningTrace) -> AdbCmdResult:
        """根据 mode 选择合适的方式停止 perfetto。"""
        if running.mode == CaptureMode.SNAPSHOT:
            res = self._adb.shell_raw(
                serial,
                f"perfetto --attach={running.detach_key} --stop",
                timeout=30,
            )
        else:
            res = self._adb.shell_raw(
                serial,
                f"kill {running.pid}",
                timeout=10,
            )
        if res.returncode != 0:
            combined = ((res.stderr or "") + " " + (res.stdout or "")).strip()
            if is_device_unavailable(res):
                raise DeviceUnavailableError(combined or "设备不可用")
            logger.warning("停止 perfetto 返回非零: %s", combined)
        time.sleep(0.3)
        return res

    # ── 会话管理 ────────────────────────────────────────────────

    def create_session(self, serial: str) -> CaptureSession:
        """创建新的抓取会话。目录延迟到首次保存 trace 时创建。"""
        output_dir = self.output_dir
        session_dir = output_dir / build_export_session_dirname()
        session = CaptureSession(
            session_id=uuid.uuid4().hex[:8],
            device_serial=serial,
            export_session_dir=session_dir,
        )
        self._session = session
        logger.info("创建会话: %s (目录将在首次保存时创建)", session.session_id)
        return session

    def cleanup_stale_sessions(self, serial: str) -> None:
        """清理设备上残留的 perfetto 会话，防止 'Too many sessions' 错误。"""
        try:
            res = self._adb.shell_raw(serial, "pkill -f perfetto", timeout=5)
            if res.returncode == 0:
                logger.info("已清理设备上残留的 perfetto 进程")
                time.sleep(0.5)
        except Exception:
            pass

    def _purge_device_path(self, serial: str, device_path: str) -> None:
        """启动 perfetto 前删除目标文件，避免属主冲突导致 Permission denied。

        /data/misc/perfetto-traces 下若存在其他用户（如 root）创建的同名文件，
        shell 身份的 perfetto 以写模式 open 会 EACCES（errno 13）。先 rm -f 清理，
        让 perfetto 以当前用户全新创建。删除失败仅告警不中断——目录无写权限时
        perfetto 会自行报错。
        """
        try:
            res = self._adb.shell_raw(serial, f"rm -f {device_path}", timeout=5)
            if res.returncode != 0:
                combined = (res.stderr or "") + (res.stdout or "")
                logger.warning("清理设备残留 trace 文件失败: %s -> %s", device_path, combined.strip())
        except Exception as e:
            logger.warning("清理设备残留 trace 文件异常: %s -> %s", device_path, e)

    def session_start_capture(self, serial: str, device_trace_dir: str) -> RunningTrace:
        """在当前会话中启动一段新的抓取。

        当前固定使用 AUTOBUFFER（background 模式 + 停止-重启保存）。
        SNAPSHOT（detach + clone）代码保留但未启用，因 clone 产出的
        trace 在部分设备上缺少完整 clock snapshot 导致时间戳异常。
        """
        session = self._session
        if session is None:
            raise RuntimeError("无活动会话")

        self.cleanup_stale_sessions(serial)
        session.trace_idx += 1
        device_path = f"{device_trace_dir}/current_{session.trace_idx}.perfetto-trace"

        self._purge_device_path(serial, device_path)
        running = self.start_tracing_legacy(serial, device_path)
        logger.info("使用自动缓冲模式 (background + 停止-重启)")

        session.running = running
        session.capture_state = CaptureState.CAPTURING
        import datetime
        session.start_time = datetime.datetime.now()
        return running

    def session_save_trace(
        self,
        serial: str,
        device_trace_dir: str,
        device_info: DeviceInfo,
    ) -> TraceItem:
        """保存当前 trace 段（停止 → 拉取 → 重启）。"""
        session = self._session
        if session is None or session.running is None:
            raise RuntimeError("无活动抓取")

        if not session.export_session_dir.exists():
            ensure_dir(session.export_session_dir)
            logger.info("创建会话导出目录: %s", session.export_session_dir)

        session.capture_state = CaptureState.SAVING

        device_ts = self.get_device_timestamp(serial)
        filename = build_trace_filename(device_info.model, device_info.soc, device_ts)
        host_path = choose_non_conflicting_path(session.export_session_dir / filename)

        saved_device_path = session.running.device_output_path
        self.stop_tracing(serial, session.running)

        item = TraceItem(
            kind=TraceKind.NORMAL,
            device_path=saved_device_path,
            export_filename=host_path.name,
        )
        session.saved_traces.append(item)

        # 持久化到待导出清单，供设备重连后接续导出（入队失败不应中断抓取）
        try:
            self.pending_store.add(PendingExportItem(
                serial=serial,
                device_path=item.device_path,
                export_filename=item.export_filename,
                session_dir=session.export_session_dir.name,
                device_model=device_info.model,
            ))
        except Exception as e:
            logger.warning("写入待导出清单失败: %s", e)

        session.trace_idx += 1
        new_device_path = (
            f"{device_trace_dir}/current_{session.trace_idx}.perfetto-trace"
        )
        self._purge_device_path(serial, new_device_path)
        running = self.start_tracing_legacy(serial, new_device_path)
        session.running = running
        session.capture_state = CaptureState.CAPTURING
        logger.info(
            "已保存第 %d 段 trace: %s",
            len(session.saved_traces), filename,
        )

        return item

    def session_stop_with_auto_save(
        self,
        serial: str,
        device_info: DeviceInfo,
        device_trace_dir: str,
        on_progress: type(None) | type(lambda: None) = None,
    ) -> list[Path]:
        """停止抓取，若有未保存的 trace 则自动保存，然后导出所有 trace。

        Args:
            serial: 设备序列号
            device_info: 设备信息
            device_trace_dir: 设备上的 trace 目录
            on_progress: 进度回调

        Returns:
            导出的文件路径列表
        """
        session = self._session
        if session is None:
            raise RuntimeError("无活动会话")

        if session.running is not None:
            if on_progress:
                on_progress("自动保存当前 trace...")
            try:
                self.session_save_trace(serial, device_trace_dir, device_info)
            except Exception as e:
                logger.warning("自动保存 trace 失败: %s", e)

        return self.session_stop_and_export(serial, on_progress)

    def session_stop_and_export(
        self,
        serial: str,
        on_progress: type(None) | type(lambda: None) = None,
    ) -> list[Path]:
        """停止抓取、导出所有已保存的 trace、结束会话。"""
        session = self._session
        if session is None:
            raise RuntimeError("无活动会话")

        session.capture_state = CaptureState.EXPORTING

        if session.running is not None:
            try:
                self.stop_tracing(serial, session.running)
            except Exception:
                logger.debug("停止 perfetto 时出错（已忽略）", exc_info=True)
            if session.running.mode == CaptureMode.SNAPSHOT:
                try:
                    self._adb.shell_raw(
                        serial, f"rm -f {session.running.device_output_path}",
                    )
                except Exception:
                    pass
            session.running = None

        exported: list[Path] = []
        if not session.saved_traces:
            logger.info("本次会话无保存的 trace，跳过导出")
            session.capture_state = CaptureState.IDLE
            self._session = None
            return exported

        for item in session.saved_traces:
            if item.exported:
                if item.export_path:
                    exported.append(item.export_path)
                continue
            dest = session.export_session_dir / item.export_filename
            if dest.exists():
                item.export_path = dest
                item.exported = True
                exported.append(dest)
                try:
                    self.pending_store.remove(serial, item.export_filename)
                except Exception:
                    pass
                continue

            if on_progress:
                on_progress(f"导出中: {item.export_filename}")

            # 防御：会话导出目录可能被历史扫描当作空目录清理，导出前确保存在
            ensure_dir(session.export_session_dir)
            pull_res = self._adb.pull_raw(serial, item.device_path, str(dest))
            if pull_res.returncode != 0:
                if is_device_unavailable(pull_res):
                    raise DeviceUnavailableError(
                        (pull_res.stderr or "").strip() or (pull_res.stdout or "").strip()
                    )
                logger.warning(
                    "导出失败: %s -> %s",
                    item.device_path,
                    (pull_res.stderr or "").strip() or (pull_res.stdout or "").strip(),
                )
                continue

            if self.config.export.cleanup_device_files:
                self._adb.shell_raw(serial, f"rm -f {item.device_path}")

            item.export_path = dest
            item.exported = True
            exported.append(dest)
            try:
                self.pending_store.remove(serial, item.export_filename)
            except Exception:
                pass

        session.capture_state = CaptureState.IDLE
        self._session = None
        logger.info("会话结束，已导出 %d 个文件", len(exported))
        return exported

    def resume_pending_exports(self, serial: str) -> dict:
        """接续导出：把该设备未导出的 trace 项补导到本地。

        按 serial 强隔离，只处理当前连接设备对应的待导出项；其他设备的项不受影响。

        Returns:
            结果统计字典：
            - exported: list[Path] 本次成功导出的本地路径（含已存在直接判定导出的项）
            - skipped_missing: list[str] 设备端文件已不存在的文件名（已出队）
            - failed: list[str] 本次 pull 失败、保留待下次重试的文件名
        """
        items = self.pending_store.get_for_serial(serial)
        if not items:
            return {"exported": [], "skipped_missing": [], "failed": []}

        exported: list[Path] = []
        skipped_missing: list[str] = []
        failed: list[str] = []

        for item in items:
            dest = self.output_dir / item.session_dir / item.export_filename

            # 1. 本地已存在且非空 → 视为已导出，直接出队
            if dest.exists() and dest.stat().st_size > 0:
                self.pending_store.remove(serial, item.export_filename)
                exported.append(dest)
                continue

            # 2. 设备端文件是否仍存在（可能被新抓取覆盖或已清理）
            ls_res = self._adb.shell_raw(serial, f"ls {item.device_path}")
            if ls_res.returncode != 0:
                self.pending_store.remove(serial, item.export_filename)
                skipped_missing.append(item.export_filename)
                continue

            # 3. pull 到本地（防御目录缺失）
            ensure_dir(dest.parent)
            pull_res = self._adb.pull_raw(serial, item.device_path, str(dest))
            if pull_res.returncode != 0:
                if is_device_unavailable(pull_res):
                    raise DeviceUnavailableError(
                        (pull_res.stderr or "").strip() or (pull_res.stdout or "").strip()
                    )
                failed.append(item.export_filename)
                continue

            self.pending_store.remove(serial, item.export_filename)
            exported.append(dest)

        logger.info("接续导出完成: serial=%s exported=%d missing=%d failed=%d",
                    serial, len(exported), len(skipped_missing), len(failed))
        return {"exported": exported, "skipped_missing": skipped_missing, "failed": failed}

    def session_abandon(self) -> None:
        """放弃当前会话，不尝试导出。用于设备断开后用户主动放弃。"""
        session = self._session
        if session is None:
            return
        session.capture_state = CaptureState.IDLE
        session.running = None
        # 放弃会话 = 不再导出这些 trace，同步清空其待导出清单项
        for item in session.saved_traces:
            try:
                self.pending_store.remove(session.device_serial, item.export_filename)
            except Exception:
                pass
        logger.info("会话已放弃 (session_id=%s, 已保存 %d 段)", session.session_id, len(session.saved_traces))
        self._session = None


class DeviceUnavailableError(Exception):
    """设备断开/不可用。"""
