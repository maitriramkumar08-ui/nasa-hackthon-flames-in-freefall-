"""Unit conversion. Plain code, never the assistant (rule 8).

Every unit has: the kind of quantity it measures, and how to turn it into
that quantity's standard unit:  standard = value * factor + offset

We never overwrite the original value (rule 4). The loader stores the
original value and unit, and the converted ones go in separate columns.
"""

# The standard unit each kind of quantity is converted to
STANDARD = {
    "pressure": "kPa",
    "speed": "cm/s",
    "length": "mm",
    "time": "s",
    "temperature": "K",
    "o2": "%",
    "gravity": "g",
}

PSI_IN_KPA = 6.894757293168   # exact by definition of psi
ATM_IN_KPA = 101.325          # exact by definition of atm

#  unit (lower case) : (kind,        factor,      offset)
UNITS = {
    "kpa":   ("pressure",    1.0,         0.0),
    "pa":    ("pressure",    0.001,       0.0),
    "psi":   ("pressure",    PSI_IN_KPA,  0.0),
    "psia":  ("pressure",    PSI_IN_KPA,  0.0),
    "atm":   ("pressure",    ATM_IN_KPA,  0.0),
    "cm/s":  ("speed",       1.0,         0.0),
    "m/s":   ("speed",       100.0,       0.0),
    "mm/s":  ("speed",       0.1,         0.0),
    "mm":    ("length",      1.0,         0.0),
    "cm":    ("length",      10.0,        0.0),
    "m":     ("length",      1000.0,      0.0),
    "ms":    ("time",        0.001,       0.0),
    "s":     ("time",        1.0,         0.0),
    "k":     ("temperature", 1.0,         0.0),
    "c":     ("temperature", 1.0,         273.15),
    "°c":    ("temperature", 1.0,         273.15),
    "degc":  ("temperature", 1.0,         273.15),
    "%":     ("o2",          1.0,         0.0),
    "g":     ("gravity",     1.0,         0.0),
}


def lookup(unit):
    """Return (kind, factor, offset) for a unit, or None if we don't know it."""
    if not isinstance(unit, str):
        return None
    return UNITS.get(unit.strip().lower())


def kind_of(unit):
    found = lookup(unit)
    return found[0] if found else None


def convert(value, from_unit, to_unit):
    """convert(10.2, "psi", "kPa") -> 70.33. Raises ValueError on bad units."""
    source, target = lookup(from_unit), lookup(to_unit)
    if source is None or target is None:
        raise ValueError(f"unknown unit: {from_unit if source is None else to_unit}")
    if source[0] != target[0]:
        raise ValueError(f"can't convert {source[0]} ({from_unit}) to {target[0]} ({to_unit})")

    _, factor, offset = source
    standard = value * factor + offset
    _, factor, offset = target
    return round((standard - offset) / factor, 6)   # round away float noise


def to_number(value):
    """10, 10.5 and "10.5" become numbers. Text like "microgravity" gives None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def normalize(value, unit, expected_kind):
    """Turn one reported value into the standard unit for its kind.

    Returns (normalized_value, normalized_unit, conversion_method).
    When it can't convert, the value is None and the method says why.
    It never guesses.
    """
    if value is None:
        return None, None, "missing"

    number = to_number(value)
    if number is None:
        return None, None, "not a number, kept as text only"

    kind = kind_of(unit)
    if kind is None:
        return None, None, f"unit {unit!r} not recognised"
    if kind != expected_kind:
        return None, None, f"unit {unit!r} is {kind}, expected {expected_kind}"

    standard = STANDARD[kind]
    method = "unchanged" if unit.strip().lower() == standard.lower() else f"{unit} -> {standard}"
    return convert(number, unit, standard), standard, method
