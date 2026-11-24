import pytest

from app.input import load
from app.main import create_app


@pytest.fixture
def dirty():
    return load('dirty')


@pytest.fixture
def clean():
    return load('clean')


@pytest.fixture
def client(tmp_path):
    return create_app(tmp_path / 'archive').test_client()
