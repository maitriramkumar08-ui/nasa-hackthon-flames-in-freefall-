"""Compatibility alias: ``pyra_library`` is the former beginner import name.

The whole toolkit now lives under one name, so the friendly surface and the full API
are the same import:

    import pyrakit as pk

``import pyra_library as pk`` keeps working and exposes the same names. New code should
import ``pyrakit``.
"""

from __future__ import annotations

import pyrakit as _pyrakit
from pyrakit import *  # noqa: F403  (re-export the public surface under the old name)

advanced = _pyrakit
__all__ = [*_pyrakit.__all__, "advanced"]
__version__ = _pyrakit.__version__


def __getattr__(name: str) -> object:
    return getattr(_pyrakit, name)
