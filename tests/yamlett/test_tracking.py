from yamlett.tracking import Run


def test_run_start_stop(tmp_path):
    sqlite_path = tmp_path / "yamlett.db"

    # initialize run
    run = Run(sqlite_path=sqlite_path)
    assert run._data is None
    assert run._dirty

    # store a value
    run.store("value", 1234)
    assert run._dirty

    # retrieve twice to check caching works okay
    for i in range(2):
        assert not run._dirty
        assert "value" in run.data.keys()
        assert run.data["value"] == 1234

    # validate the run one more time but make sure we have the
    # information about finishing time
    assert not run._dirty
