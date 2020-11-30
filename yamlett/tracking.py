from datetime import datetime
from typing import Any, Dict, Optional, Union
from uuid import uuid4

import cloudpickle as pkl
import pymongo
from fastcore.meta import delegates
from loguru import logger
from pymongo.errors import DuplicateKeyError


class Experiment:
    @delegates(pymongo.MongoClient)
    def __init__(
        self,
        name: str = "runs",
        **kwargs,
    ):
        self.name = name
        self.mongo_kwargs = kwargs

    def __getattr__(self, key: str) -> Any:
        with pymongo.MongoClient(**self.mongo_kwargs) as m:
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
    @delegates(pymongo.MongoClient)
    def __init__(
        self,
        id: Optional[str] = None,
        experiment_name: str = "runs",
        **kwargs,
    ):
        self.id = id
        if self.id is None:
            self.id = uuid4().hex
        self.experiment_name = experiment_name
        self.mongo_kwargs = kwargs
        self._dirty = False
        self._data = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, type, value, traceback):
        self.stop()

    @property
    def experiment(self) -> Experiment:
        return Experiment(name=self.experiment_name, **self.mongo_kwargs)

    @property
    def data(self) -> Dict[str, Any]:
        if self._dirty:
            self._data = self.experiment.find_one({"_id": self.id})
            self._dirty = False
        return self._data

    def start(self):
        # insert a new document storing the run id and the creation time
        #
        # NOTE: this will fail with a DuplicateKeyError if the identifier
        # already exists in the database. At this point, we assume the user
        # wants to resume the run rather than start a new one.
        try:
            doc = {"_id": self.id, "created_at": datetime.now()}
            self.experiment.insert_one(doc)
        except DuplicateKeyError:
            logger.debug(f"Resuming run {self.id}.")
        self._dirty = True

    def stop(self):
        # record the final time
        filter = {"_id": self.id}
        update = {"$set": {"finished_at": datetime.now()}}
        self.experiment.update_one(filter, update)
        self._dirty = True

    def store(
        self,
        key: str,
        value: Union[Any, Dict[str, Any]],
        push: bool = False,
        pickle: bool = False,
    ):
        if hasattr(value, "to_dict"):
            cls = value.__class__.__name__
            logger.debug(f"Calling 'to_dict' on an object of type '{cls}'.")
            value = value.to_dict()
        if pickle:
            value = pkl.dumps(value)

        filter = {"_id": self.id}
        op = "$push" if push else "$set"
        update = {op: {key: value}}
        update_result = self.experiment.update_one(filter, update)
        if update_result.modified_count == 0:
            raise ValueError("Recording this key/value pair failed.")
        self._dirty = True
        last_modified = {"$set": {"last_modified_at": datetime.now()}}
        self.experiment.update_one(filter, last_modified)
