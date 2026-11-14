"""P1 property tests (need hypothesis; skipped where it is not installed)."""

import random

import pytest

pytest.importorskip("hypothesis")
from hypothesis import given  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from pyra.provenance.hashing import sha256_hex  # noqa: E402
from pyra.provenance.status import Status, join  # noqa: E402

json_like = st.recursive(
    st.none() | st.booleans() | st.integers(-10**9, 10**9)
    | st.floats(allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6)
    | st.text(max_size=8),
    lambda children: st.lists(children, max_size=4)
    | st.dictionaries(st.text(min_size=1, max_size=5), children, max_size=4),
    max_leaves=12,
)


def shuffled(obj: object, rng: random.Random) -> object:
    if isinstance(obj, dict):
        items = [(k, shuffled(v, rng)) for k, v in obj.items()]
        rng.shuffle(items)
        return dict(items)
    if isinstance(obj, list):
        return [shuffled(v, rng) for v in obj]
    return obj


@given(json_like, st.integers(0, 10**6))
def test_hash_ignores_dict_insertion_order(obj: object, seed: int) -> None:
    assert sha256_hex(obj) == sha256_hex(shuffled(obj, random.Random(seed)))


@given(st.lists(st.sampled_from(list(Status)), min_size=1, max_size=8))
def test_join_is_the_maximum(statuses: list[Status]) -> None:
    assert join(*statuses) == max(statuses)
    assert join(*statuses) >= min(statuses)
