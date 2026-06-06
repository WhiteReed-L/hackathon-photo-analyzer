import uuid
from pathlib import Path

import aiofiles

import config


class LocalAssetStorage:
    """Local filesystem storage adapter for uploaded and generated assets."""

    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or config.UPLOAD_DIR
        self.base_dir.mkdir(exist_ok=True)

    def make_filename(self, suffix: str = ".bin", prefix: str = "") -> str:
        if not suffix.startswith("."):
            suffix = "." + suffix
        return f"{prefix}{uuid.uuid4()}{suffix}"

    def path_for(self, filename: str) -> Path:
        if Path(filename).name != filename:
            raise ValueError("Invalid filename")
        return self.base_dir / filename

    async def save_bytes(self, content: bytes, suffix: str = ".bin", prefix: str = "") -> tuple[str, Path]:
        filename = self.make_filename(suffix=suffix, prefix=prefix)
        path = self.path_for(filename)
        async with aiofiles.open(path, "wb") as f:
            await f.write(content)
        return filename, path


storage = LocalAssetStorage()
