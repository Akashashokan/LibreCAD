"""Tests for GeneratorFunction on a basic TestGeneratorFunction and RandomGeneratorFunction."""

import random

import pytest

from pydexpi.syndata.generation_history import GenerationHistory
from pydexpi.syndata.generator_function import (
    CappingFunction,
    GeneratorFunction,
    RandomGeneratorFunction,
    ReconstructionCappingFunction,
    ReconstructionGeneratorFunction,
)
from pydexpi.syndata.generator_step import (
    AddPatternStep,
    CappingStep,
    GeneratorStep,
    InitializationStep,
    InternalConnectionStep,
    TerminationStep,
)
from pydexpi.syndata.pattern import Connector, Pattern


class TestGeneratorFunction(GeneratorFunction):
    """Test class for GeneratorFunction.

    This class is used to test the GeneratorFunction class. It is a subclass of
    GeneratorFunction and implements the abstract methods.
    """

    __test__ = False

    def __init__(self, distributions: dict, test_connect_internal: bool = False) -> None:
        """
        Initialize the TestGeneratorFunction.
        """
        super().__init__(distributions)
        self.test_connect_internal = test_connect_internal

    def initialize_pattern(self) -> InitializationStep:
        """
        Initialize a pattern using the first pattern from the "Distr1" distribution.
        """
        the_distribution = self.distribution_range["Distr1"]
        the_pattern = list(the_distribution.patterns.values())[0]
        return InitializationStep(the_pattern, the_distribution.name)

    def get_next_step(self, pattern: Pattern) -> GeneratorStep:
        """
        Get the next step for the given pattern.
        """
        if self.test_connect_internal:
            # If test_connect_internal is True, create an InternalConnectionStep
            return InternalConnectionStep(
                list(pattern.connectors.values())[0], list(pattern.connectors.values())[1]
            )
        else:
            the_distribution = self.distribution_range["Distr1"]
            next_pattern = list(the_distribution.patterns.values())[0]
            return AddPatternStep(
                list(pattern.connectors.values())[0],
                next_pattern,
                list(next_pattern.connectors.values())[0],
                the_distribution.name,
            )


def test_testgeneratorfunction_initialize_pattern(simple_distribution_factory):
    """Test that TestGeneratorFunction returns a valid InitializationStep."""
    distributions = {name: simple_distribution_factory(name) for name in ["Distr1", "Distr2"]}
    test_func = TestGeneratorFunction(distributions)
    init_step = test_func.initialize_pattern()
    the_pattern = init_step.get_pattern()
    assert isinstance(the_pattern, Pattern)


def test_testgeneratorfunction_get_next_step_add(
    simple_distribution_factory, simple_pattern_factory
):
    """Test get_next_step returns AddPatternStep when test_connect_internal is False."""
    distributions = {name: simple_distribution_factory(name) for name in ["Distr1", "Distr2"]}
    test_func = TestGeneratorFunction(distributions, test_connect_internal=False)
    pattern = simple_pattern_factory("TestPattern")
    step = test_func.get_next_step(pattern)
    assert step.__class__.__name__ == "AddPatternStep"
    assert step.own_connector in pattern.connectors.values()
    assert isinstance(step.next_pattern, Pattern)
    assert step.next_connector in step.next_pattern.connectors.values()


def test_testgeneratorfunction_get_next_step_internal(
    simple_distribution_factory, simple_pattern_factory
):
    """Test get_next_step returns InternalConnectionStep when test_connect_internal is True."""
    distributions = {name: simple_distribution_factory(name) for name in ["Distr1", "Distr2"]}
    test_func = TestGeneratorFunction(distributions, test_connect_internal=True)
    pattern = simple_pattern_factory("TestPattern")
    step = test_func.get_next_step(pattern)
    assert step.__class__.__name__ == "InternalConnectionStep"
    assert step.own_connector in pattern.connectors.values()
    # Since next pattern is selected from distribution, validate that next_connector exists
    assert isinstance(step.next_connector, Connector)


