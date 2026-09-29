"""Project-relative paths shared by commands and services."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectPaths:
    root: Path

    @classmethod
    def discover(cls, requested_root: str | Path | None = None) -> "ProjectPaths":
        candidates = ([Path(requested_root)] if requested_root else []) + [
            Path.cwd(), Path(__file__).resolve().parents[3],
        ]
        for candidate in candidates:
            root = candidate.resolve()
            if (root / "config").is_dir() and (root / "data").is_dir() and (root / "src").is_dir():
                return cls(root)
        raise FileNotFoundError(
            "Could not locate a HackoWatt project root. Run from the repository root or pass --project-root PATH."
        )

    def resolve(self, value: str | Path) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.root / path
