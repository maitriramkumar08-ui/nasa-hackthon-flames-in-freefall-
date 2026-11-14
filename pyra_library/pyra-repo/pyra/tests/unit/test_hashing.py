"""P1: canonical hashing is stable and refuses what it cannot canonicalize."""

import hashlib
import math
import os
import subprocess
import sys
import unicodedata
from pathlib import Path

import pytest

from pyra.provenance.hashing import canonical_bytes, sha256_hex
from pyra.provenance.status import Status

SRC = str(Path(__file__).resolve().parents[2] / "src")


def test_known_bytes_and_independent_digest() -> None:
    assert canonical_bytes({"b": [1, 2.5], "a": None}) == b'{"a":null,"b":[1,2.5]}'
    assert sha256_hex({"a": 1}) == hashlib.sha256(b'{"a":1}').hexdigest()


def test_key_order_does_not_matter() -> None:
    one = {"a": 1, "b": {"x": 1, "y": 2}}
    two = {"b": {"y": 2, "x": 1}, "a": 1}
    assert sha256_hex(one) == sha256_hex(two)


def test_float_rounding_noise_is_normalized() -> None:
    assert sha256_hex(0.1 + 0.2) == sha256_hex(0.3)
    assert sha256_hex(0.3) != sha256_hex(0.31)


def test_negative_zero_equals_zero() -> None:
    assert sha256_hex(-0.0) == sha256_hex(0.0)


def test_int_and_float_are_distinct() -> None:
    assert sha256_hex(1) != sha256_hex(1.0)


def test_nan_and_infinities_are_stable_and_distinct() -> None:
    digests = {sha256_hex(x) for x in (math.nan, math.inf, -math.inf)}
    assert len(digests) == 3
    assert sha256_hex(math.nan) == sha256_hex(float("nan"))


def test_tuple_equals_list() -> None:
    assert sha256_hex((1, 2, 3)) == sha256_hex([1, 2, 3])


def test_unicode_normalization() -> None:
    composed = unicodedata.normalize("NFC", "\u00e9")
    decomposed = unicodedata.normalize("NFD", "\u00e9")
    assert composed != decomposed
    assert sha256_hex(composed) == sha256_hex(decomposed)


def test_status_hashes_as_its_integer_value() -> None:
    assert sha256_hex(Status.DERIVED) == sha256_hex(1)


def test_refuses_what_it_cannot_canonicalize() -> None:
    with pytest.raises(TypeError):
        sha256_hex({1: "non-string key"})
    with pytest.raises(TypeError):
        sha256_hex({"s": {1, 2}})
    with pytest.raises(TypeError):
        sha256_hex(object())


def test_numpy_arrays_and_scalars() -> None:
    np = pytest.importorskip("numpy")
    arr = np.array([1.0, 2.0, 3.0])
    assert sha256_hex(arr) == sha256_hex(np.array([1.0, 2.0, 3.0]))
    assert sha256_hex(arr) != sha256_hex([1.0, 2.0, 3.0])          # an array is not a list
    assert sha256_hex(arr) != sha256_hex(arr.astype("float32"))     # dtype is part of identity
    assert sha256_hex(np.float64(0.5)) == sha256_hex(0.5)
    assert sha256_hex(np.int64(7)) == sha256_hex(7)


def test_hash_is_stable_across_processes_and_hash_seeds() -> None:
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]);"
        "from pyra.provenance.hashing import sha256_hex;"
        "print(sha256_hex({'k%d' % i: [i, i / 7, 'v%d' % i] for i in range(20)}))"
    )
    outs = set()
    for seed in ("0", "1", "12345"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        res = subprocess.run(
            [sys.executable, "-c", code, SRC], capture_output=True, text=True, env=env, check=True
        )
        outs.add(res.stdout.strip())
    assert len(outs) == 1
