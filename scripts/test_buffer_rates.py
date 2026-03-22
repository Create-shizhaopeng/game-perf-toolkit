"""测试不同 atrace categories 配置下的实际数据速率。

用于校准 buffer 自动计算公式的参数。
在连接的 Android 设备上执行多组 10 秒 Perfetto 抓取，
统计每组配置的实际文件大小和数据速率。
"""

import subprocess
import sys
import time
import tempfile
import os

SERIAL = "HA2DL5M3"
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
data_sources {{
  config {{
    name: "linux.ftrace"
    target_buffer: 0
    ftrace_config {{
{atrace_lines}
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


def run_adb(args: list[str], input_text: str | None = None, timeout: int = 30) -> str:
    cmd = ["adb", "-s", SERIAL] + args
    result = subprocess.run(
        cmd,
        input=input_text.encode("utf-8") if input_text else None,
        capture_output=True,
        timeout=timeout,
    )
    return (result.stdout or b"").decode("utf-8", errors="replace").strip()


def run_test(categories: list[str], label: str) -> dict:
    atrace_lines = "\n".join(f'      atrace_categories: "{c}"' for c in categories)
    pbtxt = PBTXT_TEMPLATE.format(buffer_kb=BUFFER_KB, atrace_lines=atrace_lines)

    device_path = f"{DEVICE_DIR}/test_rate_{len(categories)}.perfetto-trace"

    run_adb(["shell", f"mkdir -p {DEVICE_DIR}"])

    run_adb(["shell", f"rm -f {device_path}"])

    print(f"\n[{label}] 开始抓取: {len(categories)} categories, {DURATION_SEC}s...")
    print(f"  Categories: {', '.join(categories)}")

    out = run_adb(
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

    run_adb(["shell", f"kill -TERM {pid}"])
    time.sleep(1)

    size_out = run_adb(["shell", f"stat -c %s {device_path}"])
    try:
        file_size = int(size_out)
    except ValueError:
        ls_out = run_adb(["shell", f"ls -l {device_path}"])
        print(f"  stat 失败, ls 输出: {ls_out}")
        file_size = 0

    size_mb = file_size / (1024 * 1024)
    rate_kb_per_sec = (file_size / 1024) / DURATION_SEC if DURATION_SEC > 0 else 0
    rate_per_cat = rate_kb_per_sec / len(categories) if categories else 0

    print(f"  文件大小: {size_mb:.2f} MB")
    print(f"  总速率: {rate_kb_per_sec:.0f} KB/s")
    print(f"  每 category 速率: {rate_per_cat:.0f} KB/s")

    run_adb(["shell", f"rm -f {device_path}"])

    return {
        "label": label,
        "categories": len(categories),
        "size_bytes": file_size,
        "size_mb": round(size_mb, 2),
        "rate_kb_per_sec": round(rate_kb_per_sec),
        "rate_per_cat_kb_per_sec": round(rate_per_cat),
    }


def main():
    print("=" * 60)
    print("Perfetto Buffer 速率校准测试")
    print(f"设备: {SERIAL} | 抓取时长: {DURATION_SEC}s | Buffer: {BUFFER_KB} KB")
    print("=" * 60)

    tests = [
        (["sched"], "仅 sched (最基础)"),
        (["sched", "gfx", "view"], "3 categories (轻量)"),
        (["sched", "gfx", "view", "input", "am", "wm", "freq"], "7 categories (推荐默认)"),
        (
            [
                "sched", "freq", "idle", "am", "wm", "gfx", "view",
                "input", "irq", "sync", "binder_driver", "webview",
                "workq", "thermal", "pagecache", "dalvik", "pm", "ss", "memreclaim",
            ],
            "19 categories (全选)"
        ),
    ]

    results = []
    for cats, label in tests:
        result = run_test(cats, label)
        results.append(result)
        time.sleep(2)

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    print(f"{'配置':<25} {'大小(MB)':>10} {'总速率(KB/s)':>14} {'每cat(KB/s)':>12}")
    print("-" * 65)
    for r in results:
        if "error" in r:
            print(f"{r['label']:<25} ERROR")
        else:
            print(
                f"{r['label']:<25} {r['size_mb']:>10.2f} "
                f"{r['rate_kb_per_sec']:>14} {r['rate_per_cat_kb_per_sec']:>12}"
            )

    if results and not any("error" in r for r in results):
        avg_per_cat = sum(r["rate_per_cat_kb_per_sec"] for r in results) / len(results)
        max_total = max(r["rate_kb_per_sec"] for r in results)
        print(f"\n平均每 category 速率: {avg_per_cat:.0f} KB/s")
        print(f"最大总速率: {max_total} KB/s")
        print(f"\n建议公式参数:")
        print(f"  base_rate = {results[0]['rate_kb_per_sec']} KB/s (仅 sched)")
        if len(results) > 1:
            incr = (results[-1]["rate_kb_per_sec"] - results[0]["rate_kb_per_sec"]) / (
                results[-1]["categories"] - results[0]["categories"]
            )
            print(f"  per_category_rate ≈ {incr:.0f} KB/s")


if __name__ == "__main__":
    main()
