import threading
from pathlib import Path
from typing import IO, Callable, Any, override, TypeVar, ContextManager
import json
import logging
from functools import partial

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


SerializedType = TypeVar("SerializedType")


class PersistentThreadSafeObjectContextManager[T](ThreadSafeObjectContextManager[T]):
    def __init__(
        self,
        object: T,
        file: Path | str,
        opener: OpenType = open,
        serializer: Callable[[T], SerializedType] = partial(json.dumps, indent=2),
        binary: bool = False,
    ):
        self.opener = opener
        self.serializer = serializer
        self.binary = binary
        self.persist = True
        self._object = object
        self._file = file
        self._lock = threading.Lock()

    @override
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if not self.persist:
                return
            write_if_needed(
                self._file, self.serializer(self._object), opener=self.opener, binary=self.binary
            )
        finally:
            self.persist = True
            super().__exit__(exc_type, exc_value, traceback)


class CachedStorage[T: (dict, list)]:
    def __init__(
        self,
        default: T,
        file: Path | str,
        opener: OpenType = open,
        serializer: Callable[[T], SerializedType] = partial(json.dumps, indent=2),
        deserializer: Callable[[SerializedType], T] = json.loads,
        ignore_init_errors: list[type] = [json.JSONDecodeError],
        binary: bool = False,
        validator: Callable[[T], bool] | None = None,
    ):
        self._lock = threading.Lock()

        object = default.copy()
        try:
            with opener(str(file), f"r{'b' if binary else ''}") as f:
                temp_object = deserializer(f.read())
                if validator is None or validator(temp_object):
                    object = temp_object
                else:
                    _logger.error(f"data validation failed for {file}, using default value")
                _logger.debug(f"loaded {file}")
        except FileNotFoundError:
            _logger.info(f"{file} not existing, using default value")
        except Exception as e:
            if type(e) not in ignore_init_errors:
                raise
            _logger.error(f"error deserializing existing data: {e}, using default value")

        self._manager = PersistentThreadSafeObjectContextManager(
            object=object, file=file, opener=opener, serializer=serializer, binary=binary
        )

    def open(self, persist=True) -> ContextManager[T]:
        with self._lock:
            self._manager.persist = persist
            return self._manager


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
