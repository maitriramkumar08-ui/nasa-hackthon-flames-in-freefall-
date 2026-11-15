"""Compatibility alias: ``pyra`` is the former name of :mod:`pyrakit`.

The library was renamed to ``pyrakit`` so that one import name covers the whole
toolkit, and so that it no longer collides with the separate application package also
called ``pyra``. Existing code keeps working:

    import pyra as pk                  # still valid
    from pyra.adapters import check_envelope

Both resolve to the very same module objects as ``pyrakit``, so values created through
one name pass ``isinstance`` checks from the other. New code should import ``pyrakit``.

This module is a thin alias and holds no implementation. Note that when the current
working directory contains an unrelated folder named ``pyra``, that folder wins over
this one, because Python searches the current directory first; ``import pyrakit`` is
unaffected and is the reliable spelling.
"""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import sys
from types import ModuleType

_NEW = "pyrakit"
_OLD = "pyra"


class _AliasLoader(importlib.abc.Loader):
    """Hands back the already-imported ``pyrakit`` module instead of executing code."""

    def __init__(self, module: ModuleType) -> None:
        self._module = module

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> ModuleType:
        return self._module

    def exec_module(self, module: ModuleType) -> None:
        return None


class _AliasFinder(importlib.abc.MetaPathFinder):
    """Resolves every ``pyra.*`` import to the identical ``pyrakit.*`` module object.

    Returning the same object, rather than importing the source a second time under a
    different name, is what keeps ``isinstance`` and identity comparisons working across
    the old and new spellings.
    """

    def find_spec(
        self,
        fullname: str,
        path: object = None,
        target: ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        if fullname != _OLD and not fullname.startswith(_OLD + "."):
            return None
        target_name = _NEW + fullname[len(_OLD) :]
        try:
            module = importlib.import_module(target_name)
        except ImportError:
            return None
        sys.modules[fullname] = module
        spec = importlib.util.spec_from_loader(fullname, _AliasLoader(module))
        if spec is not None and getattr(module, "__path__", None) is not None:
            spec.submodule_search_locations = list(module.__path__)
        return spec


def _shadowing_hint(module: ModuleType) -> str:
    """Explain the likely cause when ``pyrakit`` resolves to the wrong package.

    Python searches the current working directory before installed packages, so a local
    folder of the same name wins. The resulting error otherwise names a missing
    attribute rather than the real cause.
    """
    found = getattr(module, "__file__", None)
    from pathlib import Path

    location = str(Path(found).parent) if found else "an unknown location"
    return (
        f"'import pyrakit' resolved to {location}, which is not the PYRA library.\n"
        "A directory of that name in your current working directory shadows the "
        "installed library, because Python searches the current directory first.\n"
        "Run your script from a different directory, or start Python with -I "
        "(isolated mode) so the current directory is not searched."
    )


if not any(isinstance(finder, _AliasFinder) for finder in sys.meta_path):
    sys.meta_path.insert(0, _AliasFinder())

_pyrakit = importlib.import_module(_NEW)

if not hasattr(_pyrakit, "__all__"):
    raise ImportError(_shadowing_hint(_pyrakit))

# Re-export the public surface so ``import pyra as pk; pk.run_fire_test(...)`` works.
globals().update({name: getattr(_pyrakit, name) for name in _pyrakit.__all__})

__all__ = list(_pyrakit.__all__)
__version__ = _pyrakit.__version__
__path__ = list(_pyrakit.__path__)


def __getattr__(name: str) -> object:
    """Forward anything else, including submodules, to ``pyrakit``."""
    return getattr(_pyrakit, name)
