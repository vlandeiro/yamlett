from datetime import datetime
from typing import Any, Dict, Optional, Union
from uuid import uuid4

import pymongo
from pymongo.errors import DuplicateKeyError
from box import Box


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
        self.mongo_options = mongo_options

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
    ):
        """Creates a new Run or retrieves an existing Run if the provided ``id``
        already exists.

        :param id: unique ID for the Run object.  If ``None``, the ID will be
            the hexadecimal representation of a UUID4.
        :param experiment_name: name of the associated experiment.  Defaults to
            ``"runs"``.
        :param mongo_options: dictionary used to pass arguments to
            ``MongoClient``.
        """
        self.id = id
        if self.id is None:
            self.id = uuid4().hex
        self.experiment_name = experiment_name
        self.mongo_options = mongo_options
        self._dirty = True
        self._data = None
        self._started = False

    @property
    def experiment(self) -> Experiment:
        """
        Returns the ``Experiment`` where this ``Run`` is stored.
        """
        return Experiment(name=self.experiment_name, **self.mongo_options)

    @property
    def data(self) -> Dict[str, Any]:
        """
        Returns the data stored by this ``Run``.
        """
        if self._dirty:
            self._data = self.experiment.find_one({"_id": self.id})
            self._dirty = False
        return Box(self._data)

    def _start(self):
        """
        Starts or resume a ``Run``.
        """
        try:
            doc = {"_id": self.id, "_yamlett": {"created_at": datetime.now()}}
            self.experiment.insert_one(doc)
        except DuplicateKeyError:  # resume the run
            pass
        self._dirty = True
        self._started = True

    def store(
        self,
        key: str,
        value: Union[Any, Dict[str, Any]],
        push: bool = False,
    ):
        """
        Stores a given ``value`` under the given ``key``.

        :param key: String to use to uniquely identify the path to store the
            ``value``.  Dots (``.``) can be used to access deeper levels in your
            object.  For example, the key ``model.parameters.regularization``
            points to the ``regularization`` key under ``parameters`` under
            ``model``.
        :param value: Value to store under the given ``key``.
        :param push: Boolean set to ``True`` to append the ``value`` to an
            existing list under ``key``.  For instance, if ``[1,2,3]`` is
            already stored under the key ``my_list``, then calling
            ``run.store("my_list", 4, push=True)`` will result in the list
            ``[1,2,3,4]``.
        """
        if not self._started:
            self._start()

        filter = {"_id": self.id}
        op = "$push" if push else "$set"
        update = {op: {key: value}}
        update_result = self.experiment.update_one(filter, update)
        if update_result.modified_count == 0:
            raise ValueError(f"Updating operation failed: {update}")
        self._dirty = True
        last_modified = {"$set": {"_yamlett.last_modified_at": datetime.now()}}
        self.experiment.update_one(filter, last_modified)
