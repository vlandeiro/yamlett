from typing import Any, Dict, Optional

import cloudpickle as pickle
from cloudpathlib import AnyPath


class ArtifactStore:
    def __init__(self, path: AnyPath):
        self.path = path
        self.path.mkdir(parents=True, exist_ok=True)

    def load(self, key: str):
        filepath = self.path.joinpath(f"{key}.pkl")
        with filepath.open("rb") as fd:
            return pickle.load(fd)

    def save(self, key: str, value: Any):
        filepath = self.path.joinpath(f"{key}.pkl")
        with filepath.open("wb") as fd:
            pickle.dump(value, fd)
        return filepath
