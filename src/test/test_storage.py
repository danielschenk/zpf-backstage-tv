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


def test_load_existing(tmp_json_path):
    data = {"foo": 42}
    with open(tmp_json_path, "w") as f:
        json.dump(data, f)

    manager = PersistentThreadSafeObjectContextManager(data, tmp_json_path)
    with manager as loaded_data:
        assert loaded_data == data


def test_initial_value_on_deserialize_error(tmp_json_path):
    data = {"foo": 42}
    with open(tmp_json_path, "w") as f:
        f.write(r'{"foo": ')

    manager = PersistentThreadSafeObjectContextManager(data, tmp_json_path)
    with manager as loaded_data:
        assert loaded_data == data


def test_raise_unknown_deserialize_error(tmp_json_path):
    data = {"foo": 42}
    with open(tmp_json_path, "w"):
        pass

    def deserializer(dummy: str) -> dict:
        raise ValueError

    with pytest.raises(ValueError):
        PersistentThreadSafeObjectContextManager(data, tmp_json_path, deserializer=deserializer)


default = {"foo": 42}
stored = {"foo": 43}


@pytest.mark.parametrize(
    "valid, expected",
    [
        (True, stored),
        (False, default),
    ],
)
def test_validator(tmp_json_path, valid, expected):
    with open(tmp_json_path, "w") as f:
        json.dump(stored, f)

    def validator(object):
        assert object == stored
        return valid

    manager = PersistentThreadSafeObjectContextManager(default, tmp_json_path, validator=validator)
    with manager as data:
        assert data == expected


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
