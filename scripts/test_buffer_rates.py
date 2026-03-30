"""测试不同 atrace categories / ftrace events 配置下的实际数据速率。

用于校准 buffer 自动计算公式的参数。
在连接的 Android 设备上执行多组 10 秒 Perfetto 抓取，
统计每组配置的实际文件大小和数据速率。
"""

import subprocess
import sys
import time

SERIAL = ""  # 留空则自动检测首台设备
DURATION_SEC = 10
DEVICE_DIR = "/data/misc/perfetto-traces"
BUFFER_KB = 262144  # 256MB - 确保不会截断

PBTXT_TEMPLATE = """
buffers {{
  size_kb: {buffer_kb}
  fill_policy: RING_BUFFER
}}
buffers {{
  size_kb: 4096
  fill_policy: RING_BUFFER
}}
flush_period_ms: 5000
incremental_state_config {{
  clear_period_ms: 15000
}}
builtin_data_sources {{
  primary_trace_clock: BUILTIN_CLOCK_BOOTTIME
}}
data_sources {{
  config {{
    name: "linux.ftrace"
    target_buffer: 0
    ftrace_config {{
{atrace_lines}
{ftrace_lines}
      atrace_apps: "*"
      compact_sched {{
        enabled: true
      }}
    }}
  }}
}}
data_sources {{
  config {{
    name: "linux.process_stats"
    target_buffer: 1
    process_stats_config {{
      scan_all_processes_on_start: true
      record_thread_names: true
      proc_stats_poll_ms: 1000
    }}
  }}
}}
data_sources {{
  config {{
    name: "android.packages_list"
    target_buffer: 1
    packages_list_config {{
    }}
  }}
}}
"""


