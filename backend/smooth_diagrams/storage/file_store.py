"""Where uploaded files live. Only this module knows whether that is a folder or a bucket."""

import asyncio
from pathlib import Path
from typing import Protocol


class FileStore(Protocol):
	"""Keeps the bytes of uploaded files under keys the database remembers."""

	async def save(self, storage_key: str, content: bytes) -> None:
		"""Store a file under a key."""
		...

	async def read(self, storage_key: str) -> bytes:
		"""Return the file stored under a key."""
		...

	async def delete(self, storage_key: str) -> None:
		"""Remove the file stored under a key, if there is one."""
		...


class LocalFileStore:
	"""Keeps files in one folder on this computer."""

	def __init__(self, root: Path) -> None:
		self._root = root

	def _path(self, storage_key: str) -> Path:
		"""Return the path of a key, refusing keys that would leave the folder."""
		if Path(storage_key).name != storage_key:
			raise ValueError("A storage key must be a plain file name")
		return self._root / storage_key

	async def save(self, storage_key: str, content: bytes) -> None:
		"""Store a file under a key."""
		path = self._path(storage_key)
		await asyncio.to_thread(self._root.mkdir, parents=True, exist_ok=True)
		await asyncio.to_thread(path.write_bytes, content)

	async def read(self, storage_key: str) -> bytes:
		"""Return the file stored under a key."""
		return await asyncio.to_thread(self._path(storage_key).read_bytes)

	async def delete(self, storage_key: str) -> None:
		"""Remove the file stored under a key, if there is one."""
		await asyncio.to_thread(self._path(storage_key).unlink, missing_ok=True)
