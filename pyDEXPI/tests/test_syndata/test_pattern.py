"""Tests for the module pattern."""

import pytest

from tests.test_syndata.conftest import DummyConnector, DummyPattern


# Connector tests
def test_connector_constructor():
    """Test constructing a connector."""
    the_connector = DummyConnector("Testlabel", kwinfos={"dummy_kw": "Dummy kw value"})
    # Check if attributes are assigned correctly
    assert the_connector.label == "Testlabel"
    assert "dummy_kw", "Dummy kw value" in the_connector.kwinfos.items()


def test_assess_valid_counterpart():
    """Quick test to check connector method assess_valid_counterpart."""
    the_connector = DummyConnector("Testlabel")
    other_connector = DummyConnector("Testlabel")
    assert the_connector.assess_valid_counterpart(other_connector)


def test_connect_to_counterpart():
    """Test connecting a connector to a counterpart with the
    connect_to_counterpart method."""
    the_connector = DummyConnector("Testlabel")

    # Try to connect a connector to itself:
    with pytest.raises(ValueError):
        the_connector.connect_to_counterpart(the_connector)

    # Connect a counterpart
    the_counterpart = DummyConnector("Counterpart")
    the_connector.connect_to_counterpart(the_counterpart)
    assert the_connector.is_active is False
    assert the_counterpart.is_active is False

    # Try to connect again, and get a runtime error
    new_counterpart = DummyConnector("Counterpart")
    with pytest.raises(RuntimeError):
        the_connector.connect_to_counterpart(new_counterpart)


def test_deactivate():
    """Test deactivating a connector with the deactivate method."""
    the_connector = DummyConnector("Testlabel")

    # Test deactivation
    the_connector.deactivate()

    assert not the_connector.is_active

    # Try to deactivate the connector again:
    with pytest.raises(RuntimeError):
        the_connector.deactivate()

    # Try to connect the deactivated connector
    the_counterpart = DummyConnector("Counterpart")
    with pytest.raises(RuntimeError):
        the_connector.connect_to_counterpart(the_counterpart)


# Pattern tests
def test_pattern_constructor():
    """Test instantiating a simple pattern."""
    the_connector = DummyConnector("Connector label")
    the_pattern = DummyPattern(
        "Pattern label",
        connectors=[the_connector],
        kwinfos={"dummy_kw": "Dummy kw value"},
    )
    assert the_pattern.label == "Pattern label"
    assert the_connector in the_pattern.connectors.values()
    assert "dummy_kw", "Dummy kw value" in the_pattern.kwinfos.items()


def test_add_observer():
    """Test adding observer patterns to a pattern."""
    the_connector = DummyConnector("Connector label")
    the_pattern = DummyPattern("Pattern label", connectors=[the_connector])

    # Try adding an observer with an invalid tag
    observer_connector = DummyConnector("Connector label")
    observer_pattern = DummyPattern("Invalid pattern label", connectors=[observer_connector])
    with pytest.raises(ValueError):
        the_pattern.add_observer("Observer tag", observer_pattern)

    # Try adding an observer with an invalid connector
    observer_connector = DummyConnector("Invalid connector label")
    observer_pattern = DummyPattern("Pattern label", connectors=[observer_connector])
    with pytest.raises(ValueError):
        the_pattern.add_observer("Observer tag", observer_pattern)

    # Try adding an observer with an different number of connectors
    observer_connector = DummyConnector("Connector label")
    observer_connector2 = DummyConnector("Connector2")
    observer_pattern = DummyPattern(
        "Pattern label", connectors=[observer_connector, observer_connector2]
    )
    with pytest.raises(ValueError):
        the_pattern.add_observer("Observer tag", observer_pattern)

    # Add an observer normally
    observer_connector = DummyConnector("Connector label")
    observer_pattern = DummyPattern("Pattern label", connectors=[observer_connector])
    the_pattern.add_observer("Observer tag", observer_pattern)
    assert "Observer tag", observer_pattern in the_pattern.observer_patterns.items()


