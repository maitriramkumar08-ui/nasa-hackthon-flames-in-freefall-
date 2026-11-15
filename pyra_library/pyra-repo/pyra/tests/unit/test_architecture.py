"""Import-boundary tests for the dependency direction in architecture sections 4 and 19.

* Lower layers never import higher layers (core never imports adapters, report, service, cli).
* Nothing in `pyra` imports `pyra_edu`.
* `pyra_edu` may import only `pyra.service` from `pyra`.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"

LAYERS = {
    "units": 0, "schema": 0, "provenance": 0,
    "io": 1, "normalize": 1, "derive": 1, "conditions": 1, "catalog": 1, "physics": 1,
    "simulation": 1,
    "matching": 2, "coverage": 2, "compare": 2, "uq": 2, "sensitivity": 2,
    "surrogate": 2, "cluster": 2, "recommend": 2,
    "adapters": 3, "report": 3, "viz": 3, "service": 3, "cli": 3,
}


def _module_name(path: Path) -> tuple[str, str]:
    """Return (dotted module name, containing package) for a file under src."""
    parts = list(path.relative_to(SRC).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
        return ".".join(parts), ".".join(parts)
    return ".".join(parts), ".".join(parts[:-1])


def _imports(path: Path) -> set[str]:
    _, package = _module_name(path)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                pkg_parts = package.split(".")
                base = pkg_parts[: len(pkg_parts) - (node.level - 1)]
                target = ".".join(base + ([node.module] if node.module else []))
            else:
                target = node.module or ""
            found.add(target)
            found.update(f"{target}.{alias.name}" for alias in node.names)
    return found


def _files(package: str) -> list[Path]:
    return sorted((SRC / package).rglob("*.py"))


def _subpackage(module: str) -> str | None:
    parts = module.split(".")
    return parts[1] if len(parts) > 1 and parts[0] == "pyra" else None


def test_every_subpackage_has_a_layer() -> None:
    present = {
        p.name if p.is_dir() else p.stem
        for p in (SRC / "pyra").iterdir()
        if (p.is_dir() and (p / "__init__.py").exists())
        or (p.suffix == ".py" and p.stem not in {"__init__"})
    }
    assert present <= set(LAYERS), f"modules without a layer: {sorted(present - set(LAYERS))}"


def test_lower_layers_do_not_import_higher_layers() -> None:
    violations = []
    for path in _files("pyra"):
        module, _ = _module_name(path)
        mine = _subpackage(module)
        if mine is None:
            continue
        for target in _imports(path):
            theirs = _subpackage(target)
            if theirs in LAYERS and LAYERS[theirs] > LAYERS[mine]:
                violations.append(f"{module} imports {target}")
    assert not violations, violations


def test_core_never_imports_education_package() -> None:
    violations = []
    for path in _files("pyra"):
        module, _ = _module_name(path)
        for target in _imports(path):
            if target == "pyra_edu" or target.startswith("pyra_edu."):
                violations.append(f"{module} imports {target}")
    assert not violations, violations


def test_education_package_uses_only_the_service_layer() -> None:
    violations = []
    for path in _files("pyra_edu"):
        module, _ = _module_name(path)
        for target in _imports(path):
            if (
                (target == "pyra" or target.startswith("pyra."))
                and target != "pyra"
                and not target.startswith("pyra.service")
            ):
                violations.append(f"{module} imports {target}")
    assert not violations, violations
