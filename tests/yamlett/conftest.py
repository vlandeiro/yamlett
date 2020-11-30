import pytest
from contextlib import contextmanager


@pytest.fixture
@contextmanager
def nullcontext(enter_result=None):
    yield enter_result
