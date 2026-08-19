"""Tests for the GenerationHistory class and related functions."""

from pydexpi.syndata.generation_history import (
    GenerationHistory,
    load_generation_history_from_json,
    save_generation_history_as_json,
)
from pydexpi.syndata.generator_step import GeneratorStepDict


class MockStep:
    """Mock class to simulate a generator step."""

    def __init__(
        self,
        step_type: str,
        own_connector: str = None,
        next_pattern: str = None,
        next_connector: str = None,
        sampled_distribution_name: str = None,
    ):
        """Initialize the mock step."""
        self.step_type = step_type
        self.own_connector = own_connector
        self.next_pattern = next_pattern
        self.next_connector = next_connector
        self.sampled_distribution_name = sampled_distribution_name

    def to_dict(self) -> GeneratorStepDict:
        """Convert the mock step to a dictionary."""
        return {
            "generator_step_type": self.step_type,
            "own_connector": self.own_connector,
            "next_pattern": self.next_pattern,
            "next_connector": self.next_connector,
            "sampled_distribution_name": self.sampled_distribution_name,
        }


def test_generation_history_init():
    """Test that GenerationHistory initializes correctly."""
    history = GenerationHistory()
    assert isinstance(history.history, list)
    assert len(history.history) == 0


def test_write_step():
    """Test writing steps to the history."""
    history = GenerationHistory()

    # Create and add some test steps
    step1 = MockStep("initialization", next_pattern="Pattern1", sampled_distribution_name="dist1")
    step2 = MockStep(
        "add_pattern",
        own_connector="conn1",
        next_pattern="Pattern2",
        next_connector="conn2",
        sampled_distribution_name="dist2",
    )

    history.write_step(step1)
    history.write_step(step2)

    # Check the history contains the expected steps
    assert len(history.history) == 2
    assert history.history[0]["generator_step_type"] == "initialization"
    assert history.history[0]["next_pattern"] == "Pattern1"
    assert history.history[1]["generator_step_type"] == "add_pattern"
    assert history.history[1]["own_connector"] == "conn1"


def test_save_load_generation_history(tmp_path):
    """Test saving and loading generation history."""
    history = GenerationHistory()

    # Create and add some test steps
    step1 = MockStep("initialization", next_pattern="Pattern1", sampled_distribution_name="dist1")
    step2 = MockStep(
        "add_pattern",
        own_connector="conn1",
        next_pattern="Pattern2",
        next_connector="conn2",
        sampled_distribution_name="dist2",
    )

    history.write_step(step1)
    history.write_step(step2)

    # Save the history to a temporary file
    json_path = tmp_path / "test_history.json"
    save_generation_history_as_json(history, json_path)

    # Load the history from the file
    loaded_history = load_generation_history_from_json(json_path)

    # Check that the loaded history matches the original
    assert len(loaded_history) == 2
    assert loaded_history[0]["generator_step_type"] == "initialization"
    assert loaded_history[0]["next_pattern"] == "Pattern1"
    assert loaded_history[1]["generator_step_type"] == "add_pattern"
    assert loaded_history[1]["own_connector"] == "conn1"
    assert loaded_history[1]["next_connector"] == "conn2"