def detect_serial() -> str:
    """自动检测首台已连接设备的序列号。"""
    result = subprocess.run(
        ["adb", "devices"], capture_output=True, timeout=10,
    )
    lines = (result.stdout or b"").decode("utf-8", errors="replace").strip().splitlines()
    for line in lines[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            return parts[0]
    print("错误: 未检测到已连接的 ADB 设备")
    sys.exit(1)


def run_adb(serial: str, args: list[str], input_text: str | None = None, timeout: int = 30) -> str:
    cmd = ["adb", "-s", serial] + args
    result = subprocess.run(
        cmd,
        input=input_text.encode("utf-8") if input_text else None,
        capture_output=True,
        timeout=timeout,
    )
    return (result.stdout or b"").decode("utf-8", errors="replace").strip()


def run_test(
    serial: str,
    categories: list[str],
    ftrace_events: list[str],
    label: str,
) -> dict:
    atrace_lines = "\n".join(f'      atrace_categories: "{c}"' for c in categories)
    ftrace_lines = "\n".join(f'      ftrace_events: "{e}"' for e in ftrace_events)
    pbtxt = PBTXT_TEMPLATE.format(
        buffer_kb=BUFFER_KB, atrace_lines=atrace_lines, ftrace_lines=ftrace_lines,
    )

    total_tags = len(categories) + len(ftrace_events)
    tag_id = f"test_rate_{total_tags}"
    device_path = f"{DEVICE_DIR}/{tag_id}.perfetto-trace"

    run_adb(serial, ["shell", f"mkdir -p {DEVICE_DIR}"])
    run_adb(serial, ["shell", f"rm -f {device_path}"])

    print(f"\n[{label}] 开始抓取: {len(categories)} atrace + {len(ftrace_events)} ftrace = {total_tags} tags, {DURATION_SEC}s...")
    if categories:
        print(f"  Atrace: {', '.join(categories)}")
    if ftrace_events:
        print(f"  Ftrace: {', '.join(ftrace_events)}")

    out = run_adb(
        serial,
        ["shell", f"perfetto --background --txt -c - -o {device_path}"],
        input_text=pbtxt,
    )
    pid = None
    for part in out.split():
        if part.isdigit():
            pid = int(part)
            break

    if not pid:
        print(f"  ERROR: 无法获取 PID, output={out}")
        return {"label": label, "error": "no PID"}

    print(f"  PID: {pid}, 等待 {DURATION_SEC} 秒...")
    time.sleep(DURATION_SEC)

    run_adb(serial, ["shell", f"kill -TERM {pid}"])
    time.sleep(1)

    size_out = run_adb(serial, ["shell", f"stat -c %s {device_path}"])
    try:
        file_size = int(size_out)
    except ValueError:
        ls_out = run_adb(serial, ["shell", f"ls -l {device_path}"])
        print(f"  stat 失败, ls 输出: {ls_out}")
        file_size = 0

    size_mb = file_size / (1024 * 1024)
    rate_kb_per_sec = (file_size / 1024) / DURATION_SEC if DURATION_SEC > 0 else 0
    rate_per_tag = rate_kb_per_sec / total_tags if total_tags else 0

    print(f"  文件大小: {size_mb:.2f} MB")
    print(f"  总速率: {rate_kb_per_sec:.0f} KB/s")
    print(f"  每 tag 速率: {rate_per_tag:.0f} KB/s")

    run_adb(serial, ["shell", f"rm -f {device_path}"])

    return {
        "label": label,
        "atrace_count": len(categories),
        "ftrace_count": len(ftrace_events),
        "total_tags": total_tags,
        "size_bytes": file_size,
        "size_mb": round(size_mb, 2),
        "rate_kb_per_sec": round(rate_kb_per_sec),
        "rate_per_tag_kb_per_sec": round(rate_per_tag),
    }


def main():
    serial = SERIAL or detect_serial()

    print("=" * 70)
    print("Perfetto Buffer 速率校准测试")
    print(f"设备: {serial} | 抓取时长: {DURATION_SEC}s | Buffer: {BUFFER_KB} KB")
    print("=" * 70)

    ftrace_common = [
        "sched/sched_switch", "sched/sched_wakeup",
        "power/cpu_frequency", "power/cpu_idle",
    ]

    ftrace_extended = ftrace_common + [
        "power/suspend_resume",
        "irq/irq_handler_entry", "irq/irq_handler_exit",
        "irq/softirq_entry", "irq/softirq_exit",
        "block/block_rq_issue", "block/block_rq_complete",
        "gpu_mem/gpu_mem_total",
    ]

    tests = [
        # 纯 atrace 测试
        (["sched"], [], "A1: 仅 sched (1 atrace)"),
        (["sched", "gfx", "view"], [], "A3: 3 atrace"),
        (["sched", "gfx", "view", "input", "am", "wm", "freq"], [], "A7: 7 atrace (默认)"),
        (
            [
                "sched", "freq", "idle", "am", "wm", "gfx", "view",
                "input", "irq", "sync", "binder_driver", "webview",
                "workq", "thermal", "pagecache", "dalvik", "pm", "ss", "memreclaim",
            ],
            [],
            "A19: 19 atrace (全选)",
        ),
        # atrace + ftrace 混合测试
        (
            ["sched", "gfx", "view", "input", "am", "wm", "freq"],
            ftrace_common,
            "A7+F4: 7 atrace + 4 ftrace",
        ),
        (
            ["sched", "gfx", "view", "input", "am", "wm", "freq"],
            ftrace_extended,
            "A7+F12: 7 atrace + 12 ftrace",
        ),
        (
            [
                "sched", "freq", "idle", "am", "wm", "gfx", "view",
                "input", "irq", "sync", "binder_driver", "workq",
                "thermal", "pagecache", "dalvik",
            ],
            ftrace_extended,
            "A15+F12: 15 atrace + 12 ftrace",
        ),
    ]

    results = []
    for cats, ftrace, label in tests:
        result = run_test(serial, cats, ftrace, label)
        results.append(result)
        time.sleep(2)

    print("\n" + "=" * 70)
    print("测试结果汇总")
    print("=" * 70)
    print(f"{'配置':<30} {'tags':>5} {'大小(MB)':>10} {'总速率(KB/s)':>14} {'每tag(KB/s)':>12}")
    print("-" * 75)
    for r in results:
        if "error" in r:
            print(f"{r['label']:<30} ERROR")
        else:
            print(
                f"{r['label']:<30} {r['total_tags']:>5} {r['size_mb']:>10.2f} "
                f"{r['rate_kb_per_sec']:>14} {r['rate_per_tag_kb_per_sec']:>12}"
            )

    valid = [r for r in results if "error" not in r]
    if valid:
        print("\n" + "-" * 70)
        print("建议公式参数:")

        light_results = [r for r in valid if r["total_tags"] <= 7]
        heavy_results = [r for r in valid if r["total_tags"] > 7]

        if light_results:
            baseline = light_results[-1]
            print(f"  轻载基线 (≤7 tags): {baseline['rate_kb_per_sec']} KB/s "
                  f"({baseline['label']})")

        if light_results and heavy_results:
            base_rate = light_results[-1]["rate_kb_per_sec"]
            increments = []
            for hr in heavy_results:
                extra_tags = hr["total_tags"] - light_results[-1]["total_tags"]
                extra_rate = hr["rate_kb_per_sec"] - base_rate
                if extra_tags > 0:
                    per_tag = extra_rate / extra_tags
                    increments.append(per_tag)
                    print(f"  {hr['label']}: 多 {extra_tags} tags → +{extra_rate} KB/s → 每tag +{per_tag:.0f} KB/s")
            if increments:
                avg_incr = sum(increments) / len(increments)
                print(f"\n  HEAVY_PER_CAT_RATE_KB 建议值: {avg_incr:.0f} KB/s")
                print(f"  LIGHT_RATE_KB_PER_SEC 建议值: {base_rate} KB/s")


if __name__ == "__main__":
    main()
