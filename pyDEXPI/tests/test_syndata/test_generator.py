"""Tests a simple, dummy generator setup with dummy patterns and a
RandomGeneratorFunction."""

import random

import pytest

from pydexpi.syndata.generation_history import GenerationHistory
from pydexpi.syndata.generator import SyntheticPIDGenerator
from pydexpi.syndata.generator_function import CappingFunction, RandomGeneratorFunction
from pydexpi.syndata.pattern import Pattern


@pytest.fixture
def test_generator_factory(simple_distribution_factory):
    """Fixture to create a test generator."""

    def make_a_test_generator(with_capping: bool = False, random_seed: int | None = 42):
        """Create a test generator.

        Parameters
        ----------
        with_capping : bool, optional
            Whether to include a capping function, by default False
        random_seed : int, optional
            Seed for random number generation, by default 42
        """
        # Set random seed if provided for reproducible tests
        if random_seed is not None:
            random.seed(random_seed)

        distributions = {name: simple_distribution_factory(name) for name in ["Distr1", "Distr2"]}
        the_function = RandomGeneratorFunction(distributions)
        capping_function = CappingFunction() if with_capping else None
        the_generator = SyntheticPIDGenerator(
            the_function, capping_function=capping_function, max_steps=5
        )
        return the_generator

    return make_a_test_generator


def test_generator_constructor(test_generator_factory):
    """Test creating a generator."""
    generator = test_generator_factory(with_capping=False)
    assert isinstance(generator, SyntheticPIDGenerator)


def test_generate_pattern(test_generator_factory):
    """Test generating a pattern with the synthetic PID generator"""
    generator = test_generator_factory(with_capping=False)
    pattern = generator.generate_pattern("New label")
    assert isinstance(pattern, Pattern)
    assert generator._current_step > 0
    assert pattern.label == "New label"


def test_reset(test_generator_factory):
    """Test resetting the generator."""
    generator = test_generator_factory(with_capping=False)
    _ = generator.generate_pattern("New label")
    generator.reset()
    assert generator._current_step == 0


def test_generate_pattern_with_capping(test_generator_factory):
    """Test generating a pattern with capping enabled."""
    generator = test_generator_factory(with_capping=True)
    assert generator.capping_function is not None

    pattern = generator.generate_pattern("Capped Pattern")
    assert isinstance(pattern, Pattern)

    # Capping removes all connectors
    assert len(pattern.connectors) == 0


def test_generation_history_initialization(test_generator_factory):
    """Test that the generation history is properly initialized."""
    generator = test_generator_factory(with_capping=False)
    history = generator.get_generation_history()

    assert isinstance(history, GenerationHistory)
    assert len(history.history) == 0


def test_generation_history_recording(test_generator_factory):
    """Test that steps are recorded in the generation history."""
    generator = test_generator_factory(with_capping=True)

    # Generate a pattern which should create history entries
    generator.generate_pattern("Test Pattern")

    # Get the history and verify it has entries
    history = generator.get_generation_history()
    assert len(history.history) > 0

    # The first step should be the initialization step
    first_step = history.history[0]
    assert "generator_step_type" in first_step.keys()
    assert first_step["generator_step_type"] == "initialization"

    # Last step should be a capping step
    last_step = history.history[-1]
    assert last_step["generator_step_type"] == "capping"


def test_generation_history_reset(test_generator_factory):
    """Test that the generation history is reset when the generator is reset."""
    generator = test_generator_factory(with_capping=False)

    # Generate a pattern to create history
    generator.generate_pattern("First Pattern")
    assert len(generator.get_generation_history().history) > 0

    # Reset the generator
    generator.reset()

    # History should be empty after reset
    assert len(generator.get_generation_history().history) == 0

    # Generate a new pattern and verify history is populated again
    generator.generate_pattern("Second Pattern")
    assert len(generator.get_generation_history().history) > 0
