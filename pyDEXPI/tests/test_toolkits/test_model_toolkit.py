import datetime
from collections import Counter
from copy import deepcopy

from pydexpi.dexpi_classes import (
    customization,
    equipment,
    metaData,
    piping,
)
from pydexpi.toolkits import model_toolkit as mt


def test_combine_dexpi_models(simple_dexpi_model_factory):
    """Test combine two or more dexpi models"""

    # Retrieve/set some data for later assertion
    metadata = metaData.MetaData()
    export_date_time = datetime.datetime(2020, 10, 3)
    models = [deepcopy(simple_dexpi_model_factory()) for i in range(3)]

    new_model = mt.combine_dexpi_models(models, metaData=metadata, exportDateTime=export_date_time)

    assert len(new_model.conceptualModel.pipingNetworkSystems) == 6
    assert new_model.exportDateTime == export_date_time
    assert new_model.conceptualModel.metaData == metadata


def test_import_model_contents_into_model(simple_dexpi_model_factory):
    """Test importing other models into a dexpi model"""

    # Retrieve/set some data for later assertion
    model = simple_dexpi_model_factory()  # call factory to create a new instance
    metadata = model.conceptualModel.metaData
    export_date_time = datetime.datetime(1967, 4, 27)
    model.exportDateTime = export_date_time

    # Combine models
    models = [deepcopy(simple_dexpi_model_factory()) for i in range(2)]
    mt.import_model_contents_into_model(model, import_models=models)

    assert len(model.conceptualModel.pipingNetworkSystems) == 6
    assert model.exportDateTime == export_date_time
    assert model.conceptualModel.metaData == metadata


def test_get_instances_with_attribute(simple_dexpi_model_factory):
    """Test getting all instances of a pns with a custom attribute and a data
    attribute."""
    # call factory to create a new instance
    model = simple_dexpi_model_factory()

    # First, assert getting an empty list if no attributes are set
    instances = mt.get_instances_with_attribute(model, "segmentNumber", "123")
    assert not instances

    # Assert getting None values
    instances = mt.get_instances_with_attribute(model, "targetItem", None)
    assert len(instances) == 2  # One pipe and one segment

    segment1 = model.conceptualModel.pipingNetworkSystems[0].segments[0]
    equipment1 = model.conceptualModel.taggedPlantItems[0]
    segment1.segmentNumber = "123"

    instances = mt.get_instances_with_attribute(
        model, "segmentNumber", "123", piping.PipingNetworkSegment
    )
    assert instances == [segment1]

    for obj in [segment1, equipment1]:
        new_custom_attribute = customization.CustomAttribute(
            attributeName="Testattribute", value="321"
        )
        obj.customAttributes.append(new_custom_attribute)

    # Rediscover instances
    instances = mt.get_instances_with_attribute(model, "Testattribute", "321")
    assert len(instances) == 2
    assert segment1 in instances
    assert equipment1 in instances

    # Test discovering instances without specifying the target value
    instances = mt.get_instances_with_attribute(model, "Testattribute")
    assert len(instances) == 2
    assert segment1 in instances
    assert equipment1 in instances

    # Rediscover instances, but only the piping network segment
    instances = mt.get_instances_with_attribute(
        model, "Testattribute", "321", piping.PipingNetworkSegment
    )
    assert instances == [segment1]


def test_get_all_instances_in_model(simple_conceptual_model_factory):
    """Test getting all instances of several classes in the simple conceptual
    model"""

    conceptual_model = simple_conceptual_model_factory()  # call factory
    pipes = mt.get_all_instances_in_model(conceptual_model, piping.Pipe)
    assert len(pipes) == 8

    equipments = mt.get_all_instances_in_model(conceptual_model, equipment.Equipment)
    assert len(equipments) == 1

    nozzles = mt.get_all_instances_in_model(equipments[0], equipment.Nozzle)
    assert len(nozzles) == 2

    p_and_e = mt.get_all_instances_in_model(conceptual_model, (equipment.Equipment, piping.Pipe))
    assert len(p_and_e) == len(pipes) + len(equipments)

    everything = mt.get_all_instances_in_model(conceptual_model)
    # Make sure there are no duplicates
    element_counts = Counter(everything)
    duplicates = [item for item, count in element_counts.items() if count > 1]
    assert len(duplicates) == 0
    assert len(everything) == 35


def test_object_is_in_model(simple_dexpi_model_factory):
    """Test to discover an object in a simple dexpi model and cross check with
    an unrelated object."""
    model = simple_dexpi_model_factory()  # call factory to create a new instance
    true_member = model.conceptualModel.pipingNetworkSystems[0].segments[0]
    assert mt.object_is_in_model(model, true_member)
    false_member = piping.Pipe()
    assert not mt.object_is_in_model(model, false_member)
