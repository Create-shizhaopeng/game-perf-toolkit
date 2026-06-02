# Compat shim — bridges old SkillDiscovery API to new SkillRegistry
from toolkit.core.skill_registry import SkillRegistry as _CoreRegistry, parse_yaml_frontmatter

class SkillDiscovery:
    """Backward-compatible SkillDiscovery wrapping the core SkillRegistry."""

    def __init__(self, search_paths=None):
        self._core = _CoreRegistry()
        for p in (search_paths or []):
            self._core.add_search_path(p)

    def add_search_path(self, path):
        self._core.add_search_path(path)

    def scan(self):
        """Scan all search paths, return {name: (SkillMetadata, skill_dir)}."""
        metas = self._core.scan()
        # Filter out disabled skills
        return {m.name: (m, m.skill_dir) for m in metas if getattr(m, 'enabled', True)}

    def get_all_metadata(self):
        return self._core.get_skills()

    def get_skill_path(self, name):
        meta = self._core.get_skill(name)
        return meta.skill_dir if meta else None

    def get_metadata(self, name):
        return self._core.get_skill(name)