def test_incorporate_pattern(simple_pattern_factory):
    pattern1 = simple_pattern_factory("Pattern1")
    pattern2 = simple_pattern_factory(
        "Pattern2", connector_label_prefix="Pattern2 Connector label_"
    )

    invalid_connector = DummyConnector("Some label")
    with pytest.raises(ValueError):
        pattern1.incorporate_pattern(
            invalid_connector, pattern2, list(pattern2.connectors.values())[0]
        )
    with pytest.raises(ValueError):
        pattern1.incorporate_pattern(
            list(pattern1.connectors.values())[0], pattern2, invalid_connector
        )

    new_observer = simple_pattern_factory(
        "Pattern2", connector_label_prefix="Pattern2 Connector label_"
    )
    pattern2.add_observer("Observer_tag", new_observer)
    with pytest.raises(ValueError):
        pattern1.incorporate_pattern(
            list(pattern1.connectors.values())[0], pattern2, list(pattern2.connectors.values())[1]
        )

    pattern2 = simple_pattern_factory(
        "Pattern3", connector_label_prefix="Pattern3 Connector label_"
    )
    pattern1.incorporate_pattern(
        list(pattern1.connectors.values())[0], pattern2, list(pattern2.connectors.values())[1]
    )
    assert len(pattern1.connectors) == 2
    assert list(pattern2.connectors.keys())[0] in pattern1.connectors
    assert len(pattern1.observer_patterns["Observer tag"].connectors) == 2
    assert (
        list(pattern2.observer_patterns["Observer tag"].connectors.keys())[0]
        in pattern1.observer_patterns["Observer tag"].connectors
    )
    assert pattern2.is_incorporated is True
    assert pattern1.is_incorporated is False

    new_observer = simple_pattern_factory(
        "Pattern2", connector_label_prefix="Pattern2 Connector label_"
    )
    with pytest.raises(RuntimeError):
        pattern2.add_observer("Observer_tag", new_observer)
    pattern3 = simple_pattern_factory(
        "Pattern3", connector_label_prefix="Pattern3 Connector label_"
    )
    with pytest.raises(RuntimeError):
        pattern2.incorporate_pattern(
            list(pattern2.connectors.keys())[0], pattern3, list(pattern3.connectors.keys())[0]
        )


def test_connect_internal(simple_pattern_factory):
    pattern1 = simple_pattern_factory("Pattern1")
    invalid_connector = DummyConnector("Some label")
    connector1 = list(pattern1.connectors.values())[0]
    connector2 = list(pattern1.connectors.values())[1]
    with pytest.raises(ValueError):
        pattern1.connect_internal(connector1, invalid_connector)
    pattern1.connect_internal(connector1, connector2)
    assert len(pattern1.connectors) == 0
    assert len(pattern1.observer_patterns["Observer tag"].connectors) == 0
    assert connector1.is_active is False
    assert connector2.is_active is False


def test_drop_connector(simple_pattern_factory):
    pattern1 = simple_pattern_factory("Pattern1")
    the_connector = list(pattern1.connectors.values())[0]
    no_connectors = len(pattern1.connectors)
    pattern1.drop_connector(the_connector)
    assert not the_connector._is_active
    assert the_connector not in pattern1.connectors
    assert len(pattern1.connectors) == no_connectors - 1
    assert len(pattern1.observer_patterns["Observer tag"].connectors) == no_connectors - 1


def test_relabel_connector(simple_pattern_factory):
    """Test relabeling a connector with the relabel_connector method."""
    the_pattern = simple_pattern_factory("Pattern1")

    # Get the first connector and its current label
    the_connector = list(the_pattern.connectors.values())[0]
    old_label = the_connector.label

    # Define a new label and relabel the connector
    new_label = "New Connector Label"
    the_pattern.relabel_connector(the_connector, new_label)

    # Check that the connector's label has been updated
    assert the_connector.label == new_label

    # Check that the connectors dictionary has been updated correctly
    assert new_label in the_pattern.connectors
    assert old_label not in the_pattern.connectors
    assert the_pattern.connectors[new_label] == the_connector

    # Check that observer patterns' connectors have also been updated
    observer = the_pattern.observer_patterns["Observer tag"]
    assert new_label in observer.connectors
    assert old_label not in observer.connectors
    assert observer.connectors[new_label].label == new_label


def test_copy_pattern(simple_pattern_factory):
    the_pattern = simple_pattern_factory("Pattern1")
    copied_pattern = the_pattern.copy_pattern()
    assert len(copied_pattern.connectors) == len(the_pattern.connectors)
    assert len(copied_pattern.observer_patterns) == len(the_pattern.observer_patterns)


def test_change_label(simple_pattern_factory):
    the_pattern = simple_pattern_factory("Pattern1")
    the_pattern.change_label("New label")
    assert the_pattern.label == "New label"
    assert the_pattern.observer_patterns["Observer tag"].label == "New label"


def test_save_and_load_pattern(tmp_path, simple_pattern_factory):
    the_pattern = simple_pattern_factory("Pattern1")
    the_pattern.save(tmp_path, "test")
    loaded_pattern = DummyPattern.load(tmp_path, "test")
    assert the_pattern.label == loaded_pattern.label
    connectors = the_pattern.connectors
    loaded_connectors = loaded_pattern.connectors
    assert len(connectors) == len(loaded_connectors)
    for c, lc in zip(connectors.values(), loaded_connectors.values()):
        assert c.label == lc.label
    observers = the_pattern.observer_patterns
    loaded_observers = loaded_pattern.observer_patterns
    assert len(observers) == len(loaded_observers)
    assert set(observers.keys()) == set(loaded_observers.keys())
