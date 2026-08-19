import copy
import datetime

import pytest

from pydexpi.dexpi_classes import dexpiModel, equipment, metaData, piping
from pydexpi.loaders import proteus_serializer
from pydexpi.toolkits import piping_toolkit as pt


@pytest.fixture()
def loaded_example_dexpi():
    """Initialize DEXPI loader."""
    path = "data"
    filename = "C01V04-VER.EX01"
    serializer = proteus_serializer.ProteusSerializer()
    example_dexpi = serializer.load(path, filename)
    return example_dexpi


@pytest.fixture()
def simple_pns_factory():
    """Piping network segment with two pipes and valves"""

    def _create_simple_pns(no_valves=3):
        """Create a simple piping network segment with two pipes and valves."""
        valves = [
            piping.BallValve(nodes=[piping.PipingNode() for i in range(2)])
            for j in range(no_valves)
        ]
        pipes = [piping.Pipe() for i in range(no_valves)]
        segment = pt.construct_new_segment(
            valves,
            pipes,
            target_connector_item=valves[-1],
            target_connector_node_index=1,
        )
        return segment

    return _create_simple_pns


@pytest.fixture()
def simple_conceptual_model_factory(simple_pns_factory):
    """Simple conceptual model with one tank, two piping network systems for
    inlet and outlet, and an empty metadata."""

    def _create_simple_conceptual_model():
        """Create a simple conceptual model with one tank and two piping network systems."""
        the_equipment = equipment.Tank(nozzles=[equipment.Nozzle() for i in range(2)])
        pns1 = simple_pns_factory()
        pns2 = copy.deepcopy(pns1)
        pt.append_connection_to_unconnected_segment(pns1, piping.Pipe(), -1)
        pt.append_connection_to_unconnected_segment(pns2, piping.Pipe(), -1)
        pt.connect_piping_network_segment(pns1, the_equipment.nozzles[0])
        pt.connect_piping_network_segment(pns2, the_equipment.nozzles[1], as_source=True)
        the_systems = [piping.PipingNetworkSystem(segments=[i]) for i in [pns1, pns2]]
        the_metadata = metaData.MetaData()
        the_conceptual_model = dexpiModel.ConceptualModel(
            pipingNetworkSystems=the_systems,
            taggedPlantItems=[the_equipment],
            metaData=the_metadata,
        )
        return the_conceptual_model

    return _create_simple_conceptual_model


@pytest.fixture()
def simple_dexpi_model_factory(simple_conceptual_model_factory):
    """Simple dexpi model containing a simple conceptual model fixure and some
    data attributes"""

    def _create_simple_dexpi_model():
        """Create a simple dexpi model with a simple conceptual model."""
        conceptual_model = (
            simple_conceptual_model_factory()
        )  # call factory to create a new instance
        data_dict = {
            "exportDateTime": datetime.datetime(1990, 10, 3),
            "originatingSystemName": "The System Name",
            "originatingSystemVendorName": "The System Vendor",
            "originatingSystemVersion": "The System Version",
        }
        the_dexpi_model = dexpiModel.DexpiModel(conceptualModel=conceptual_model, **data_dict)
        return the_dexpi_model

    return _create_simple_dexpi_model
