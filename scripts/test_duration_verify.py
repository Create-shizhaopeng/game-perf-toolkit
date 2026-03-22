"""验证修正公式下的实际 trace 时长。

使用修正后的 buffer 大小抓取 30 秒，检查输出 trace 的实际时间范围。
"""

import subprocess
import time

SERIAL = "HA2DL5M3"
DEVICE_DIR = "/data/misc/perfetto-traces"
DEVICE_PATH = f"{DEVICE_DIR}/verify_duration.perfetto-trace"
DURATION_SEC = 15
BUFFER_KB = 22050  # 修正后：(1400) × 15 × 1.05

PBTXT = f"""
buffers {{
  size_kb: {BUFFER_KB}
  fill_policy: RING_BUFFER
}}
buffers {{
  size_kb: 4096
  fill_policy: RING_BUFFER
}}
data_sources {{
  config {{
    name: "linux.ftrace"
    target_buffer: 0
    ftrace_config {{
      atrace_categories: "sched"
      atrace_categories: "gfx"
      atrace_categories: "view"
      atrace_categories: "input"
      atrace_categories: "am"
      atrace_categories: "wm"
      atrace_categories: "freq"
      atrace_apps: "*"
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


def run_adb(args, input_text=None, timeout=30):
    cmd = ["adb", "-s", SERIAL] + args
    result = subprocess.run(
        cmd,
        input=input_text.encode("utf-8") if input_text else None,
        capture_output=True, timeout=timeout,
    )
    return (result.stdout or b"").decode("utf-8", errors="replace").strip()


def main():
    print(f"Buffer: {BUFFER_KB} KB ({BUFFER_KB/1024:.1f} MB)")
    print(f"目标时长: {DURATION_SEC}s")
    print()

    run_adb(["shell", f"mkdir -p {DEVICE_DIR}"])
    run_adb(["shell", f"rm -f {DEVICE_PATH}"])

    for wait_sec in [10, 20, 30, 45]:
        run_adb(["shell", f"rm -f {DEVICE_PATH}"])

        print(f"--- 测试: 抓取 {wait_sec} 秒后停止 ---")
        out = run_adb(
            ["shell", f"perfetto --background --txt -c - -o {DEVICE_PATH}"],
            input_text=PBTXT,
        )
        pid = None
        for part in out.split():
            if part.isdigit():
                pid = int(part)
                break
        if not pid:
            print(f"  ERROR: 无法获取 PID: {out}")
            continue

        print(f"  PID: {pid}, 等待 {wait_sec}s...")
        time.sleep(wait_sec)

        run_adb(["shell", f"kill -TERM {pid}"])
        time.sleep(1)

        size_out = run_adb(["shell", f"stat -c %s {DEVICE_PATH}"])
        try:
            file_size = int(size_out)
        except ValueError:
            print(f"  stat 失败: {size_out}")
            continue

        size_mb = file_size / (1024 * 1024)
        print(f"  文件大小: {size_mb:.2f} MB")

        if wait_sec <= DURATION_SEC:
            expected_sec = wait_sec
        else:
            expected_sec = DURATION_SEC

        estimated_duration = file_size / 1024 / 1386
        print(f"  估算时长: {estimated_duration:.1f}s (基于 1386 KB/s 速率)")
        print(f"  期望时长: ~{expected_sec}s")
        print()

        time.sleep(2)

    run_adb(["shell", f"rm -f {DEVICE_PATH}"])


if __name__ == "__main__":
    main()
