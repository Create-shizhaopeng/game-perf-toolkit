"""验证 perfetto --clone 功能是否可用于无间隙快照。"""

import subprocess
import time

SERIAL = "HA2DL5M3"
DEVICE_DIR = "/data/misc/perfetto-traces"
DETACH_KEY = "test_clone"
BUFFER_KB = 22050

PBTXT = f"""
unique_session_name: "test_clone_session"
write_into_file: true
file_write_period_ms: 5000
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
"""


def run_adb(args, input_text=None, timeout=30):
    cmd = ["adb", "-s", SERIAL] + args
    result = subprocess.run(
        cmd,
        input=input_text.encode("utf-8") if input_text else None,
        capture_output=True, timeout=timeout,
    )
    stdout = (result.stdout or b"").decode("utf-8", errors="replace").strip()
    stderr = (result.stderr or b"").decode("utf-8", errors="replace").strip()
    return stdout, stderr, result.returncode


def main():
    print("=" * 60)
    print("Perfetto --clone 快照功能验证")
    print("=" * 60)

    run_adb(["shell", f"mkdir -p {DEVICE_DIR}"])

    print("\n1. 启动 detach 模式的 perfetto...")
    out, err, rc = run_adb(
        ["shell", f"perfetto --detach={DETACH_KEY} --txt -c - -o {DEVICE_DIR}/detach_main.pb"],
        input_text=PBTXT,
    )
    print(f"   stdout: {out}")
    print(f"   stderr: {err}")
    print(f"   returncode: {rc}")

    if rc != 0:
        print("   ERROR: 启动失败")
        return

    print("\n2. 等待 10 秒...")
    time.sleep(10)

    print("\n3. 尝试 clone-by-name...")
    clone_path = f"{DEVICE_DIR}/clone_snapshot_1.pb"
    out, err, rc = run_adb(
        ["shell", f"perfetto --clone-by-name test_clone_session -o {clone_path}"],
    )
    print(f"   stdout: {out}")
    print(f"   stderr: {err}")
    print(f"   returncode: {rc}")

    if rc == 0:
        out2, _, _ = run_adb(["shell", f"stat -c %s {clone_path}"])
        print(f"   快照文件大小: {int(out2)/1024/1024:.2f} MB")
    else:
        print("   clone-by-name 失败, 尝试 --clone...")

    print("\n4. 再等 10 秒后再次快照...")
    time.sleep(10)

    clone_path2 = f"{DEVICE_DIR}/clone_snapshot_2.pb"
    out, err, rc = run_adb(
        ["shell", f"perfetto --clone-by-name test_clone_session -o {clone_path2}"],
    )
    print(f"   stdout: {out}")
    print(f"   stderr: {err}")
    print(f"   returncode: {rc}")

    if rc == 0:
        out2, _, _ = run_adb(["shell", f"stat -c %s {clone_path2}"])
        print(f"   快照文件大小: {int(out2)/1024/1024:.2f} MB")

    print("\n5. 检查原始 session 是否仍在运行...")
    out, err, rc = run_adb(["shell", f"perfetto --is_detached={DETACH_KEY}"])
    print(f"   is_detached: rc={rc}, out={out}")

    print("\n6. 停止原始 session...")
    out, err, rc = run_adb(["shell", f"perfetto --attach={DETACH_KEY} --stop"])
    print(f"   attach --stop: rc={rc}")

    print("\n7. 清理...")
    for f in ["detach_main.pb", "clone_snapshot_1.pb", "clone_snapshot_2.pb"]:
        run_adb(["shell", f"rm -f {DEVICE_DIR}/{f}"])

    print("\n验证完成!")


if __name__ == "__main__":
    main()
