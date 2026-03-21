"""Build script for Toolkit.

Usage:
    python build.py

Produces:
    dist/Toolkit/          (onedir distribution)
    dist/Toolkit-v1.0.0.zip (compressed archive)
"""
import os
import subprocess
import sys
import shutil
import zipfile

VERSION = "1.0.0"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(BASE_DIR, "dist")
SPEC_FILE = os.path.join(BASE_DIR, "build.spec")
APP_NAME = "Toolkit"
OUTPUT_NAME = f"{APP_NAME}-v{VERSION}"


def run_pyinstaller():
    print(f"[BUILD] Running PyInstaller with {SPEC_FILE}...")
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", SPEC_FILE, "--noconfirm"],
        cwd=BASE_DIR,
    )
    if result.returncode != 0:
        print("[BUILD] PyInstaller failed!")
        sys.exit(1)
    print("[BUILD] PyInstaller completed successfully.")


def ensure_data_dir():
    dist_app = os.path.join(DIST_DIR, APP_NAME)
    data_dir = os.path.join(dist_app, "data")
    os.makedirs(data_dir, exist_ok=True)

    import json
    config_path = os.path.join(data_dir, "config.json")
    if not os.path.exists(config_path):
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump({"theme": "dark", "adb_path": ""}, f, indent=2)
        print("[BUILD] Created default config.json")

    src_profiles = os.path.join(BASE_DIR, "data", "device_profiles.json")
    dst_profiles = os.path.join(data_dir, "device_profiles.json")
    if os.path.exists(src_profiles):
        shutil.copy2(src_profiles, dst_profiles)
        print("[BUILD] Copied device_profiles.json with sample data")


def create_zip():
    dist_app = os.path.join(DIST_DIR, APP_NAME)
    zip_path = os.path.join(DIST_DIR, f"{OUTPUT_NAME}.zip")

    if os.path.exists(zip_path):
        os.remove(zip_path)

    print(f"[BUILD] Creating {zip_path}...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(dist_app):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, DIST_DIR)
                zf.write(file_path, arcname)

    size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    print(f"[BUILD] Created {zip_path} ({size_mb:.1f} MB)")


def main():
    print(f"[BUILD] Building {APP_NAME} v{VERSION}")
    run_pyinstaller()
    ensure_data_dir()
    create_zip()
    print(f"[BUILD] Done! Output: dist/{OUTPUT_NAME}.zip")


if __name__ == "__main__":
    main()
