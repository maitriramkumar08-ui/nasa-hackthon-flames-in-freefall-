"""The claim gate must check the scenario against the envelope, not just its presence.

All conditions and evidence below are fictional test fixtures, not real datasets.
"""

from typing import Any

import pytest

from pyra.adapters import (
    ClaimGateError,
    EnvelopeGatePolicy,
    check_envelope,
    parse_envelope,
    require_in_envelope,
    require_validated,
)
from pyra.adapters.envelope import NumericLimit
from pyra.schema import Conditions, FuelSpec, Measure, ModelCard, Scenario, ValidationEvidence

EARTH_ENVELOPE: dict[str, Any] = {
    "gravity_g": [0.9, 1.1],
    "o2_mole_fraction": [0.18, 0.25],
    "pressure": {"min": 95, "max": 105, "unit": "kPa"},
}


def conditions(
    *,
    gravity_g: float = 1.0,
    o2: float = 0.21,
    pressure_kpa: float = 101.3,
    diluent: str = "nitrogen",
    material: str = "PMMA",
    temperature_k: float | None = None,
) -> Conditions:
    payload: dict[str, Any] = {
        "gravity_g": Measure(value=gravity_g, unit="dimensionless"),
        "pressure": Measure(value=pressure_kpa, unit="kPa"),
        "o2_mole_fraction": Measure(value=o2, unit="dimensionless"),
        "diluent": diluent,
        "flow_mode": "forced",
        "fuel": FuelSpec(material=material),
        "configuration": "concurrent",
        "length_scale": Measure(value=0.02, unit="m"),
    }
    if temperature_k is not None:
        payload["temperature"] = Measure(value=temperature_k, unit="K")
    return Conditions(**payload)


def scenario(scenario_id: str = "s", **kwargs: Any) -> Scenario:
    return Scenario(scenario_id=scenario_id, conditions=conditions(**kwargs))


def card(*envelopes: dict[str, Any], name: str = "toy") -> ModelCard:
    return ModelCard(
        name=name,
        version="1",
        code_hash="abc",
        licence="MIT",
        physics_summary="fictional test model",
        envelope=[
            ValidationEvidence(
                experiment_ids=[f"synthetic-{index}"],
                quantity="flame_length",
                metric="bias",
                result={"bias": 0.0},
                envelope=envelope,
            )
            for index, envelope in enumerate(envelopes)
        ],
    )


def test_earth_validated_card_does_not_cover_a_microgravity_scenario() -> None:
    """The gap this module closes: presence of evidence is not coverage of a scenario."""
    earth_card = card(EARTH_ENVELOPE)
    microgravity = scenario("saffire-like", gravity_g=1e-5)

    # The old presence-only gate accepts the claim.
    require_validated(earth_card)

    # The scenario-aware gate refuses it and says why.
    check = check_envelope(earth_card, microgravity)
    assert not check.inside
    assert [axis.axis for axis in check.evidence[0].outside] == ["gravity_g"]
    with pytest.raises(ClaimGateError, match="gravity_g is 1e-05"):
        require_in_envelope(earth_card, microgravity)


def test_scenario_inside_the_envelope_passes_and_reports_the_supporting_entry() -> None:
    earth_card = card(EARTH_ENVELOPE)
    check = require_in_envelope(earth_card, scenario(gravity_g=1.0, o2=0.21))
    assert check.inside
    assert len(check.covering) == 1
    assert check.covering[0].experiment_ids == ("synthetic-0",)
    assert "covers this scenario" in check.covering[0].reason()


def test_one_covering_entry_among_several_is_enough() -> None:
    multi = card(
        EARTH_ENVELOPE,
        {
            "gravity_g": [0.0, 1e-4],
            "o2_mole_fraction": [0.18, 0.25],
            "pressure": {"min": 95, "max": 105, "unit": "kPa"},
        },
    )
    check = require_in_envelope(multi, scenario(gravity_g=1e-5))
    assert check.inside
    assert [entry.experiment_ids for entry in check.covering] == [("synthetic-1",)]


def test_empty_envelope_dict_never_covers_a_scenario() -> None:
    """An evidence entry with no recorded limits must not reopen the loophole."""
    vague = card({})
    require_validated(vague)  # presence-only gate still passes
    check = check_envelope(vague, scenario())
    assert not check.inside
    assert "records no envelope limits" in check.reasons()[0]
    with pytest.raises(ClaimGateError):
        require_in_envelope(vague, scenario())


