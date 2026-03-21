import json
import os
import tempfile
from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class DeviceProfile:
    brand: str
    manufacturer: str
    model: str
    notes: str = ""

    def unique_key(self) -> str:
        return f"{self.brand}|{self.manufacturer}|{self.model}".lower()


class ProfileManager:
    def __init__(self, data_path: str = None):
        if data_path is None:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_path = os.path.join(base, "data", "device_profiles.json")
        self._path = data_path
        self._profiles: List[DeviceProfile] = []
        self.load()

    def load(self):
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._profiles = [
                    DeviceProfile(**item) for item in data if isinstance(item, dict)
                ]
            except (json.JSONDecodeError, TypeError):
                self._profiles = []
        else:
            self._profiles = []

    def save(self):
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        dir_name = os.path.dirname(self._path)
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(
                    [asdict(p) for p in self._profiles],
                    f, indent=2, ensure_ascii=False
                )
            if os.path.exists(self._path):
                os.replace(tmp_path, self._path)
            else:
                os.rename(tmp_path, self._path)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def get_all(self) -> List[DeviceProfile]:
        return list(self._profiles)

    def exists(self, brand: str, manufacturer: str, model: str) -> bool:
        key = f"{brand}|{manufacturer}|{model}".lower()
        return any(p.unique_key() == key for p in self._profiles)

    def find(self, field_name: str, value: str) -> List[DeviceProfile]:
        value_lower = value.lower()
        return [
            p for p in self._profiles
            if value_lower in getattr(p, field_name, "").lower()
        ]

    def add(self, profile: DeviceProfile):
        if self.exists(profile.brand, profile.manufacturer, profile.model):
            raise ValueError(
                f"设备档案已存在: {profile.brand}/{profile.manufacturer}/{profile.model}"
            )
        self._profiles.append(profile)
        self.save()

    def update(self, old_profile: DeviceProfile, new_profile: DeviceProfile):
        if old_profile.unique_key() != new_profile.unique_key():
            if self.exists(new_profile.brand, new_profile.manufacturer, new_profile.model):
                raise ValueError(
                    f"设备档案已存在: {new_profile.brand}/{new_profile.manufacturer}/{new_profile.model}"
                )
        idx = self._find_index(old_profile)
        if idx < 0:
            raise ValueError("未找到要更新的档案")
        self._profiles[idx] = new_profile
        self.save()

    def delete(self, profile: DeviceProfile):
        idx = self._find_index(profile)
        if idx < 0:
            raise ValueError("未找到要删除的档案")
        self._profiles.pop(idx)
        self.save()

    def import_from(self, path: str) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        imported = 0
        skipped = 0
        for item in data:
            if not isinstance(item, dict):
                skipped += 1
                continue
            try:
                profile = DeviceProfile(
                    brand=item.get("brand", ""),
                    manufacturer=item.get("manufacturer", ""),
                    model=item.get("model", ""),
                    notes=item.get("notes", ""),
                )
                if not profile.brand or not profile.manufacturer or not profile.model:
                    skipped += 1
                    continue
                self.add(profile)
                imported += 1
            except ValueError:
                skipped += 1

        return {"imported": imported, "skipped": skipped}

    def _find_index(self, profile: DeviceProfile) -> int:
        key = profile.unique_key()
        for i, p in enumerate(self._profiles):
            if p.unique_key() == key:
                return i
        return -1
