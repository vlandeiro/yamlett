from typing import Any, Dict

import mongomock
import pymongo
import pytest

from yamlett.tracking import Experiment, Run
from yamlett.utils_test import nullcontext


@pytest.mark.parametrize(
    "name, kwargs, patch, context",
    [
        ("runs", {}, mongomock.patch(), None),
        ("other_db", {}, mongomock.patch(), None),
        (
            "other_db",
            {"host": "other.host", "port": 1234},
            mongomock.patch(servers=(("other.host", 1234),)),
            None,
        ),
        (
            "runs",
            {},
            mongomock.patch("not.localhost"),
            pytest.raises(ValueError, match=".*not.localhost.*"),
        ),
    ],
)
def test_experiment(name, kwargs, patch, context):
    context = context or nullcontext()
    with context:
        with patch:
            experiment = Experiment(name=name, **kwargs)
            obj = {"_id": 1, "value": 1234}
            experiment.insert_one(obj)
            assert experiment.find_one({"_id": 1}) == obj

            # fail on invalid methods for a pymongo.Collection object
            with pytest.raises(AttributeError):
                print(experiment.foo_bar_machin_truc)


def helper_validate_run_data(result: Dict[str, Any], finished):
    assert {"_id", "created_at", "last_modified_at"} <= set(result.keys())
    if finished:
        assert "finished_at" in result.keys()


@pytest.mark.parametrize(
    "experiment_name, kwargs, patch, context", [("runs", {}, mongomock.patch(), None)]
)
def test_run_start_stop(experiment_name, kwargs, patch, context):
    context = context or nullcontext()

    with context:
        with patch:
            # initialize corresponding mock MongoClient
            client = pymongo.MongoClient(**kwargs)

            # initialize run
            run = Run(experiment_name=experiment_name, **kwargs)
            assert run._data is None
            assert not run._dirty

            # start the run
            run.start()
            assert run._dirty

            # store a value
            run.store("value", 1234)
            assert run._dirty

            # retrieve twice to check caching works okay
            for i in range(2):
                helper_validate_run_data(run.data, finished=False)
                assert not run._dirty
                assert "value" in run.data.keys()
                assert run.data["value"] == 1234

            # add another value by creating a list
            run.store("other", 1, push=True)
            assert run._dirty

            helper_validate_run_data(run.data, finished=False)
            assert not run._dirty
            assert "value" in run.data.keys()
            assert run.data["value"] == 1234
            assert "other" in run.data.keys()
            assert run.data["other"] == [1]

            # stop the run
            run.stop()
            assert run._dirty

            # resume the run
            run.start()
            assert run._dirty

            # add another value to the same list
            run.store("other", 2, push=True)
            assert run._dirty

            helper_validate_run_data(run.data, finished=False)
            assert not run._dirty
            assert "value" in run.data.keys()
            assert run.data["value"] == 1234
            assert "other" in run.data.keys()
            assert run.data["other"] == [1, 2]

            # stop the run
            run.stop()

            # validate the run one more time but make sure we have the
            # information about finishing time
            helper_validate_run_data(run.data, finished=True)
            assert not run._dirty


@pytest.mark.parametrize(
    "experiment_name, kwargs, patch, context", [("runs", {}, mongomock.patch(), None)]
)
def test_run_context_manager(experiment_name, kwargs, patch, context):
    context = context or nullcontext()

    with context:
        with patch:
            # initialize corresponding mock MongoClient
            client = pymongo.MongoClient(**kwargs)

            # initialize run
            run = Run(experiment_name=experiment_name, **kwargs)
            assert run._data is None
            assert not run._dirty

            # start the run
            run.start()
            assert run._dirty

            # store a value
            run.store("value", 1234)
            assert run._dirty

            # retrieve twice to check caching works okay
            for i in range(2):
                helper_validate_run_data(run.data, finished=False)
                assert not run._dirty
                assert "value" in run.data.keys()
                assert run.data["value"] == 1234

            # add another value by creating a list
            run.store("other", 1, push=True)
            assert run._dirty

            helper_validate_run_data(run.data, finished=False)
            assert not run._dirty
            assert "value" in run.data.keys()
            assert run.data["value"] == 1234
            assert "other" in run.data.keys()
            assert run.data["other"] == [1]

            # stop the run
            run.stop()
            assert run._dirty

            # resume the run
            run.start()
            assert run._dirty

            # add another value to the same list
            run.store("other", 2, push=True)
            assert run._dirty

            helper_validate_run_data(run.data, finished=False)
            assert not run._dirty
            assert "value" in run.data.keys()
            assert run.data["value"] == 1234
            assert "other" in run.data.keys()
            assert run.data["other"] == [1, 2]

            # validate the run one more time but make sure we have the
            # information about finishing time
            helper_validate_run_data(run.data, finished=True)
            assert not run._dirty

            run.stop()
