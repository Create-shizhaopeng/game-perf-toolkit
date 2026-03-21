"""外部进程桥接 — 调用非 Python 技术栈工具"""

from __future__ import annotations

import json
import logging
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


class ProcessBridge:
    """通过子进程调用外部可执行文件，使用 JSON 作为交互格式。

    输入通过 stdin 传入 JSON，输出从 stdout 读取 JSON。
    """

    def call(
        self,
        executable: str,
        args: list[str] | None = None,
        input_data: dict | None = None,
        timeout: int = 30,
        encoding: str = "utf-8",
    ) -> dict[str, Any]:
        """调用外部工具并返回 JSON 结果。

        Raises:
            subprocess.TimeoutExpired: 超时。
            subprocess.CalledProcessError: 进程非零退出。
            json.JSONDecodeError: 输出不是合法 JSON。
        """
        cmd = [executable, *(args or [])]
        stdin_data = (
            json.dumps(input_data, ensure_ascii=False) if input_data else None
        )

        logger.debug("调用外部进程: %s", " ".join(cmd))
        result = subprocess.run(
            cmd,
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding=encoding,
        )

        if result.returncode != 0:
            logger.error("外部进程失败: %s\nstderr: %s", cmd, result.stderr)
            raise subprocess.CalledProcessError(
                result.returncode, cmd, result.stdout, result.stderr
            )

        return json.loads(result.stdout)

    def call_raw(
        self,
        executable: str,
        args: list[str] | None = None,
        timeout: int = 30,
        encoding: str = "utf-8",
    ) -> str:
        """调用外部工具并返回原始文本输出。"""
        cmd = [executable, *(args or [])]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, encoding=encoding
        )
        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode, cmd, result.stdout, result.stderr
            )
        return result.stdout
