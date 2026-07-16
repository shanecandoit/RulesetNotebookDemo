"""Tests for immutable Rule and validated EvaluationSettings."""

import uuid

import pytest

from ruleset_notebook.domain import EvaluationSettings, Rule
from ruleset_notebook.domain.terms import Application, Literal, Var


def test_rule_has_stable_uuid_by_default():
    rule = Rule("add-zero", Application("add", (Var("x"), Literal(0))), Var("x"))
    assert isinstance(rule.id, uuid.UUID)
    same = Rule("add-zero", Application("add", (Var("x"), Literal(0))), Var("x"))
    assert rule.id != same.id


def test_rule_explicit_id_is_preserved():
    fixed = uuid.uuid4()
    rule = Rule(
        "add-zero",
        Application("add", (Var("x"), Literal(0))),
        Var("x"),
        id=fixed,
    )
    assert rule.id == fixed


def test_rule_enabled_by_default():
    rule = Rule("r", Var("x"), Var("x"))
    assert rule.enabled is True


def test_rule_disabled_state():
    rule = Rule("r", Var("x"), Var("x"), enabled=False)
    assert rule.enabled is False


def test_rule_repr_shows_name_and_arrow():
    rule = Rule("add-zero", Application("add", (Var("x"), Literal(0))), Var("x"))
    text = repr(rule)
    assert "add-zero" in text
    assert "add(x, 0)" in text
    assert "=> x" in text


def test_rule_repr_marks_disabled():
    rule = Rule("r", Var("x"), Var("x"), enabled=False)
    assert "disabled" in repr(rule)


def test_settings_defaults():
    settings = EvaluationSettings()
    assert settings.max_steps == 100
    assert settings.max_depth == 1000


def test_settings_custom_values():
    settings = EvaluationSettings(max_steps=50, max_depth=10)
    assert settings.max_steps == 50
    assert settings.max_depth == 10


def test_settings_rejects_nonpositive_steps():
    with pytest.raises(ValueError, match="max_steps"):
        EvaluationSettings(max_steps=0)


def test_settings_rejects_nonpositive_depth():
    with pytest.raises(ValueError, match="max_depth"):
        EvaluationSettings(max_depth=-1)
