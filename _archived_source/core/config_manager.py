import json
import os


class ConfigManager:
    DEFAULTS = {
        "theme": "dark",
        "adb_path": "",
    }

    def __init__(self, config_path: str = None):
        if config_path is None:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base, "data", "config.json")
        self._path = config_path
        self._config: dict = {}
        self.load()

    def load(self):
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._config = json.load(f)
            except (json.JSONDecodeError, TypeError):
                self._config = {}
        else:
            self._config = {}

        for key, default in self.DEFAULTS.items():
            self._config.setdefault(key, default)

    def save(self):
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._config, f, indent=2)

    def get_theme(self) -> str:
        return self._config.get("theme", "dark")

    def set_theme(self, theme: str):
        if theme not in ("dark", "light"):
            raise ValueError(f"无效主题: {theme}, 仅支持 dark/light")
        self._config["theme"] = theme
        self.save()

    def get_adb_path(self) -> str:
        return self._config.get("adb_path", "")

    def set_adb_path(self, path: str):
        self._config["adb_path"] = path
        self.save()
