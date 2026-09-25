"""Static operator pages served next to the JSON endpoints."""

from pathlib import Path
from typing import Dict, List

from .router import PathNotFound

PAGE_FILES: Dict[str, str] = {
    "overview": "overview.html",
    "operations": "operations.html",
    "audit": "audit.html",
}


def default_pages_root() -> Path:
    return Path(__file__).resolve().parents[2] / "web"


class PageCatalog:
    def __init__(self, root: Path = None) -> None:
        self._root = Path(root) if root is not None else default_pages_root()

    @property
    def root(self) -> Path:
        return self._root

    def names(self) -> List[str]:
        return sorted(PAGE_FILES)

    def path(self, name: str) -> Path:
        filename = PAGE_FILES.get(name)
        if filename is None:
            raise PathNotFound("no such page", page=name)
        return self._root / filename

    def exists(self, name: str) -> bool:
        try:
            return self.path(name).exists()
        except PathNotFound:
            return False

    def read(self, name: str) -> str:
        target = self.path(name)
        if not target.exists():
            raise PathNotFound("page file is missing", page=name, path=str(target))
        return target.read_text(encoding="utf-8")

    def describe(self) -> Dict[str, object]:
        return {
            "root": str(self._root),
            "pages": [
                {"name": name, "present": self.exists(name)} for name in self.names()
            ],
        }
