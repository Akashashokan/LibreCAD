"""Tests for the GenerationStep classes."""

import pytest

from pydexpi.syndata.connector_renaming import ConnectorRenamingConvention
from pydexpi.syndata.generator_step import (
    AddPatternStep,
    CappingStep,
    InitializationStep,
    InternalConnectionStep,
    TerminationStep,
)
from tests.test_syndata.test_pattern import DummyConnector, DummyPattern


def test_add_pattern_step_to_dict():
    """Test that AddPatternStep.to_dict returns correct dictionary representation."""
    own = DummyConnector("own")
    next_conn = DummyConnector("next")
    next_pat = DummyPattern("pattern", connectors=[next_conn])

    step = AddPatternStep(own, next_pat, next_conn, "sampled")

    d = step.to_dict()
    assert d["generator_step_type"] == "add_pattern"
    assert d["own_connector"] == "own"
    assert d["next_pattern"] == "pattern"
    assert d["next_connector"] == "next"
    assert d["sampled_distribution_name"] == "sampled"


def test_add_pattern_step_execute():
    """Test that executing AddPatternStep incorporates the next pattern."""
    own = DummyConnector("own")
    next_conn = DummyConnector("next")
    next_pat = DummyPattern("pattern", connectors=[next_conn])
    current_pat = DummyPattern("current", connectors=[own])

    # Test with an invalid own connector
    invalid_own = DummyConnector("invalid")
    step = AddPatternStep(invalid_own, next_pat, next_conn, "sampled")
    with pytest.raises(RuntimeError, match="is not associated"):
        step.execute_on(current_pat)

    # Test with a valid own connector
    step = AddPatternStep(own, next_pat, next_conn, "sampled")

    step.execute_on(current_pat)
    assert next_pat.is_incorporated is True


def test_add_pattern_step_invalid_own_connector():
    """Test that executing AddPatternStep with an invalid own_connector raises RuntimeError."""
    own = DummyConnector("own")
    next_conn = DummyConnector("next")
    next_pat = DummyPattern("pattern", connectors=[next_conn])
    current_pat = DummyPattern("current", connectors=[own])

    # Test with an invalid own connector
    invalid_own = DummyConnector("invalid")
    step = AddPatternStep(invalid_own, next_pat, next_conn, "sampled")
    with pytest.raises(RuntimeError, match="is not associated"):
        step.execute_on(current_pat)


def test_add_pattern_step_invalid_next_connector():
    """Test that initializing AddPatternStep with an invalid next_connector raises ValueError."""
    own = DummyConnector("own")
    next_conn = DummyConnector("next")
    next_pat = DummyPattern("pattern", connectors=[])  # Empty connectors list to trigger error
    with pytest.raises(ValueError, match="The connector"):
        AddPatternStep(own, next_pat, next_conn, "sampled")


def test_add_pattern_step_termination_status():
    """Test that AddPatternStep returns termination status False."""
    own = DummyConnector("own")
    next_conn = DummyConnector("next")
    next_pat = DummyPattern("pattern", connectors=[next_conn])

    step = AddPatternStep(own, next_pat, next_conn, "sampled")
    assert step.get_termination_status() is False


def test_add_pattern_step_apply_renaming_convention():
    """Test that AddPatternStep applies the renaming convention."""
    own = DummyConnector("own")
    next_conn = DummyConnector("next")
    other_conn = DummyConnector("other")
    next_pat = DummyPattern("pattern", connectors=[next_conn, other_conn])

    step = AddPatternStep(own, next_pat, next_conn, "sampled")
    renaming_convention = ConnectorRenamingConvention()
    step.apply_renaming_convention(renaming_convention=renaming_convention)

    # Own and next stay the same, other gets renamed
    assert own.label == "own"
    assert next_conn.label == "next"
    assert other_conn.label == "pattern_0_other"


def test_interal_connection_step_with_same_connectors_raises_value_error():
    """Test that initializing InternalConnectionStep with the same connector raises ValueError."""
    own = DummyConnector("own")

    with pytest.raises(ValueError, match="The connector"):
        InternalConnectionStep(own, own)


def test_internal_connection_step_to_dict():
    """Test that InternalConnectionStep.to_dict returns correct dictionary representation."""
    own = DummyConnector("own")
    next_conn = DummyConnector("next")

    step = InternalConnectionStep(own, next_conn)

    d = step.to_dict()
    assert d["generator_step_type"] == "internal_connection"
    assert d["own_connector"] == "own"
    assert d["next_connector"] == "next"
    assert d["next_pattern"] is None
    assert d["sampled_distribution_name"] is None


