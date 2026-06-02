# SOP manager merged into Skill system — backward-compatible stub
import logging
import yaml

logger = logging.getLogger(__name__)


def _split_frontmatter(content):
    """Parse YAML frontmatter from Markdown content. Returns (dict, body)."""
    if not content.startswith("---"):
        return {}, content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content
    try:
        fm = yaml.safe_load(parts[1]) or {}
        return fm, parts[2]
    except Exception:
        return {}, content


class SOPManager:
    def __init__(self, builtin_dir=None, custom_dir=None):
        self._builtin_dir = builtin_dir
        self._custom_dir = custom_dir

    def load_all(self):
        """Load all SOPs from builtin + custom directories."""
        sops = []
        from pathlib import Path
        for d in [self._builtin_dir, self._custom_dir]:
            if d and Path(d).exists():
                for f in Path(d).glob("*.md"):
                    try:
                        content = f.read_text(encoding="utf-8")
                        fm, body = _split_frontmatter(content)
                        from modules.agent_chat.src.models import SOPDocument, SOPSource
                        src = SOPSource.BUILTIN if d == str(self._builtin_dir) else SOPSource.CUSTOM
                        sops.append(SOPDocument(
                            path=f, title=fm.get("title", f.stem),
                            keywords=fm.get("keywords", []),
                            description=fm.get("description", ""),
                            recommended_provider=fm.get("recommended_provider", ""),
                            required_tools=fm.get("required_tools", []),
                            content=body, source=src,
                        ))
                    except Exception as e:
                        logger.warning("SOP load failed %s: %s", f, e)
        return sops

    def get_all_metadata(self):
        sops = self.load_all()
        return [{"name": s.title, "description": s.description, "keywords": s.keywords} for s in sops]

    def import_sop(self, path):
        logger.info("SOP import: %s", path)
