from pathlib import Path
import subprocess as sp
from typing import Iterable, Optional, Union

from loguru import logger
from rich.progress import track

from .utils import console
from .utils import file_size_string as fss
from .utils import StrPath


def _find_image_magick() -> Path:
    lst = list(Path(r'C:\Program Files').glob('ImageMagick*'))

    if len(lst) == 0:
        raise OSError('ImageMagick을 찾을 수 없음')

    if len(lst) > 1:
        logger.warning(
            '다수의 ImageMagick 경로가 발견됨 {}',
            [x.as_posix() for x in lst],
        )

    return lst[-1].joinpath('magick.exe')


def _find_files(path: Path, exts):
    return (x for x in path.iterdir() if x.suffix in exts)


class _ImageMagicResizer:
    IMG_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp'}

    def __init__(self,
                 path: Optional[StrPath] = None,
                 ext: Optional[str] = None,
                 resize_filter='Mitchell',
                 shrink_only=True) -> None:
        if path is None:
            path = _find_image_magick()

        self._im = path
        self._filter = resize_filter
        self._shrink = '^>' if shrink_only else ''
        self._format = ext

    def resize(self, src: Path, dst: Path, size, capture=True):
        raise NotImplementedError


class ConvertResizer(_ImageMagicResizer):

    def __init__(self,
                 path: Optional[StrPath] = None,
                 ext: Optional[str] = None,
                 resize_filter='Mitchell',
                 shrink_only=True) -> None:
        super().__init__(path=path,
                         ext=ext,
                         resize_filter=resize_filter,
                         shrink_only=shrink_only)

        self._args = (f'{self._im} convert -resize {{size}}{self._shrink} '
                      f'-filter {self._filter} "{{src}}" "{{dst}}"')

    def _convert(self, src: Path, dst: Path, size, capture=True):
        args = self._args.format(src=src.as_posix(),
                                 dst=dst.as_posix(),
                                 size=size)

        return sp.run(args, capture_output=capture, check=False)

    def resize(self, src: Path, dst: Path, size, capture=True):
        images = sorted(_find_files(path=src, exts=self.IMG_EXTS))
        if not images:
            logger.warning('No images in "{}"', src)

        ss, ds = 0.0, 0.0
        for image in track(images, console=console, transient=True):
            resized = dst.joinpath(image.name)
            if self._format:
                resized = resized.with_suffix(f'.{self._format}')

            out = self._convert(src=image,
                                dst=resized,
                                size=size,
                                capture=capture)
            if not resized.exists():
                raise RuntimeError(out.stderr)

            ss += image.stat().st_size
            ds += resized.stat().st_size

        logger.info('{} -> {} ({:.1f}%)', fss(ss), fss(ds), (100.0 * ds / ss))


class MogrifyResizer(_ImageMagicResizer):

    def __init__(self,
                 path: Optional[StrPath] = None,
                 ext: Optional[str] = None,
                 resize_filter='Mitchell',
                 shrink_only=True) -> None:
        super().__init__(path=path,
                         ext=ext,
                         resize_filter=resize_filter,
                         shrink_only=shrink_only)

        fmt = '' if ext is None else f'-format {ext}'
        self._args = (f'{self._im} mogrify -verbose {fmt} '
                      f'-resize {{size}}{self._shrink} -filter {self._filter} '
                      f'-path "{{dst}}" "{{src}}/*"')

    @staticmethod
    def _mogrify(args):
        with sp.Popen(args=args, stdout=sp.PIPE, stderr=sp.DEVNULL) as process:
            while process.poll() is None:
                yield process.stdout.readline().decode().strip()

    def resize(self, src: Path, dst: Path, size, capture=True):
        args = self._args.format(src=src.as_posix(),
                                 dst=dst.as_posix(),
                                 size=size)
        logger.debug(args)

        if not capture:
            sp.run(args=args, check=False)
        else:
            files_count = sum(
                1 for _ in _find_files(path=src, exts=self.IMG_EXTS))
            for line in track(sequence=self._mogrify(args),
                              total=files_count,
                              console=console,
                              transient=True):
                logger.debug(line)

        ss = sum(x.stat().st_size for x in src.glob('*'))
        ds = sum(x.stat().st_size for x in dst.glob('*'))
        logger.info('{} -> {} ({:.1f}%)', fss(ss), fss(ds), (100 * ds / ss))


def resize(src,
           dst=None,
           size: Union[int, str] = 2000,
           ext=None,
           resize_filter='Mitchell',
           batch=True,
           capture=True,
           prefix_original=True,
           mogrify=True):
    if not batch and dst is None:
        raise ValueError('batch 모드가 아닌 경우 dst를 지정해야 합니다.')

    src = Path(src)
    dst = src if dst is None else Path(dst)

    if batch:
        subdirs: Iterable = (x for x in src.iterdir() if x.is_dir())
    else:
        subdirs = [src]

    if isinstance(size, int):
        size = f'{size}x{size}'

    Resizer = MogrifyResizer if mogrify else ConvertResizer
    resizer = Resizer(ext=ext, resize_filter=resize_filter)

    logger.info('SRC: "{}"', src)
    logger.info('DST: "{}"', dst)
    logger.info('Output size: "{}" | ext: "{}" | filter: "{}"', size, ext,
                resize_filter)

    for subdir in subdirs:
        if src != dst:
            s = subdir
            d = dst.joinpath(subdir.name)
        elif prefix_original:
            s = src.joinpath(f'[ORIGINAL]{subdir.name}')
            d = dst.joinpath(subdir.name)
            subdir.rename(s)
        else:
            if subdir.name.startswith('[RESIZED]'):
                continue

            s = subdir
            d = dst.joinpath(f'[RESIZED]{subdir.name}')

        logger.info('Target: "{}"', subdir.name)
        d.mkdir(exist_ok=True)
        resizer.resize(src=s, dst=d, size=size, capture=capture)