def test_internal_connection_step_execute():
    """Test that executing InternalConnectionStep deactivates the own connector."""
    own = DummyConnector("own")
    next_conn = DummyConnector("next")
    current_pat = DummyPattern("current", connectors=[own, next_conn])

    # Test with a valid own connector
    step = InternalConnectionStep(own, next_conn)

    step.execute_on(current_pat)
    assert own.is_active is False


def test_internal_connection_step_execute_runtime_error():
    """Test that executing InternalConnectionStep with a missing next_connector raises RuntimeError."""
    own = DummyConnector("own")
    next_conn = DummyConnector("next")
    current_pat = DummyPattern("current", connectors=[own, next_conn])

    invalid_conn = DummyConnector("invalid")

    step = InternalConnectionStep(own, invalid_conn)
    with pytest.raises(RuntimeError, match="is not associated"):
        step.execute_on(current_pat)

    step = InternalConnectionStep(invalid_conn, next_conn)
    with pytest.raises(RuntimeError, match="is not associated"):
        step.execute_on(current_pat)


def test_internal_connection_step_termination_status():
    """Test that InternalConnectionStep returns termination status False."""
    own = DummyConnector("own")
    next_conn = DummyConnector("next")

    step = InternalConnectionStep(own, next_conn)
    assert step.get_termination_status() is False


def test_termination_step():
    """Test that TerminationStep returns termination status and leaves connectors unchanged."""
    dummy_pat = DummyPattern("dummy", connectors=[DummyConnector("dummy")])
    step = TerminationStep()
    step.execute_on(dummy_pat)
    d = step.to_dict()
    assert d["generator_step_type"] == "termination"
    assert d["own_connector"] is None
    assert d["next_connector"] is None
    assert d["next_pattern"] is None
    assert d["sampled_distribution_name"] is None
    assert step.get_termination_status() is True


def test_initialization_step():
    """Test that InitializationStep returns a proper dictionary and pattern."""
    pat = DummyPattern("init", connectors=[DummyConnector("init")])
    step = InitializationStep(pat, "sampled")
    d = step.to_dict()
    assert d["generator_step_type"] == "initialization"
    assert d["next_pattern"] == "init"
    assert d["sampled_distribution_name"] == "sampled"
    assert step.get_pattern() == pat


def test_capping_step_to_dict():
    """Test that CappingStep.to_dict returns correct dictionary representation."""
    own = DummyConnector("own")
    next_conn = DummyConnector("next")
    next_pat = DummyPattern("pattern_cap", connectors=[next_conn])

    step = CappingStep(own, next_pat, next_conn, "cap_sample")
    d = step.to_dict()
    assert d["generator_step_type"] == "capping"
    assert d["own_connector"] == "own"
    assert d["next_pattern"] == "pattern_cap"
    assert d["next_connector"] == "next"
    assert d["sampled_distribution_name"] == "cap_sample"


def test_capping_step_execute_with_next_pattern():
    """Test that CappingStep.execute_on incorporates the next pattern."""
    own = DummyConnector("own")
    next_conn = DummyConnector("next")
    next_pat = DummyPattern("pattern_cap", connectors=[next_conn])
    current_pat = DummyPattern("current_cap", connectors=[own])

    step = CappingStep(own, next_pat, next_conn, "cap_sample")
    step.execute_on(current_pat)

    assert next_pat.is_incorporated is True
    assert next_conn.is_active is False
    assert own.is_active is False


def test_capping_step_execute_drop_connector():
    """Test that CappingStep.execute_on drops the connector when next_pattern is None."""
    own = DummyConnector("own")
    current_pat = DummyPattern("current_drop", connectors=[own])
    step = CappingStep(own, None, None, None)
    step.execute_on(current_pat)

    # Verify that the connector is dropped and removed from the pattern
    assert own.is_active is False
    assert current_pat.connectors == {}


def test_capping_step_invalid_connector_and_multiple_connectors():
    """Test that initializing CappingStep with an invalid next_connector or multiple connectors raises ValueError."""
    own = DummyConnector("own")
    invalid_conn = DummyConnector("invalid")
    # Create a pattern with an empty connectors list to trigger invalid connector error
    next_pat_invalid = DummyPattern("pattern_invalid", connectors=[])

    with pytest.raises(ValueError, match="The connector"):
        CappingStep(own, next_pat_invalid, invalid_conn, "cap_sample")

    # Create a pattern with multiple connectors
    conn1 = DummyConnector("conn1")
    conn2 = DummyConnector("conn2")
    next_pat_multi = DummyPattern("pattern_multi", connectors=[conn1, conn2])
    with pytest.raises(ValueError, match="has more than one connector"):
        CappingStep(own, next_pat_multi, conn1, "cap_sample")