def test_card_with_no_evidence_is_refused_with_a_clear_reason() -> None:
    check = check_envelope(card(), scenario())
    assert not check.inside
    assert check.reasons() == ("the model card records no validation evidence at all",)


def test_partial_envelope_is_refused_until_required_axes_are_bounded() -> None:
    gravity_only = card({"gravity_g": [0.9, 1.1]})
    check = check_envelope(gravity_only, scenario())
    assert not check.inside
    assert check.evidence[0].missing_required_axes == ("o2_mole_fraction", "pressure")
    assert "does not bound the required axes" in check.reasons()[0]

    # A caller who has reason to accept a narrower declaration can say so explicitly.
    relaxed = EnvelopeGatePolicy(required_axes=("gravity_g",))
    assert check_envelope(gravity_only, scenario(), policy=relaxed).inside


def test_recorded_limits_are_unit_converted_before_comparison() -> None:
    """A limit written in kPa must compare correctly against a scenario held in Pa."""
    bar_card = card(
        {
            "gravity_g": [0.9, 1.1],
            "o2_mole_fraction": [0.18, 0.25],
            "pressure": {"min": 0.95, "max": 1.05, "unit": "bar"},
        }
    )
    assert check_envelope(bar_card, scenario(pressure_kpa=101.3)).inside
    assert not check_envelope(bar_card, scenario(pressure_kpa=50.0)).inside


def test_an_unset_optional_scenario_axis_is_not_treated_as_inside() -> None:
    temperature_card = card({**EARTH_ENVELOPE, "temperature": {"min": 280, "max": 320}})
    check = check_envelope(temperature_card, scenario(temperature_k=None))
    assert not check.inside
    assert "leaves it unset" in check.evidence[0].outside[0].reason
    assert check_envelope(temperature_card, scenario(temperature_k=295.0)).inside


def test_categorical_axes_compare_case_insensitively() -> None:
    diluent_card = card({**EARTH_ENVELOPE, "diluent": ["Nitrogen", "carbon dioxide"]})
    assert check_envelope(diluent_card, scenario(diluent="nitrogen")).inside
    outside = check_envelope(diluent_card, scenario(diluent="helium"))
    assert not outside.inside
    assert "not one of Nitrogen, carbon dioxide" in outside.evidence[0].outside[0].reason

    fuel_card = card({**EARTH_ENVELOPE, "fuel_material": "PMMA"})
    assert check_envelope(fuel_card, scenario(material="PMMA")).inside
    assert not check_envelope(fuel_card, scenario(material="cotton")).inside


def test_explain_names_the_verdict_and_refuses_to_imply_certification() -> None:
    text = check_envelope(card(EARTH_ENVELOPE), scenario(gravity_g=1e-5)).explain()
    assert "is OUTSIDE the recorded validation envelope" in text
    assert "not a safety certification" in text
    assert "toy 1" in text


@pytest.mark.parametrize(
    "envelope",
    [
        {"grvaity_g": [0, 1]},  # a typo must not silently widen the envelope
        {"gravity_g": [1, 0]},  # min above max
        {"gravity_g": [0]},  # not a pair
        {"gravity_g": "wide"},  # not a range
        {"gravity_g": {}},  # neither min nor max
        {"gravity_g": {"min": 0, "limit": 1}},  # unknown key
        {"gravity_g": {"min": "low"}},  # non-numeric
        {"gravity_g": [True, False]},  # booleans are not measurements
        {"diluent": []},  # no allowed value
        {"diluent": [""]},  # blank allowed value
    ],
)
def test_malformed_envelope_fails_loudly(envelope: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        parse_envelope(envelope)


def test_parse_envelope_resolves_one_sided_and_unit_bearing_limits() -> None:
    limits = parse_envelope({"pressure": {"max": 101.325, "unit": "kPa"}})
    assert limits == (
        NumericLimit(axis="pressure", low=-float("inf"), high=101325.0, unit="pascal"),
    )
    assert limits[0].describe() == "-inf to 101325 pascal"


def test_policy_rejects_an_unknown_required_axis() -> None:
    with pytest.raises(ValueError, match="unknown envelope axes"):
        EnvelopeGatePolicy(required_axes=("gravity",))
