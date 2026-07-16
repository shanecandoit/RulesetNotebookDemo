"""Tests for rewrite events, evaluation results, stop reasons, and errors."""

from ruleset_notebook.domain import (
    DivisionByZeroError,
    EngineError,
    EvaluationResult,
    InvalidOperandError,
    RewriteEvent,
    StopReason,
    UnboundVariableError,
)
from ruleset_notebook.domain.terms import Application, Literal, Var


def test_stop_reason_values():
    assert StopReason.NORMAL_FORM.value == "normal form"
    assert StopReason.STEP_LIMIT.value == "step limit"
    assert StopReason.DEPTH_LIMIT.value == "depth limit"
    assert StopReason.CANCELLED.value == "cancelled"
    assert StopReason.RUNTIME_ERROR.value == "runtime error"


def test_rewrite_event_fields_and_repr():
    event = RewriteEvent(
        index=1,
        before=Application("add", (Literal(1), Literal(2))),
        after=Literal(3),
        rule_name="add-step",
        rule_id="abc",
        position=(0,),
        bindings={"x": Literal(1)},
    )
    assert event.index == 1
    assert event.rule_name == "add-step"
    assert event.position == (0,)
    assert event.bindings["x"] == Literal(1)
    assert "add-step" in repr(event)


def test_evaluation_result_defaults_and_step_count():
    result = EvaluationResult(
        input_term=Var("x"),
        output_term=Literal(5),
        events=(),
        stop_reason=StopReason.NORMAL_FORM,
    )
    assert result.step_count() == 0
    assert result.error is None
    assert result.stop_reason is StopReason.NORMAL_FORM


def test_evaluation_result_counts_events():
    events = (
        RewriteEvent(1, Var("x"), Literal(1), "r1", "id1", (), {}),
        RewriteEvent(2, Literal(1), Literal(2), "r2", "id2", (), {}),
    )
    result = EvaluationResult(
        input_term=Var("x"),
        output_term=Literal(2),
        events=events,
        stop_reason=StopReason.STEP_LIMIT,
    )
    assert result.step_count() == 2


def test_engine_error_carries_message_and_code():
    error = EngineError("boom")
    assert error.message == "boom"
    assert error.code == "engine-error"
    assert "boom" in repr(error)


def test_specific_engine_errors_subclass_and_codes():
    assert issubclass(DivisionByZeroError, EngineError)
    assert issubclass(InvalidOperandError, EngineError)
    assert issubclass(UnboundVariableError, EngineError)
    assert DivisionByZeroError("x").code == "division-by-zero"
    assert InvalidOperandError("x").code == "invalid-operand"
    assert UnboundVariableError("x").code == "unbound-variable"
