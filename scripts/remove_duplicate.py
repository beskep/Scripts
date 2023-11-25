from collections.abc import Iterable
from pathlib import Path

from loguru import logger


def _suffix(value: str):
    return value if value.startswith('.') else f'.{value}'


class DuplicateCleaner:
    def __init__(self, keep='webp', remove: Iterable[str] | None = None) -> None:
        self._keep = _suffix(keep)
        self._remove = tuple(_suffix(x) for x in remove) if remove else ()

    def files_to_keep(self, root: Path):
        return root.glob(f'*{self._keep}')

    def _is_duplicate(self, path: Path):
        if path.suffix == self._keep:
            return False

        return not self._remove or path.suffix in self._remove

    def duplicate_files(self, keep: Path):
        return (x for x in keep.parent.glob(f'{keep.stem}.*') if self._is_duplicate(x))

    def clean(self, root: Path):
        for keep in self.files_to_keep(root):
            files = list(self.duplicate_files(keep))

            if files:
                logger.info(
                    'Keep "{}" | Remove {}',
                    keep.name,
                    ', '.join(f'"{x.suffix}"' for x in files),
                )

            for file in files:
                file.unlink()


def remove_duplicate(
    src: str | Path,
    *,
    batch=True,
    keep: str = 'webp',
    remove: Iterable[str] | None = None,
):
    src = Path(src)

    subdirs = [x for x in src.iterdir() if x.is_dir()] if batch else [src]
    if not subdirs:
        logger.warning('No subdirs in "{}"', str(src))
        return

    cleaner = DuplicateCleaner(keep=keep, remove=remove)

    for subdir in subdirs:
        logger.info('Target="{}"', subdir.name)
        cleaner.clean(subdir)
