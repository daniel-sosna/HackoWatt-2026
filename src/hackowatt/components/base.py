"""Shared contract for independently runnable HackoWatt components."""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from typing import Protocol, Sequence

from ..config import ProjectPaths


class Component(Protocol):
    """A unit of application behaviour that can register and run itself."""

    name: str
    help: str

    def add_arguments(self, subparsers: argparse._SubParsersAction) -> None: ...

    def run(self, args: argparse.Namespace, paths: ProjectPaths) -> int: ...


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
