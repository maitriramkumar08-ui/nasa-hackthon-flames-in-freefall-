from pyra_edu import check_lesson, decay_activity, make_decay_trace, status_badge


def test_concept_activity_is_labelled_and_has_a_trace() -> None:
    activity = decay_activity(steps=3)
    assert "NOT A FIRE MODEL" in activity["label"]
    assert len(activity["trace"]) == 3
    assert len(make_decay_trace(steps=4)) == 4


def test_lesson_check_requires_source_or_concept_label() -> None:
    assert not check_lesson(title="A claim").ok
    assert check_lesson(title="A source-backed lesson", evidence_ids=("PSI-25",)).ok
    assert check_lesson(title="A toy", concept_sketch=True).ok


def test_status_badge_uses_plain_language() -> None:
    assert status_badge("SIMULATED") == "SIMULATED: Simulation output"
