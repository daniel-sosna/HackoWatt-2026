"""Shared contract for independently runnable HackoWatt components."""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, Sequence


@dataclass(frozen=True)
class ProjectContext:
    """Stable project paths passed to every component."""

    root: Path

    @classmethod
    def discover(cls, requested_root: str | Path | None = None) -> 'ProjectContext':
        """Find a repository checkout for source and editable installations."""
        candidates = ([Path(requested_root)] if requested_root else []) + [
            Path.cwd(), Path(__file__).resolve().parents[3],
        ]
        for candidate in candidates:
            root = candidate.resolve()
            if (root / 'config').is_dir() and (root / 'data').is_dir() and (root / 'src').is_dir():
                return cls(root)
        raise FileNotFoundError(
            'Could not locate a HackoWatt project root. Run from the repository root or pass --project-root PATH.')

    def path(self, value: str | Path) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.root / path


class Component(Protocol):
    """A unit of application behaviour that can register and run itself."""

    name: str
    help: str

    def add_arguments(self, subparsers: argparse._SubParsersAction) -> None: ...

    def run(self, args: argparse.Namespace, context: ProjectContext) -> int: ...


@dataclass
class ComponentRegistry:
    """Explicit registry keeps the application entry point independent of features."""

    _components: list[Component] = field(default_factory=list)

    def register(self, component: Component) -> None:
        if any(existing.name == component.name for existing in self._components):
            raise ValueError(f'Duplicate component name: {component.name}')
        self._components.append(component)

    @property
    def components(self) -> Sequence[Component]:
        return tuple(self._components)

    def add_subparsers(self, subparsers: argparse._SubParsersAction) -> None:
        for component in self._components:
            component.add_arguments(subparsers)