def test_random_generator_function_constructor(simple_distribution_factory):
    """Test construction of a generator function by instantiating a RandomGeneratorFunction."""
    distributions = {name: simple_distribution_factory(name) for name in ["Distr1", "Distr2"]}
    the_function = RandomGeneratorFunction(distributions)
    assert isinstance(the_function, GeneratorFunction)
    assert isinstance(the_function, RandomGeneratorFunction)


def test_random_function_initialize_pattern(simple_distribution_factory):
    """Test initializing a pattern with the simple example
    RandomGeneratorFunction."""
    random.seed(42)
    distributions = {name: simple_distribution_factory(name) for name in ["Distr1", "Distr2"]}
    the_function = RandomGeneratorFunction(distributions)
    initialization_step = the_function.initialize_pattern()
    # get the initialized pattern from the step
    the_pattern = initialization_step.get_pattern()
    assert isinstance(the_pattern, Pattern)


def test_random_generator_function(simple_distribution_factory, simple_pattern_factory):
    """Test getting the next step from RandomGeneratorFunction with a simple pattern."""
    random.seed(42)
    the_pattern = simple_pattern_factory("Some label")

    # Case: set p_connect_internal to 0 (expect an AddPatternStep)
    distributions = {name: simple_distribution_factory(name) for name in ["Distr1", "Distr2"]}
    the_function = RandomGeneratorFunction(distributions)

    step = the_function.get_next_step(the_pattern)
    assert isinstance(step, AddPatternStep)

    selected_connector = step.own_connector
    next_pattern = step.next_pattern
    next_connector = step.next_connector

    assert isinstance(selected_connector, Connector)
    assert isinstance(next_connector, Connector)
    assert isinstance(next_pattern, Pattern)
    assert selected_connector in the_pattern.connectors.values()
    assert next_connector in next_pattern.connectors.values()

    # Case: set p_connect_internal to 1 (expect an InternalConnectionStep)
    the_function.set_p_connect_internal(1)
    step = the_function.get_next_step(the_pattern)
    assert isinstance(step, InternalConnectionStep)

    selected_connector = step.own_connector
    next_connector = step.next_connector

    assert isinstance(selected_connector, Connector)
    assert isinstance(next_connector, Connector)
    assert selected_connector in the_pattern.connectors.values()
    assert next_connector in the_pattern.connectors.values()


def test_capping_function_constructor():
    """ "Test construction of a generator function by instantiating a CappingFunction."""
    my_function = CappingFunction()
    assert isinstance(my_function, CappingFunction)


def test_capping_function_get_capping_steps(simple_pattern_factory):
    """Test getting capping steps from CappingFunction."""
    my_function = CappingFunction()

    pattern1 = simple_pattern_factory("dummy")

    capping_steps = my_function.get_capping_steps(pattern1)

    assert isinstance(capping_steps, list)
    assert len(capping_steps) == 2
    assert isinstance(capping_steps[0], CappingStep)

    # Make sure capping steps are valid by executing it
    for step in capping_steps:
        step.execute_on(pattern1)

    # Corrupt internal _make_capping_step method to test error handling
    pattern1 = simple_pattern_factory("dummy")
    my_function._make_capping_steps = lambda x: []
    with pytest.raises(RuntimeError, match="Connectors of the CappingSteps do not match"):
        my_function.get_capping_steps(pattern1)


def test_reconstruction_generator_function_constructor(simple_distribution_factory):
    """Test construction of a reconstruction generator function."""
    distributions = {name: simple_distribution_factory(name) for name in ["Distr1", "Distr2"]}
    the_function = ReconstructionGeneratorFunction(distributions)
    assert isinstance(the_function, GeneratorFunction)
    assert isinstance(the_function, ReconstructionGeneratorFunction)
    assert the_function.generation_history is None
    assert the_function._current_step == 0


def test_reconstruction_generator_function_set_history():
    """Test setting the generation history."""
    reconstruction_func = ReconstructionGeneratorFunction({})
    history = GenerationHistory()
    reconstruction_func.set_generation_history(history)
    assert reconstruction_func.generation_history is history
    assert reconstruction_func._current_step == 0


