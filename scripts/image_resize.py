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
        logger.warning('다수의 ImageMagick 경로가 발견됨 {}', list(map(str, lst)))

    return lst[-1].joinpath('magick.exe')


def _find_files(path: Path, exts):
    return (x for x in path.iterdir() if x.suffix in exts)


def _log_size(src: int, dst: int):
    logger.info('{} -> {} ({:.1%})', fss(src), fss(dst), dst / src)


class _ImageMagicResizer:
    IMG_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp'}

    def __init__(self,
                 path: Optional[StrPath] = None,
                 ext: Optional[str] = None,
                 resize_filter='Mitchell',
                 shrink_only=True,
                 option: Optional[str] = None) -> None:
        if path is None:
            path = _find_image_magick()

        self._im = path
        self._filter = resize_filter
        self._shrink = '^>' if shrink_only else ''
        self._format = ext
        self._option = option or ''

    def resize(self, src: Path, dst: Path, size, capture=True):
        raise NotImplementedError

    def _find_images(self, path: Path):
        return _find_files(path=path, exts=self.IMG_EXTS)


class ConvertResizer(_ImageMagicResizer):

    def __init__(self,
                 path: Optional[StrPath] = None,
                 ext: Optional[str] = None,
                 resize_filter='Mitchell',
                 shrink_only=True,
                 option: Optional[str] = None) -> None:
        super().__init__(path=path,
                         ext=ext,
                         resize_filter=resize_filter,
                         shrink_only=shrink_only,
                         option=option)

        self._args = (f'{self._im} convert -resize {{size}}{self._shrink} '
                      f'-filter {self._filter} {option} "{{src}}" "{{dst}}"')

    def _convert(self, src: Path, dst: Path, size, capture=True):
        args = self._args.format(src=src.as_posix(),
                                 dst=dst.as_posix(),
                                 size=size)

        return sp.run(args, capture_output=capture, check=False)

    def resize(self, src: Path, dst: Path, size, capture=True):
        images = sorted(self._find_images(src))
        if not images:
            logger.warning('No images in "{}"', src)
            return

        ss, ds = 0, 0
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

        _log_size(src=ss, dst=ds)


class MogrifyResizer(_ImageMagicResizer):

    def __init__(self,
                 path: Optional[StrPath] = None,
                 ext: Optional[str] = None,
                 resize_filter='Mitchell',
                 shrink_only=True,
                 option: Optional[str] = None) -> None:
        super().__init__(path=path,
                         ext=ext,
                         resize_filter=resize_filter,
                         shrink_only=shrink_only,
                         option=option)

        fmt = '' if ext is None else f'-format {ext}'
        self._args = (f'{self._im} mogrify -verbose {fmt} '
                      f'-resize {{size}}{self._shrink} '
                      f'-filter {self._filter} {option} '
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

        images_count = sum(1 for _ in self._find_images(src))
        if not images_count:
            logger.warning('No images in "{}"', src)
            return

        if not capture:
            sp.run(args=args, check=False)
        else:
            for line in track(sequence=self._mogrify(args),
                              total=images_count,
                              console=console,
                              transient=True):
                logger.debug(line)

        ss = sum(x.stat().st_size for x in src.glob('*'))
        ds = sum(x.stat().st_size for x in dst.glob('*'))
        _log_size(src=ss, dst=ds)


def _resize(src: Path, dst: Path, subdir: Path, resizer: _ImageMagicResizer,
            size: str, prefix_original: bool, capture: bool):
    if src != dst:
        s = subdir
        d = dst.joinpath(subdir.name)
    elif prefix_original:
        s = src.joinpath(f'[ORIGINAL]{subdir.name}')
        d = dst.joinpath(subdir.name)
        subdir.rename(s)
    else:
        if subdir.name.startswith('[RESIZED]'):
            return

        s = subdir
        d = dst.joinpath(f'[RESIZED]{subdir.name}')

    logger.info('Target: "{}"', subdir.name)
    d.mkdir(exist_ok=True)
    resizer.resize(src=s, dst=d, size=size, capture=capture)


def resize(src: StrPath,
           dst: Optional[StrPath] = None,
           size: Union[int, str] = 2000,
           ext: Optional[str] = None,
           resize_filter='Mitchell',
           option: Optional[str] = None,
           batch=True,
           capture=True,
           prefix_original=True):
    if not batch and dst is None:
        raise ValueError('batch 모드가 아닌 경우 dst를 지정해야 합니다.')

    src = Path(src)
    dst = src if dst is None else Path(dst)

    if batch:
        subdirs: Iterable = (x for x in src.iterdir() if x.is_dir())
    else:
        subdirs = [src]

    if size == 0:
        size = '100%'
    elif isinstance(size, int):
        size = f'{size}x{size}'

    resizer = MogrifyResizer(ext=ext,
                             resize_filter=resize_filter,
                             option=option)

    logger.info('SRC: "{}"', src)
    logger.info('DST: "{}"', dst)
    logger.info('Output size: "{}" | ext: "{}" | filter: "{}" | option: "{}"',
                size, ext, resize_filter, option)

    for subdir in subdirs:
        _resize(src=src,
                dst=dst,
                subdir=subdir,
                resizer=resizer,
                size=size,
                prefix_original=prefix_original,
                capture=capture)
