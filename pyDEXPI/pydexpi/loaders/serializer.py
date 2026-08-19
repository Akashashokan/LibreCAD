import pickle
from abc import ABC, abstractmethod
from pathlib import Path

from pydexpi.dexpi_classes.dexpiModel import DexpiModel


class Serializer(ABC):
    """Abstract class to (de)serialize DEXPI models."""

    @abstractmethod
    def save(self, model: DexpiModel, dir_path: Path, filename: str):
        """Abstract method to save a DEXPI model to a file.

        Parameters
        ----------
        model : DexpiModel
            DEXPI model that should be saved.
        dir_path : Path
            Directory where the DEXPI model should be saved.
        filename : str
            Filename for the saved DEXPI model.
        """
        pass

    @abstractmethod
    def load(self, dir_path: Path, filename: str):
        """Abstract method to load a DEXPI PID data model from a P&ID file.

        Parameters
        ----------
        dir_path : Path
            Directory where the P&ID file is stored.
        filename : str
            Filename of the P&ID file.

        Returns
        -------
        DexpiModel
            Loaded DEXPI model.
        """
        pass


class PickleSerializer(Serializer):
    def save(self, model: DexpiModel, dir_path: Path, filename: str):
        """Saves a DEXPI model to pickle.

        Parameters
        ----------
        model : DexpiModel
            DEXPI model that should be saved.
        dir_path : Path
            Directory where the DEXPI model should be saved.
        filename : str
            Filename for the saved DEXPI model.
        """
        if not filename.endswith(".pkl"):
            filename += ".pkl"
        path = Path(dir_path) / filename

        with open(path, "wb") as f:
            pickle.dump(model, f)

    def load(self, dir_path: Path, filename: str):
        """Load a DEXPI model from a pickle file.

        Parameters
        ----------
        dir_path : Path
            Directory where the pickle file is stored.
        filename : str
            Filename of the pickle file.

        Returns
        -------
        DexpiModel
            Loaded DEXPI model.
        """
        if not filename.endswith(".pkl"):
            filename += ".pkl"
        path = Path(dir_path) / filename

        with open(path, "rb") as f:
            model = pickle.load(f)
        return model
