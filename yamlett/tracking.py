from datetime import datetime
from uuid import uuid4
from typing import Any, Optional, Union, Dict

from fastcore.meta import delegates
from pymongo.mongo_client import MongoClient
from loguru import logger


class Experiment:
    @delegates(MongoClient)
    def __init__(
        self,
        name: str = "runs",
        **kwargs,
    ):
        self.name = name
        self.mongo_kwargs = kwargs

    def __getattr__(self, key: str):
        with MongoClient(**self.mongo_kwargs) as m:
            collection = m.yamlett[self.name]
            if hasattr(collection, key):
                return getattr(collection, key)
            else:
                raise AttributeError(
                    f"Experiment does not have an attribute named '{key}'"
                )


class Run:
    @delegates(MongoClient)
    def __init__(
        self,
        id: Optional[str] = None,
        experiment_name: str = "runs",
        resume: bool = False,
        **kwargs,
    ):
        self.id = id
        if self.id is None:
            self.id = uuid4().hex
        self.experiment_name = experiment_name
        self.resume = resume
        self.mongo_kwargs = kwargs

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, type, value, traceback):
        self.stop()

    @property
    def experiment(self):
        return Experiment(name=self.experiment_name, **self.mongo_kwargs)

    def start(self):
        if not self.resume:
            # insert a new document storing the run id and the creation time
            #
            # NOTE: this will fail if the identifier already exists in the
            # database and this is the expected behavior
            doc = {"_id": self.id, "id": self.id, "created_at": datetime.now()}
            self.experiment.insert_one(doc)

    def stop(self):
        # record the final time
        filter = {"_id": self.id}
        update = {"$set": {"finished_at": datetime.now()}}
        self.experiment.update_one(filter, update)

    def store(self, key: str, value: Union[Any, Dict[str, Any]], append=False):
        if hasattr(value, "to_dict"):
            cls = value.__class__.__name__
            logger.debug(f"Calling 'to_dict' on an object of type '{cls}'.")
            value = value.to_dict()

        filter = {"_id": self.id}
        op = "$push" if append else "$set"
        update = {op: {key: value}, "$set": {"last_modified_at": datetime.now()}}
        update_result = self.experiment.update_one(filter, update)

        if update_result.modified_count == 0:
            raise ValueError("Recording this key/value pair failed.")