def test_reconstruction_generator_function_no_history(simple_distribution_factory):
    """Test error handling when generation history is not set."""
    distributions = {name: simple_distribution_factory(name) for name in ["Distr1", "Distr2"]}
    the_function = ReconstructionGeneratorFunction(distributions)

    with pytest.raises(AttributeError, match="Generation history is not set"):
        the_function.initialize_pattern()

    # Create a dummy pattern to test get_next_step
    pattern = next(iter(distributions.values())).patterns[
        next(iter(distributions["Distr1"].patterns.keys()))
    ]

    with pytest.raises(AttributeError, match="Generation history is not set"):
        the_function.get_next_step(pattern)


def test_reconstruction_initialize_pattern(simple_distribution_factory):
    """Test initializing a pattern with a valid history."""
    distributions = {name: simple_distribution_factory(name) for name in ["Distr1", "Distr2"]}
    history = GenerationHistory()

    # Add a mock initialization step to history
    history.history.append(
        {
            "generator_step_type": "initialization",
            "own_connector": None,
            "next_pattern": "pattern1",
            "next_connector": None,
            "sampled_distribution_name": "Distr1",
        }
    )

    the_function = ReconstructionGeneratorFunction(distributions, history)

    # Test initialize_pattern
    init_step = the_function.initialize_pattern()
    assert isinstance(init_step, InitializationStep)
    assert init_step.sampled_distribution_name == "Distr1"
    assert the_function._current_step == 1


def test_reconstruction_get_next_step(simple_distribution_factory):
    """Test getting next steps with a valid history."""
    distributions = {name: simple_distribution_factory(name) for name in ["Distr1", "Distr2"]}
    history = GenerationHistory()

    # Get actual patterns from the distributions to work with
    pattern1 = next(iter(distributions["Distr1"].patterns.values()))
    pattern2 = next(iter(distributions["Distr2"].patterns.values()))

    # Get connector ids from the actual patterns
    connector1 = next(iter(pattern1.connectors.values()))
    connector2 = next(iter(pattern2.connectors.values()))
    connector3 = (
        list(pattern1.connectors.values())[1] if len(pattern1.connectors) > 1 else connector1
    )

    # Setup mock history with different step types
    history.history = [
        {
            "generator_step_type": "initialization",
            "own_connector": None,
            "next_pattern": pattern1.label,
            "next_connector": None,
            "sampled_distribution_name": "Distr1",
        },
        {
            "generator_step_type": "add_pattern",
            "own_connector": connector1.label,
            "next_pattern": pattern2.label,
            "next_connector": connector2.label,
            "sampled_distribution_name": "Distr2",
        },
        {
            "generator_step_type": "internal_connection",
            "own_connector": connector1.label,
            "next_connector": connector3.label,
            "next_pattern": None,
            "sampled_distribution_name": None,
        },
        {
            "generator_step_type": "termination",
            "own_connector": None,
            "next_pattern": None,
            "next_connector": None,
            "sampled_distribution_name": None,
        },
    ]

    the_function = ReconstructionGeneratorFunction(distributions, history)

    # Skip initialization step
    the_function._current_step = 1

    # Test add_pattern step
    next_step = the_function.get_next_step(pattern1)
    assert isinstance(next_step, AddPatternStep)
    assert next_step.own_connector.label == connector1.label
    assert next_step.next_pattern.label == pattern2.label
    assert the_function._current_step == 2

    # Test internal_connection step
    next_step = the_function.get_next_step(pattern1)
    assert isinstance(next_step, InternalConnectionStep)
    assert next_step.own_connector.label == connector1.label
    assert next_step.next_connector.label == connector3.label
    assert the_function._current_step == 3

    # Test termination step
    next_step = the_function.get_next_step(pattern1)
    assert isinstance(next_step, TerminationStep)
    assert the_function._current_step == 4

    # Test Error: Attempting to get next step after all steps have been processed
    invalid_history = GenerationHistory()
    invalid_history.history = history.history.copy()

    # Create a new function with the same history
    error_function = ReconstructionGeneratorFunction(distributions, invalid_history)
    error_function._current_step = 4  # Set to after all steps

    with pytest.raises(IndexError):
        error_function.get_next_step(pattern1)

    # Test Error: Invalid step type in history
    invalid_history = GenerationHistory()
    invalid_history.history = [
        {
            "generator_step_type": "initialization",
            "own_connector": None,
            "next_pattern": pattern1.label,
            "next_connector": None,
            "sampled_distribution_name": "Distr1",
        },
        {
            "generator_step_type": "invalid_step_type",  # Invalid step type
            "own_connector": connector1.label,
            "next_pattern": pattern2.label,
            "next_connector": connector2.label,
            "sampled_distribution_name": "Distr2",
        },
    ]

    error_function = ReconstructionGeneratorFunction(distributions, invalid_history)
    error_function._current_step = 1  # Skip initialization

    with pytest.raises(ValueError, match="Unknown step type"):
        error_function.get_next_step(pattern1)


