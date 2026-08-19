"""Conftest for synthetic data generation tests.

Contains some mock classes and package-wide fixtures"""

import pytest

from pydexpi.syndata.pattern import (
    Connector,
    Pattern,
)
from pydexpi.syndata.pattern_distribution import PatternDistribution


class DummyConnector(Connector):
    """
    A dummy implementation of the abstract `Connector` class for testing purposes.

    This class provides a minimal concrete implementation of the `_implement_connection`
    method, allowing the `Connector` class to be instantiated and tested.
    """

    def _implement_connection(self, counterpart: Connector) -> None:
        return super()._implement_connection(counterpart)

    def assess_valid_counterpart(self, counterpart: Connector) -> bool:
        if not isinstance(counterpart, DummyConnector):
            raise TypeError(f"Counterpart must be of type DummyConnector, not {type(counterpart)}")
        return True


class DummyPattern(Pattern):
    """
    A dummy implementation of the abstract `Pattern` class for testing purposes.

    This class provides a minimal concrete implementation of the `_implement_incorporation`
    method, allowing the `Pattern` class to be instantiated and tested.
    """

    def _implement_incorporation(
        self,
        counterpart: Pattern,
    ) -> None:
        return super()._implement_incorporation(counterpart)


@pytest.fixture
def simple_pattern_factory():
    """Factory function to create a simple pattern with two connectors."""

    def _factory(
        pattern_label: str,
        connector_label_prefix: str = "Connector label",
        no_pattern_connectors: int = 2,
    ) -> DummyPattern:
        """Factory function to create a simple pattern."""
        # Create primary connectors
        connectors = [
            DummyConnector(f"{connector_label_prefix}{i + 1}") for i in range(no_pattern_connectors)
        ]
        the_pattern = DummyPattern(
            pattern_label,
            connectors=connectors,
            kwinfos={"dummy_kw": "Dummy kw value"},
        )
        # Create observer pattern and add it
        observer_connectors = [
            DummyConnector(f"{connector_label_prefix}{i + 1}") for i in range(no_pattern_connectors)
        ]
        observer_pattern = DummyPattern(pattern_label, connectors=observer_connectors)
        the_pattern.add_observer("Observer tag", observer_pattern)
        return the_pattern

    return _factory


@pytest.fixture
def simple_distribution_factory(simple_pattern_factory):
    """Factory function to create a simple pattern distribution."""

    def _factory(
        name: str, no_patterns: int = 2, no_pattern_connectors: int = 2
    ) -> PatternDistribution:
        """Factory function to create a simple pattern distribution."""
        patterns = [
            simple_pattern_factory(f"pattern{i + 1}", no_pattern_connectors=no_pattern_connectors)
            for i in range(no_patterns)
        ]
        pattern_dict = {p.label: p for p in patterns}
        some_weights = [float(i) for i in range(len(pattern_dict))]
        normalized_probs = [i / sum(some_weights) for i in some_weights]
        probabilities = {p: normalized_probs[i] for i, p in enumerate(pattern_dict.keys())}
        connector_labels = patterns[0].connectors.keys()
        return PatternDistribution(name, pattern_dict, probabilities, connector_labels)

    return _factory
