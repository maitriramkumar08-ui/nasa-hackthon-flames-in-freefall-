"""P0: the package imports and exposes a version."""

import pyra
import pyra_library


def test_version_is_a_string() -> None:
    assert isinstance(pyra.__version__, str)
    assert pyra.__version__.count(".") == 2


def test_beginner_import_surface_exposes_short_functions() -> None:
    assert pyra_library.heat_release is pyra.heat_release
    assert pyra_library.playground is pyra.fire_playground
    assert pyra_library.compare is pyra.compare_values
    assert pyra_library.advanced is pyra