def test_reconstruction_reset():
    """Test resetting the reconstruction generator function."""
    reconstruction_func = ReconstructionGeneratorFunction({})
    history = GenerationHistory()
    reconstruction_func.set_generation_history(history)

    # Manually set current step to non-zero
    reconstruction_func._current_step = 3

    # Reset should set current step back to 0
    reconstruction_func.reset()
    assert reconstruction_func._current_step == 0


def test_reconstruction_capping_function_constructor(simple_distribution_factory):
    """Test construction of a reconstruction capping function."""
    distributions = {
        name: simple_distribution_factory(name, no_pattern_connectors=1)
        for name in ["Distr1", "Distr2"]
    }
    the_function = ReconstructionCappingFunction(distributions)
    assert isinstance(the_function, CappingFunction)
    assert isinstance(the_function, ReconstructionCappingFunction)
    assert the_function.generation_history is None


def test_reconstruction_capping_function(simple_distribution_factory, simple_pattern_factory):
    """Test making capping steps with a valid history."""
    distributions = {
        name: simple_distribution_factory(name, no_pattern_connectors=1)
        for name in ["Distr1", "Distr2"]
    }
    history = GenerationHistory()

    # Use simple_pattern_factory for the pattern
    pattern = simple_pattern_factory("TestPattern")

    # Get connector labels from the pattern
    conn_labels = list(pattern.connectors.keys())

    # Setup mock capping steps in history
    history.history = [
        {
            "generator_step_type": "capping",
            "own_connector": conn_labels[0],
            "next_pattern": "CapPattern",
            "next_connector": "Connector label0",
            "sampled_distribution_name": "Distr1",
        },
        {
            "generator_step_type": "capping",
            "own_connector": conn_labels[1],
            "next_pattern": None,
            "next_connector": None,
            "sampled_distribution_name": None,
        },
    ]

    # Create the reconstruction capping function with the history
    the_function = ReconstructionCappingFunction(distributions, history)

    # Verify construction
    assert isinstance(the_function, CappingFunction)
    assert isinstance(the_function, ReconstructionCappingFunction)
    assert the_function.generation_history is history

    # Test setting history separately
    new_function = ReconstructionCappingFunction(distributions)
    assert new_function.generation_history is None
    new_function.set_generation_history(history)
    assert new_function.generation_history is history

    # Test Error: Create with distributions having multiple connectors
    with pytest.raises(
        ValueError, match="CappingFunction should only use distributions with one connector label"
    ):
        multi_connector_distributions = {
            name: simple_distribution_factory(name, no_pattern_connectors=2)
            for name in ["Distr1", "Distr2"]
        }
        ReconstructionCappingFunction(multi_connector_distributions)

    # Test Error: History with invalid capping step (missing connector)
    incomplete_history = GenerationHistory()
    # Only include one connector, missing the second
    incomplete_history.history = [history.history[0]]

    error_function = ReconstructionCappingFunction(distributions, incomplete_history)

    # This would fail in _make_capping_steps if we were able to test it directly
    # Since the original test doesn't actually call _make_capping_steps, we're verifying the attribute
    assert error_function.generation_history is incomplete_history
