"""Canonical hashing (architecture sections 5 and 11).

``sha256_hex(obj)`` hashes a canonical JSON encoding: sorted keys, no whitespace, ASCII only,
floats rounded to 12 significant digits, NFC-normalized strings. The result does not depend on
dict insertion order, PYTHONHASHSEED, platform or process.

Anything that cannot be canonicalized raises ``TypeError``; there is no silent ``str()`` fallback.
The 12-digit float rule is a design choice recorded in docs/adr/0001.

TODO(verify): xarray DataArray/Dataset are refused until their canonical form (coordinates,
attrs, dims) is designed against the real xarray API at prompts P3/P4.
"""

from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from collections.abc import Mapping
from enum import Enum
from typing import Any

FLOAT_SIGNIFICANT_DIGITS = 12


def _norm_str(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def _norm_float(x: float) -> Any:
    if math.isnan(x):
        return {"__float__": "nan"}
    if math.isinf(x):
        return {"__float__": "inf" if x > 0 else "-inf"}
    y = float(format(x, f".{FLOAT_SIGNIFICANT_DIGITS}g"))
    return 0.0 if y == 0.0 else y   # folds -0.0 into 0.0


def canonicalize(obj: Any) -> Any:
    """Return a JSON-serializable structure with a unique representation for ``obj``."""
    if isinstance(obj, Enum):
        return canonicalize(obj.value)
    if obj is None or isinstance(obj, bool):
        return obj
    if isinstance(obj, int):
        return int(obj)
    if isinstance(obj, float):
        return _norm_float(float(obj))
    if isinstance(obj, str):
        return _norm_str(str(obj))
    if isinstance(obj, bytes):
        return {"__bytes__": obj.hex()}
    if isinstance(obj, Mapping):
        out: dict[str, Any] = {}
        for key, value in obj.items():
            if not isinstance(key, str):
                raise TypeError(f"canonical hashing needs str keys, got {type(key).__name__}")
            nkey = _norm_str(key)
            if nkey in out:
                raise TypeError(f"keys collide after Unicode normalization: {key!r}")
            out[nkey] = canonicalize(value)
        return out
    if isinstance(obj, (list, tuple)):
        return [canonicalize(v) for v in obj]
    # numpy arrays and scalars, detected by duck typing so numpy stays an optional import here.
    if hasattr(obj, "dtype") and hasattr(obj, "shape") and hasattr(obj, "tolist"):
        data = canonicalize(obj.tolist())
        if tuple(obj.shape) == ():
            return data
        return {"__ndarray__": {"dtype": str(obj.dtype), "shape": list(obj.shape), "data": data}}
    raise TypeError(f"cannot canonicalize object of type {type(obj).__name__}")


def canonical_bytes(obj: Any) -> bytes:
    """Canonical JSON bytes of ``obj`` (ASCII, sorted keys, compact separators)."""
    return json.dumps(
        canonicalize(obj),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def sha256_hex(obj: Any) -> str:
    """SHA-256 hex digest of the canonical bytes of ``obj``."""
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()
