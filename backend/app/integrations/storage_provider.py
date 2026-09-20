from abc import ABC, abstractmethod
from pathlib import Path
from uuid import uuid4

class StorageProvider(ABC):
    @abstractmethod
    def store(self, file_data: bytes, file_name: str, metadata=None) -> str:
        raise NotImplementedError
    @abstractmethod
    def retrieve(self, key: str) -> bytes:
        raise NotImplementedError
    @abstractmethod
    def delete(self, key: str) -> bool:
        raise NotImplementedError
    @abstractmethod
    def exists(self, key: str) -> bool:
        raise NotImplementedError

class LocalStorageProvider(StorageProvider):
    def __init__(self, storage_path):
        self.root = Path(storage_path).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key):
        if not key or Path(key).is_absolute() or ":" in key or "\\" in key or ".." in Path(key).parts:
            raise ValueError("Invalid storage key")
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root) or path == self.root:
            raise ValueError("Invalid storage key")
        return path

    def store(self, file_data, file_name, metadata=None):
        from app.config.settings import settings
        if len(file_data) > settings.MAX_FILE_SIZE:
            raise ValueError("File too large")
        # Untrusted original names never become filesystem paths.
        key = uuid4().hex
        with self._path(key).open("xb") as stream:
            stream.write(file_data)
        return key

    def retrieve(self, key):
        return self._path(key).read_bytes()

    def delete(self, key):
        path = self._path(key)
        if not path.is_file():
            return False
        path.unlink()
        return True

    def exists(self, key):
        return self._path(key).is_file()

    def get_url(self, key):
        raise NotImplementedError("Media delivery requires an authenticated download route")
