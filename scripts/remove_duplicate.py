from pathlib import Path
from typing import Iterable, Optional, Tuple

from loguru import logger

from .utils import StrPath


def _suffix(value: str):
    if not value.startswith('.'):
        value = f'.{value}'

    return value


class DuplicateCleaner:

    def __init__(self,
                 keep='webp',
                 remove: Optional[Tuple[str]] = None) -> None:
        self._keep = _suffix(keep)
        self._remove = tuple(_suffix(x) for x in remove) if remove else ()

    def files_to_keep(self, root: Path):
        return root.glob(f'*{self._keep}')

    def _is_duplicate(self, path: Path):
        if path.suffix == self._keep:
            return False

        if not self._remove:
            return True

        return path.suffix in self._remove

    def duplicate_files(self, keep: Path):
        return (x for x in keep.parent.glob(f'{keep.stem}.*')
                if self._is_duplicate(x))

    def clean(self, root: Path):
        for keep in self.files_to_keep(root):
            files = list(self.duplicate_files(keep))

            if files:
                logger.info('Keep "{}" | Remove {}', keep.name,
                            ', '.join(f'"{x.suffix}"' for x in files))

            for file in files:
                file.unlink()


def remove_duplicate(src: StrPath,
                     batch=True,
                     keep: str = 'webp',
                     remove: Optional[Tuple[str]] = None):
    src = Path(src)

    if batch:
        subdirs: Iterable = (x for x in src.iterdir() if x.is_dir())
    else:
        subdirs = [src]

    cleaner = DuplicateCleaner(keep=keep, remove=remove)

    for subdir in subdirs:
        logger.info('Target: "{}"', subdir.name)
        cleaner.clean(subdir)
