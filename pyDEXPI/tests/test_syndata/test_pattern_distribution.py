"""Tests for the module pattern distribution."""

import pytest

from pydexpi.syndata.pattern_distribution import PatternDistribution


def test_distribution_constructor(simple_distribution_factory):
    """Test if a distribution is created correctly"""
    simple_distribution = simple_distribution_factory("simple_distribution")
    assert len(simple_distribution.patterns) == 2


def test_add_pattern_and_normalize(simple_distribution_factory, simple_pattern_factory):
    """Test adding a pattern to the distribution with and without normalization."""
    simple_distribution = simple_distribution_factory("simple_distribution")
    # Add a new pattern without normalization
    the_pattern = simple_pattern_factory("New label")
    simple_distribution.add_pattern(the_pattern, 0.5, normalize=False)
    assert len(simple_distribution.patterns) == 3
    assert sum(simple_distribution.probabilities.values()) == 1.5

    # Add a new pattern with normalization
    simple_distribution.add_pattern(simple_pattern_factory("New label 2"), 0.5)
    assert 0.99999 < sum(simple_distribution.probabilities.values()) < 1.00001

    # try adding a pattern that is already part
    with pytest.raises(ValueError):
        simple_distribution.add_pattern(the_pattern, 0.5)

    # try adding a pattern with invalid connectors
    invalid_pattern = simple_pattern_factory("New label 3")
    del invalid_pattern.connectors[next(iter(invalid_pattern.connectors))]
    with pytest.raises(ValueError):
        simple_distribution.add_pattern(invalid_pattern, 0.5)


def test_check_pattern_compatibility(simple_distribution_factory, simple_pattern_factory):
    """Test the check pattern compatibility method"""
    simple_distribution = simple_distribution_factory("simple_distribution")
    the_pattern = simple_pattern_factory("New label")
    assert simple_distribution.check_pattern_compatibility(the_pattern)
    del the_pattern.connectors[next(iter(the_pattern.connectors))]
    assert not simple_distribution.check_pattern_compatibility(the_pattern)


def test_sample_pattern(simple_distribution_factory):
    """Test if the simple distributions sampling methods work"""
    simple_distribution = simple_distribution_factory("simple_distribution")
    assert simple_distribution.check_pattern_compatibility(simple_distribution.sample_pattern()[0])
    assert simple_distribution.check_pattern_compatibility(simple_distribution.random_pattern()[0])
    for pattern in simple_distribution:
        assert simple_distribution.check_pattern_compatibility(pattern[0])


def test_save_and_load_distribution(tmp_path, simple_distribution_factory):
    """Test loading and saving a distribution"""
    simple_distribution = simple_distribution_factory("simple_distribution")
    simple_distribution.save(tmp_path)
    loaded_distribution = PatternDistribution.load(tmp_path, simple_distribution.name)
    assert simple_distribution.name == loaded_distribution.name
    for key in simple_distribution.labels():
        assert simple_distribution.patterns[key].label == loaded_distribution.patterns[key].label
