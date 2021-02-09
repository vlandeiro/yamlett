from typing import Any, Dict

import mongomock
import pymongo
import pytest

from yamlett.tracking import Experiment, Run
from yamlett.utils_test import nullcontext


@pytest.mark.parametrize(
    "name, mongo_options, patch, context",
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
def test_experiment(name, mongo_options, patch, context):
    context = context or nullcontext()
    with context:
        with patch:
            experiment = Experiment(name=name, mongo_options=mongo_options)
            obj = {"_id": 1, "value": 1234}
            experiment.insert_one(obj)
            assert experiment.find_one({"_id": 1}) == obj

            # fail on invalid methods for a pymongo.Collection object
            with pytest.raises(AttributeError):
                print(experiment.foo_bar_machin_truc)


def helper_validate_run_data(result: Dict[str, Any]):
    assert "_id" in result.keys()
    # assert {"created_at", "last_modified_at"} <= set(result["_yamlett"].keys())


@pytest.mark.parametrize(
    "experiment_name, mongo_options, patch, context",
    [("runs", {}, mongomock.patch(), None)],
)
def test_run_start_stop(experiment_name, mongo_options, patch, context):
    context = context or nullcontext()

    with context:
        with patch:
            # initialize run
            run = Run(experiment_name=experiment_name, mongo_options=mongo_options)
            assert run._data is None
            assert run._dirty

            # store a value
            run.store("value", 1234)
            assert run._dirty

            # retrieve twice to check caching works okay
            for i in range(2):
                helper_validate_run_data(run.data())
                assert not run._dirty
                assert "value" in run.data().keys()
                assert run.data()["value"] == 1234

            # add another value by creating a list
            run.store("other", 1, push=True)
            assert run._dirty

            helper_validate_run_data(run.data())
            assert not run._dirty
            assert "value" in run.data().keys()
            assert run.data()["value"] == 1234
            assert "other" in run.data().keys()
            assert run.data()["other"] == [1]

            run.store("other", 2, push=True)
            assert run._dirty

            helper_validate_run_data(run.data())
            assert not run._dirty
            assert "value" in run.data().keys()
            assert run.data()["value"] == 1234
            assert "other" in run.data().keys()
            assert run.data()["other"] == [1, 2]

            # validate the run one more time but make sure we have the
            # information about finishing time
            helper_validate_run_data(run.data())
            assert not run._dirty
