from pathlib import Path
import subprocess as sp
from typing import Iterable, Optional

from loguru import logger
from rich.progress import track

from .utils import console
from .utils import file_size_unit
from .utils import StrPath


class ResizedDirectoryError(ValueError):
    pass


class NoImagesError(FileNotFoundError):

    def __init__(self, path, message='No images in "{}"') -> None:
        self.path = path
        self.message = message.format(path)
        super().__init__(self.message)


def _find_image_magick() -> Path:
    lst = list(Path(r'C:\Program Files').glob('ImageMagick*'))

    if len(lst) == 0:
        raise FileNotFoundError('ImageMagick을 찾을 수 없음')

    if len(lst) > 1:
        logger.warning('다수의 ImageMagick 경로가 발견됨 {}', list(map(str, lst)))

    return lst[-1].joinpath('magick.exe')


def _size_arg(size: int):
    if size == 0:
        arg = '100%'
    else:
        arg = f'{size}x{size}'

    return arg


def _fs(size: float):
    s, u = file_size_unit(size)
    return f'{s: 6.1f} {u}'


def _log_size(src: int, dst: int, scaled=True):
    if dst <= src * 0.9:
        level = 'INFO'
    elif dst < src:
        level = 'WARNING'
    else:
        level = 'ERROR'

    msg = '' if scaled else ' ([red italic]NOT scaled[/])'
    logger.log(level, '{} -> {} ({:.1%}){}', _fs(src), _fs(dst), dst / src, msg)


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

    def resize(self, src: Path, dst: Path, size: int, capture=True) -> bool:
        raise NotImplementedError

    @classmethod
    def find_images(cls, path: Path):
        return (x for x in path.iterdir() if x.suffix.lower() in cls.IMG_EXTS)

    def get_size(self, path):
        cmd = f'{self._im} identify -ping -format "%w %h" "{path}"'
        size = sp.run(cmd, capture_output=True, check=True).stdout.decode()
        return [int(x) for x in size.split(' ')]

    def max_size(self, path):
        return max(min(self.get_size(x)) for x in self.find_images(path))


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

    def resize(self, src: Path, dst: Path, size: int, capture=True):
        images = sorted(self.find_images(src))
        if not images:
            raise NoImagesError(src)

        ss, ds = 0, 0
        size_arg = _size_arg(size)
        for image in track(images, console=console, transient=True):
            resized = dst.joinpath(image.name)
            if self._format:
                resized = resized.with_suffix(f'.{self._format}')

            out = self._convert(src=image,
                                dst=resized,
                                size=size_arg,
                                capture=capture)
            if not resized.exists():
                raise RuntimeError(out.stderr)

            ss += image.stat().st_size
            ds += resized.stat().st_size

        scaled = size != 0 and self.max_size(src) > size
        _log_size(src=ss, dst=ds, scaled=scaled)

        return ds < ss


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

    def resize(self, src: Path, dst: Path, size: int, capture=True):
        args = self._args.format(src=src.as_posix(),
                                 dst=dst.as_posix(),
                                 size=_size_arg(size))
        logger.debug(args)

        images_count = sum(1 for _ in self.find_images(src))
        if not images_count:
            raise NoImagesError(src)

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
        scaled = size != 0 and self.max_size(src) > size
        _log_size(src=ss, dst=ds, scaled=scaled)

        return ds < ss


def _resize(src: Path, dst: Path, subdir: Path, resizer: _ImageMagicResizer,
            size: int, prefix_original: bool, capture: bool):
    logger.info('Target: "{}"', subdir.name)
    if not any(True for _ in resizer.find_images(subdir)):
        raise NoImagesError(subdir)

    if src != dst:
        s = subdir
        d = dst.joinpath(subdir.name)
    elif prefix_original:
        s = src.joinpath(f'≪ORIGINAL≫{subdir.name}')
        d = dst.joinpath(subdir.name)
        subdir.rename(s)
    else:
        if subdir.name.startswith('≪RESIZED≫'):
            logger.info('Pass resized directory')
            raise ResizedDirectoryError

        s = subdir
        d = dst.joinpath(f'≪RESIZED≫{subdir.name}')

    d.mkdir(exist_ok=True)

    reduced = resizer.resize(src=s, dst=d, size=size, capture=capture)
    if not reduced:
        d.rename(d.parent.joinpath(f'≪NotReduced≫{d.name}'))

    return reduced


def resize(src: StrPath,
           dst: Optional[StrPath] = None,
           size=2000,
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

    resizer = MogrifyResizer(ext=ext,
                             resize_filter=resize_filter,
                             option=option)

    logger.info('SRC: "{}"', src)
    logger.info('DST: "{}"', dst)
    logger.info('Output size: "{}" | ext: "{}" | filter: "{}" | option: "{}"',
                size, ext, resize_filter, option)

    for subdir in subdirs:
        try:
            _resize(src=src,
                    dst=dst,
                    subdir=subdir,
                    resizer=resizer,
                    size=size,
                    prefix_original=prefix_original,
                    capture=capture)
        except ResizedDirectoryError:
            pass
        except NoImagesError as e:
            logger.warning(str(e))
            continue
        except (OSError, RuntimeError, ValueError) as e:
            logger.catch(e, reraise=True)  # type: ignore
