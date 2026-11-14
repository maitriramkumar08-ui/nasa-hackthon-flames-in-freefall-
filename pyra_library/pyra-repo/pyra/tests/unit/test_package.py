"""P0: the package imports and exposes a version."""

import pyra


def test_version_is_a_string() -> None:
    assert isinstance(pyra.__version__, str)
    assert pyra.__version__.count(".") == 2
