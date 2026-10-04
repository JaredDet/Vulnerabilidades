import os
import shutil

from pathlib import Path
from tempfile import NamedTemporaryFile, mkdtemp


def create_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def create_temporary_directory(parent: Path, prefix: str) -> Path:
    create_directory(parent)
    return Path(mkdtemp(prefix=prefix, dir=parent)).resolve()


def delete_directory(path: Path) -> None:
    shutil.rmtree(path)


def save_data(path: Path, data: str) -> None:
    path.write_text(data, encoding="utf-8")


def save_data_atomic(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary = None

    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(data)

        os.replace(temporary, path)

    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def load_data(path: Path) -> str:
    return path.read_text(encoding="utf-8")
