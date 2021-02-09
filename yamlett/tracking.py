from datetime import datetime
from typing import Any, Dict, Optional, Union, Tuple, List
from uuid import uuid4
from pathlib import Path

import pymongo
from pymongo.errors import DuplicateKeyError
from box import Box
import cloudpickle as pickle


class Experiment:
    def __init__(
        self,
        name: str = "runs",
        mongo_options: Optional[Dict] = None,
    ):
        """Access a named ``Experiment`` that can be queried.

        :param name: name of the experiment.
        :param mongo_options: dictionary used to pass arguments to
            ``MongoClient``.
        """
        self.name = name
        self.mongo_options = mongo_options or {}

    def __getattr__(self, key: str) -> Any:
        with pymongo.MongoClient(**self.mongo_options) as m:
            collection = m.yamlett[self.name]
            # NOTE: use ``dir`` on a pymongo.Collection object to find valid
            # methods because missing attributes are automatically created as
            # new Collection objects.
            if key in dir(collection):
                return getattr(collection, key)
            else:
                raise AttributeError(
                    f"Experiment does not have an attribute named '{key}'"
                )


class Run:
    def __init__(
        self,
        id: Optional[str] = None,
        experiment_name: str = "runs",
        mongo_options: Optional[Dict] = None,
        path: Optional[Union[str, Path]] = ".yamlett",
    ):
        """Creates a new Run or retrieves an existing Run if the provided ``id``
        already exists.

        :param id: unique ID for the Run object.  If ``None``, the ID will be
            the hexadecimal representation of a UUID4.
        :param experiment_name: name of the associated experiment.  Defaults to
            ``"runs"``.
        :param mongo_options: dictionary used to pass arguments to
            ``MongoClient``.
        :param path: a string or a ``pathlib.Path``-compatible object pointing
            to a directory where pickled objects will be stored.  This can be
            used to write large objects to cloud storage (using the cloudpathlib
            library) or to the local filesystem.  If a string is passed, then
            yamlett will use ``pathlib.Path`` to make it compatible.  Defaults
            to ``".yamlett"``.
        """
        self.id = id
        if self.id is None:
            self.id = uuid4().hex
        self.experiment_name = experiment_name
        self.mongo_options = mongo_options or {}

        self.path = path
        if isinstance(path, str):
            self.path = Path(path)
        self.path = self.path.joinpath(self.experiment_name, self.id)
        self.path.mkdir(parents=True, exist_ok=True)

        self._dirty = True
        self._data = None
        self._start()

    @property
    def experiment(self) -> Experiment:
        """
        Returns the ``Experiment`` where this ``Run`` is stored.
        """
        return Experiment(name=self.experiment_name, mongo_options=self.mongo_options)

    def data(self, resolve=False) -> Dict[str, Any]:
        """
        Returns the data stored by this ``Run``.
        """
        if self._dirty:
            data = self.experiment.find_one({"_id": self.id})
            del data["_yamlett"]
            self._data = data
            self._dirty = False
            if resolve:
                self._data = self._resolve_data(self._data)
        if self._data:
            return Box(self._data)

    def _resolve_data(
        self, data: Union[Tuple, List, Dict[str, Any]], parts: Optional[str] = None
    ) -> Dict[str, Any]:
        parts = parts or []
        if isinstance(data, dict):
            if data.get("_yamlett", {}).get("pickled", False):
                key = ".".join(parts)
                filepath = self.path.joinpath(f"{key}.pkl")
                with filepath.open("rb") as fd:
                    return pickle.load(fd)
            else:
                return {k: self._resolve_data(v, parts + [k]) for k, v in data.items()}
        else:
            return data

    def _start(self):
        """
        Starts or resume a ``Run``.
        """
        try:
            doc = {
                "_id": self.id,
                "_yamlett": {
                    "created_at": datetime.now(),
                    "path": pickle.dumps(self.path.resolve()),
                },
            }
            self.experiment.insert_one(doc)
        except DuplicateKeyError:  # resume the run
            run_data = Box(self.experiment.find_one({"_id": self.id}))
            self.path = pickle.loads(run_data._yamlett.path)
        self._dirty = True
        self._started = True

    def store(
        self,
        key: str,
        value: Union[Any, Dict[str, Any]],
        push: bool = False,
        pickled: bool = False,
    ):
        """
        Stores a given ``value`` under the given ``key``.

        :param key: string to use to uniquely identify the path to store the
            ``value``.  Dots (``.``) can be used to access deeper levels in your
            object.  For example, the key ``model.parameters.regularization``
            points to the ``regularization`` key under ``parameters`` under
            ``model``.
        :param value: value to store under the given ``key``.
        :param push: set to ``True`` to append the ``value`` to an existing list
            under ``key``.  For instance, if ``[1,2,3]`` is already stored under
            the key ``my_list``, then calling ``run.store("my_list", 4,
            push=True)`` will result in the list ``[1,2,3,4]``.  Defaults to
            False.
        :param pickled: set to ``True`` to cloudpickle the value and store it in
            the file system specified by ``self.path``.  The pickle file will be
            stored under
            ``self.path.cwd()``/``self.experiment.name``/``self.id``/``key``.pkl.
        """
        filter = {"_id": self.id}
        op = "$push" if push else "$set"
        if pickled:
            if push:
                raise ValueError(
                    "push and pickled cannot be set to True at the same time."
                )
            filepath = self.path.joinpath(f"{key}.pkl")
            with filepath.open("wb") as fd:
                pickle.dump(value, fd)
            update = {op: {f"{key}._yamlett.pickled": True}}
        else:
            update = {op: {key: value}}

        update_result = self.experiment.update_one(filter, update)
        if update_result.modified_count == 0:
            raise ValueError(f"Updating operation failed: {update}")
        self._dirty = True
        last_modified = {"$set": {"_yamlett.last_modified_at": datetime.now()}}
        self.experiment.update_one(filter, last_modified)
