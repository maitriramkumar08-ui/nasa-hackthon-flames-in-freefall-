"""P0: the package imports and exposes a version."""

import pyrakit


def test_version_is_a_string() -> None:
    assert isinstance(pyrakit.__version__, str)
    assert pyrakit.__version__.count(".") == 2


def test_beginner_import_surface_exposes_short_functions() -> None:
    assert pyrakit.heat_release is pyrakit.heat_release
    assert pyrakit.playground is pyrakit.fire_playground
    # `compare` stays the advanced subpackage; the quick helper keeps its full name.
    import pyrakit.compare as compare_module
    assert pyrakit.compare is compare_module
    assert callable(pyrakit.compare_values)
    # `advanced` was the old escape hatch from the beginner facade to the full API.
    # pyrakit is both, so the alias only needs to survive on the legacy name.
    import pyra_library
    assert pyra_library.advanced is pyrakit
