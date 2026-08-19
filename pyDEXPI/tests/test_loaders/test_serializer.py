from decimal import Decimal

import pytest

from pydexpi.dexpi_classes import (
    dexpiModel,
    equipment,
    physicalQuantities,
)
from pydexpi.loaders.serializer import PickleSerializer


@pytest.fixture
def reactor_model():
    """Creates a simple reactor DEXPI model.

    Returns
    -------
    nx.DiGraph
        NetworkX graph of a reactor dexpi model.
    """
    return dexpiModel.DexpiModel(
        conceptualModel=dexpiModel.ConceptualModel(
            taggedPlantItems=[
                equipment.PressureVessel(
                    tagName="R-1",
                    chambers=[
                        equipment.Chamber(
                            upperLimitDesignPressure=physicalQuantities.PressureGauge(
                                unit=physicalQuantities.PressureGaugeUnit("bar"),
                                value=Decimal(1),
                            )
                        )
                    ],
                )
            ]
        )
    )


def test_pickle_serializer(reactor_model, tmp_path):
    """Saves and loads a dummy reactor model and compares it with the original
    object.

    Parameters
    ----------
    reactor_model : DexpiModel
        Dummy reactor model.
    """
    my_serializer = PickleSerializer()
    my_serializer.save(reactor_model, tmp_path, "test_pkl_serializer")
    new_reactor_model = my_serializer.load(tmp_path, "test_pkl_serializer")
    assert reactor_model == new_reactor_model
