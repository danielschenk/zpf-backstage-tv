from pathlib import Path
import json
from unittest.mock import MagicMock
import pytest
from ..storage import PersistentThreadSafeObjectContextManager


@pytest.fixture
def tmp_json_path(tmp_path: Path) -> Path:
    return tmp_path / "test.json"


def test_persistance(tmp_json_path):
    data = {}
    update = {"foo": 42}
    manager = PersistentThreadSafeObjectContextManager(data, tmp_json_path)

    with manager as data:
        data.update(update)

    with open(tmp_json_path) as f:
        assert json.load(f) == update


@pytest.fixture
def mock_open(tmp_path):
    def side_effect(filename, mode):
        return open(tmp_path / filename, mode)

    return MagicMock(side_effect=side_effect)


def test_skip_identical_write(mock_open):
    data = {}
    update = {"foo": 42}
    filename = "foo.json"
    manager = PersistentThreadSafeObjectContextManager(data, filename, opener=mock_open)

    with manager as data:
        data.update(update)

    mock_open.assert_called_with(filename, "w")

    mock_open.reset_mock()
    with manager as data:
        pass

    mock_open.assert_called_once_with(filename, "r")
