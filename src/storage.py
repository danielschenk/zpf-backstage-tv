import threading
from pathlib import Path
from typing import IO, Callable, Any, ContextManager
import json
import logging
from functools import partial

_logger = logging.getLogger(__name__)


class ThreadSafeObjectContextManager[T]:
    def __init__(self, object: T, lock=threading.Lock()):
        self._object = object
        self._lock = lock

    def __enter__(self) -> T:
        self._lock.acquire()
        return self._object

    def __exit__(self, exc_type, exc_value, traceback):
        self._lock.release()


OpenType = Callable[[str, str], IO[Any]]


class CachedStorage[DataType: (dict, list), SerializedType]:
    def __init__(
        self,
        default: DataType,
        file: Path | str,
        opener: OpenType = open,
        serializer: Callable[[DataType], SerializedType] = partial(json.dumps, indent=2),
        deserializer: Callable[[SerializedType], DataType] = json.loads,
        ignore_init_errors: list[type[Exception]] = [json.JSONDecodeError],
        binary: bool = False,
        validator: Callable[[DataType], bool] = lambda _: True,
    ):
        self.opener = opener
        self.serializer = serializer
        self.binary = binary
        self._file = file

        self._object = default.copy()
        need_save = True
        try:
            with opener(str(file), f"r{'b' if binary else ''}") as f:
                temp_object = deserializer(f.read())
            if validator(temp_object):
                self._object = temp_object
                need_save = False
            else:
                _logger.error(f"data validation failed for {file}, using default value")
            _logger.debug(f"loaded {file}")
        except FileNotFoundError:
            _logger.info(f"{file} not existing, using default value")
        except Exception as e:
            if type(e) not in ignore_init_errors:
                raise
            _logger.error(f"error deserializing existing data: {e}, using default value")

        self._manager = ThreadSafeObjectContextManager(object=self._object, lock=threading.RLock())

        if need_save:
            self.save()

    def lock(self) -> ContextManager[DataType]:
        return self._manager

    def save(self):
        # we use an RLock so this should be fine both outside and inside of the lock
        with self._manager:
            write_if_needed(
                self._file, self.serializer(self._object), opener=self.opener, binary=self.binary
            )


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
