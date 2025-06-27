import threading
from pathlib import Path
from typing import IO, Callable, Any, override
import json
import logging

_logger = logging.getLogger(__name__)

OpenType = Callable[[str, str], IO[Any]]


class ThreadSafeObjectContextManager[T]:
    def __init__(self, object: T):
        self._object = object
        self._lock = threading.Lock()

    def __enter__(self) -> T:
        self._lock.acquire()
        return self._object

    def __exit__(self, exc_type, exc_value, traceback):
        self._lock.release()


class PersistentDictContextManager[KeyType, ValueType](
    ThreadSafeObjectContextManager[dict[KeyType, ValueType]]
):
    def __init__(self, dict: dict[KeyType, ValueType], file: Path | str, opener: OpenType = open):
        super().__init__(dict)
        self.opener = opener
        self._file = file
        self._dict = dict

    @override
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            write_if_needed(self._file, json.dumps(self._dict, indent=2), opener=self.opener)
        finally:
            super().__exit__(exc_type, exc_value, traceback)


def write_if_needed(file: Path | str, new_contents, binary=False, opener: OpenType = open):
    optional_b = "b" if binary else ""
    try:
        with opener(str(file), f"r{optional_b}") as f:
            if new_contents == f.read():
                _logger.debug(f"contents of {file} unchanged, skipping write")
                return
    except FileNotFoundError:
        _logger.debug(f"creating {file}")

    _logger.debug(f"writing {file}")
    with opener(str(file), f"w{optional_b}") as f:
        f.write(new_contents)
