from typing import Any, Dict, Optional

import cloudpickle as pickle
from cloudpathlib import AnyPath


class Artifact:
    MAGIC_KEY = "__yamlett_artifact__"

    def __init__(self, path: AnyPath, key: str, value: Optional[Any] = None):
        self.path = path
        self.key = key
        self.value = value

    @staticmethod
    def is_artifact(d: Dict):
        if isinstance(d, dict):
            return d.get(Artifact.MAGIC_KEY, False)
        return False

    def load(self):
        filepath = self.path.joinpath(f"{self.key}.pkl")
        with filepath.open("rb") as fd:
            return pickle.load(fd)

    def save(self):
        if self.value is not None:
            filepath = self.path.joinpath(f"{self.key}.pkl")
            with filepath.open("wb") as fd:
                pickle.dump(self.value, fd)
        else:
            raise ValueError(
                "Cannot save an artifact that doesn't have "
                "a value. Make sure you passed a value argument "
                "when initializing your artifact if you want "
                "to save it to disk."
            )

    def __repr__(self):
        return {f"{self.key}.{self.MAGIC_KEY}": True}
