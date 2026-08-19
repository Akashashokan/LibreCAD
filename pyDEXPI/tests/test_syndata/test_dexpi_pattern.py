"""Tests for the module dexpi_pattern."""

import pytest

from pydexpi.dexpi_classes import equipment, piping
from pydexpi.syndata.dexpi_pattern import (
    BasicPipingInConnector,
    BasicPipingOutConnector,
    DexpiPattern,
)
from pydexpi.toolkits import piping_toolkit as pt


@pytest.fixture
def in_connector_factory():
    """Fixture to create an in connector factory."""

    def _create_in_connector():
        """Create an in connector."""
        in_item = piping.OperatedValve(nodes=[piping.PipingNode() for i in range(2)])
        return BasicPipingInConnector("Main-In", in_item, target_node_index=0)

    return _create_in_connector


@pytest.fixture
def out_connector_factory(simple_pns_factory):
    """Fixture to create an out connector factory."""

    def _create_out_connector():
        """Create an out connector."""
        segment = simple_pns_factory()
        pt.append_connection_to_unconnected_segment(segment, piping.Pipe(), 1)
        return BasicPipingOutConnector("Main-Out", segment)

    return _create_out_connector


@pytest.fixture
def the_pattern_factory(simple_dexpi_model_factory, connector_label_prefix="Main"):
    """Fixture to create a pattern factory."""

    def _create_pattern(pattern_name="the_pattern", connector_prefix=connector_label_prefix):
        """Create a Dexpi pattern."""
        model = simple_dexpi_model_factory()
        new_nozzle = equipment.Nozzle(nodes=[piping.PipingNode()])
        model.conceptualModel.taggedPlantItems[0].nozzles.append(new_nozzle)
        in_conn = BasicPipingInConnector(f"{connector_prefix}-In", new_nozzle, target_node_index=0)
        out_conn = BasicPipingOutConnector(
            f"{connector_prefix}-Out",
            model.conceptualModel.pipingNetworkSystems[-1].segments[-1],
        )
        return DexpiPattern(pattern_name, [in_conn, out_conn], model)

    return _create_pattern


# Connector tests
def test_connector_constructor(in_connector_factory, out_connector_factory):
    """Evaluation if the In and Out Connectors are created properly"""
    conn_in = in_connector_factory()
    conn_out = out_connector_factory()
    assert conn_in is not None
    assert conn_out is not None


def test_assert_valid_counterpart(in_connector_factory, out_connector_factory):
    """Test to see if dexpi connectors correctly assert counterpart validity."""
    instance_in = in_connector_factory()
    instance_out = out_connector_factory()
    assert instance_in.assess_valid_counterpart(instance_out)
    assert instance_out.assess_valid_counterpart(instance_in)
    second_in = in_connector_factory()
    second_out = out_connector_factory()
    assert not instance_in.assess_valid_counterpart(second_in)
    assert not instance_out.assess_valid_counterpart(second_out)


def test_connect_to_counterpart(in_connector_factory, out_connector_factory):
    """Try connecting the connectors. Call the method on the in connector,
    because this one calls the connection method of its counterpart."""
    instance_in = in_connector_factory()
    instance_out = out_connector_factory()
    second_in = in_connector_factory()
    with pytest.raises(ValueError):
        instance_in.connect_to_counterpart(second_in)

    instance_in.connect_to_counterpart(instance_out)
    assert instance_out.piping_network_segment.targetItem == instance_in.target_item
    assert instance_out.piping_network_segment.targetNode == instance_in.target_item.nodes[0]


# Test pattern functionality
def test_pattern_constructor(the_pattern_factory):
    """Evaluation if the pattern constructor works as required."""
    pattern_instance = the_pattern_factory()
    assert len(pattern_instance.connectors) == 2


def test_incorporate_pattern(the_pattern_factory):
    """Test incorporating a counterpart to a pattern to a counterpart."""

    new_pattern = the_pattern_factory("Pattern 1")
    counterpart = the_pattern_factory("Pattern 2", connector_prefix="Counterpart")

    new_pattern.incorporate_pattern(
        new_pattern.connectors["Main-Out"], counterpart, counterpart.connectors["Counterpart-In"]
    )
    assert len(new_pattern.connectors) == 2
    assert len(new_pattern.dexpi_model.conceptualModel.taggedPlantItems) == 2

    # Check if exceptions are working if connectors are not correctly affiliated
    new_pattern = the_pattern_factory()
    counterpart = the_pattern_factory()
    # Removing the out connector from pattern by key
    faulty_connector = new_pattern.connectors["Main-Out"]
    new_pattern.connectors.pop("Main-Out")
    with pytest.raises(ValueError):
        new_pattern.incorporate_pattern(
            faulty_connector, counterpart, counterpart.connectors["Main-In"]
        )

    new_pattern = the_pattern_factory()
    counterpart = the_pattern_factory()
    # Removing the in connector from the counterpart by key
    faulty_connector = counterpart.connectors["Main-In"]
    counterpart.connectors.pop("Main-In")
    with pytest.raises(ValueError):
        new_pattern.incorporate_pattern(
            new_pattern.connectors["Main-Out"], counterpart, faulty_connector
        )


def test_load_and_save(tmp_path, the_pattern_factory):
    """Test loading and saving a graph pattern"""
    pattern_instance = the_pattern_factory()
    pattern_instance.save(tmp_path, "test")
    loaded_pattern = DexpiPattern.load(tmp_path, "test")

    assert pattern_instance.label == loaded_pattern.label

    connectors = pattern_instance.connectors
    loaded_connectors = loaded_pattern.connectors
    assert len(connectors) == len(loaded_connectors)
    for c, lc in zip(connectors, loaded_connectors):
        assert c == lc
        assert connectors[c].label == loaded_connectors[lc].label

    observers = pattern_instance.observer_patterns
    loaded_observers = loaded_pattern.observer_patterns
    assert len(observers) == len(loaded_observers)
    assert set(observers.keys()) == set(loaded_observers.keys())
