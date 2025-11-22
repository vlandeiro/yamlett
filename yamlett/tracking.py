from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import uuid4

from box import Box
from cloudpathlib import AnyPath
import cloudpickle as pickle

from .artifact import ArtifactStore
from .db import (
    create_run,
    create_runs_table,
    get_data_from_run,
    run_exists,
    store_rows,
)
from .utils import rows_to_dict, dict_to_rows


class Run:
    def __init__(
        self,
        sqlalchemy_path: str = "sqlite://",
        run_id: Optional[str] = None,
        artifacts_path: Optional[str] = ".yamlett",
        sep: str = ".",
    ):
        """Creates a new Run or retrieves an existing Run if the provided ``id``
          already exists.

          :param run_id: unique ID for the Run object.  If not specified, the ID
              will be the hexadecimal representation of a UUID4.
          :param sqlalchemy_path: the SQLAlchemy path to the SQL database.
              Defaults to SQLite in ``:memory:``.
          :param artifacts_path: a string pointing to a directory where pickled
              objects will be stored.  This can be used to write large objects
              to cloud storage (leveraging the ``cloudpathlib`` library) or to
              the local filesystem.  If a string is passed,
              ``cloudpathlib.AnyPath`` will be used to resolve the path.
              Defaults to local store in the ``".yamlett"`` folder.
            """
        self.run_id = run_id or uuid4().hex[:8]
        self.sqlite_path = sqlite_path
        self.sep = sep

        create_runs_table(sqlite_path)
        artifacts_path = AnyPath(artifacts_path).joinpath(self.run_id)
        self.artifacts = ArtifactStore(path=artifacts_path)

        self._dirty = True
        self._data = None
        self._resolved = False
        self._start()

    @property
    def data(self) -> Dict[str, Any]:
        return self.get_data(resolve=True)

    def get_data(self, resolve=False, as_df=False) -> Dict[str, Any]:
        """
        Returns the data stored by this ``Run``.

        :param resolve: boolean indicating whether the data artifacts should be
            resolved or not.  Defaults to False.
        """
        # Force-load the data if it has changed or if the user wants to see the
        # data with/without artifacts and it's different than the last call
        if self._dirty or self._resolved != resolve:
            self._load_run_data(resolve=resolve)
        if self._data:
            if as_df:
                import pandas as pd

                return pd.DataFrame(
                    self._data,
                    columns=["key", "value", "pickled", "run_id", "last_modified_at"],
                )
            else:
                return Box(rows_to_dict(rows=self._data, sep=self.sep))

    def _load_run_data(self, resolve=False):
        self._data = get_data_from_run(self.sqlite_path, self.run_id)
        self._dirty = False
        if resolve:
            self._data = self._resolve_data(self._data)
        self._resolved = resolve

    def _resolve_data(self, data: List[Tuple[str, Any]]) -> List[Tuple[str, Any]]:
        """Iterates over data key-value pairs and loads yamlett artifacts when
        necessary.
        """
        resolved_data = []
        for k, v, pickled, run_id, last_modified_at in data:
            if pickled:
                v = pickle.loads(v)
            resolved_data.append((k, v, pickled, run_id, last_modified_at))
        return resolved_data

    def _start(self):
        """
        Starts or resume a ``Run``.
        """
        if not run_exists(sqlite_path=self.sqlite_path, run_id=self.run_id):
            create_run(sqlite_path=self.sqlite_path, run_id=self.run_id, sep=self.sep)

        self._dirty = True
        self._started = True

    def store(
        self,
        key: str,
        value: Union[Any, Dict[str, Any]],
        pickled: Optional[bool] = None,
    ):
        """
        Stores a given ``value`` under the given ``key``.

        :param key: string to use to uniquely identify the path to store the
            ``value``.  Dots (``.``) can be used to access deeper levels in your
            object.  For example, the key ``model.parameters.regularization``
            points to the ``regularization`` key under ``parameters`` under
            ``model``.
        :param value: value to store under the given ``key``.
        :param pickled: set to ``True`` to pickle the value and store it in the
            file system specified by ``artifacts_path``.  The pickle file will
            be stored under ``artifacts_path.cwd()``/``run_id``/``key``.pkl.  By
            default (None), any value not natively compatible with sqlite will
            be pickled.  This means that if ``value`` is not a number or a
            string, it will be pickled.
        """
        if pickled is None:
            if isinstance(value, (float, int, str)):
                pickled = False
            elif isinstance(value, dict):
                rows = dict_to_rows(d=value, sep=self.sep, prefix=key)
                for key, value in rows:
                    self.store(key, value)
                return
            else:
                pickled = True

        if pickled:
            value = pickle.dumps(value)

        store_rows(
            sqlite_path=self.sqlite_path,
            run_id=self.run_id,
            rows=[(key, value, pickled)],
        )
        self._dirty = True


if __name__ == "__main__":
    run = Run(sqlite_path="yamlett.db")
    run.store("experiment", "My Very Interesting Experiment")
    run.store("params.C", "0.01")
    print(run.data)
    run.store("params.C", "100.5")
    print(run.data)
    run.store("results.preds", [0, 1, 1, 0])
    print(run.data)
    run.store(
        "metrics",
        {"f1": 0.9, "prec": 0.8, "recall": 0.95, "some_crazy_object": [1, 2, 3]},
    )
    print(run.data)
    print(run.get_data(as_df=True, resolve=True))
    print(run.data.yamlett.run_id)
