import subprocess as sp
from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass, field
from itertools import chain
from pathlib import Path
from typing import Any, ClassVar, Literal

from loguru import logger
from rich.progress import track

from scripts.utils import FileSize


class ResizedDirectoryError(ValueError):
    pass


class NoImagesError(FileNotFoundError):
    def __init__(self, path, message='No images in "{}"') -> None:
        self.path = path
        self.message = message.format(path)
        super().__init__(self.message)


def _find_image_magick() -> Path:
    lst = sorted(Path(r'C:\Program Files').glob('ImageMagick*'))

    if len(lst) == 0:
        msg = 'ImageMagick Not Found'
        raise FileNotFoundError(msg)

    path = lst[-1].joinpath('magick.exe')

    if len(lst) > 1:
        logger.warning('다수의 ImageMagick 경로가 발견됨: {}', list(map(str, lst)))
        logger.info('ImageMagick="{}"', str(path))

    return path


def _bytes(size: float):
    fs = FileSize(size)
    return f'{fs.size: 6.1f} {fs.unit}'


@dataclass
class Config:
    format: str | None = None
    size: int | str = 0
    filter: str | None = 'Mitchell'
    shrink_only: bool = True
    quality: int | None = None
    option: str | None = None

    _size: str = field(init=False)

    def __post_init__(self):
        self._size = '100%' if self.size == 0 else f'{self.size}x{self.size}'
        if self.shrink_only:
            self._size = f'{self._size}^>'

    def args(self):
        values = [True, self.format, self.filter, self.quality, self.option]
        args: list[Any] = [
            ['-resize', self._size],
            ['-format', self.format],
            ['-filter', self.filter],
            ['-quality', str(self.quality)],
            [self.option],
        ]

        return chain.from_iterable(a for a, v in zip(args, values, strict=True) if v)


class _ImageMagicResizer(ABC):
    IMG_EXTS: ClassVar[set[str]] = {
        '.apng',
        '.avif',
        '.bmp',
        '.gif',
        '.jpeg',
        '.jpg',
        '.jxl',
        '.png',
        '.tiff',
        '.webp',
    }

    def __init__(
        self,
        path: str | Path | None = None,
        config: Config | None = None,
    ) -> None:
        self._magick = path or _find_image_magick()
        self._config = config or Config()

    @abstractmethod
    def resize(self, src: Path, dst: Path, *, capture=True) -> bool:
        pass

    @classmethod
    def find_images(cls, path: Path):
        return (x for x in path.iterdir() if x.suffix.lower() in cls.IMG_EXTS)

    def get_size(self, path):
        args = [self._magick, 'identify', '-ping', '-format', '%w %h', path]
        size = sp.check_output(args).decode()
        return [int(x) for x in size.split(' ')]

    def scaling_ratio(self, path: Path, size: int) -> Iterable[float]:
        for image in self.find_images(path):
            yield min(1.0, size / min(self.get_size(image)))

    def log(self, src: Path, ss: int, ds: int, size: int | str):
        if ds <= ss * 0.9:
            level = 'INFO'
        elif ds < ss:
            level = 'WARNING'
        else:
            level = 'ERROR'

        if not isinstance(size, int):
            msg = ''
        else:
            ratio = tuple(self.scaling_ratio(path=src, size=size))
            scaled = sum(1 for x in ratio if x > 0)
            total = len(ratio)

            avg = (
                f'(avg ratio {sum(ratio) / total:5.1%})'
                if scaled
                else '[red italic](NOT scaled)[/]'
            )
            msg = f'Scaled Images {scaled:>3d}/{total:>3d}={scaled / total:4.0%} {avg}'

        logger.log(
            level,
            'File Size {ss} -> {ds} ({r:6.1%}) | {msg}',
            ss=_bytes(ss),
            ds=_bytes(ds),
            r=ds / ss,
            msg=msg,
        )


class ConvertResizer(_ImageMagicResizer):
    def __init__(
        self,
        path: str | Path | None = None,
        config: Config | None = None,
    ) -> None:
        super().__init__(path=path, config=config)

        self._args = [self._magick, 'convert', *self._config.args()]

    def _convert(self, src: Path, dst: Path, *, capture=True):
        return sp.run([*self._args, src, dst], capture_output=capture, check=False)

    def resize(self, src: Path, dst: Path, *, capture=True):
        if not (images := sorted(self.find_images(src))):
            raise NoImagesError(src)

        ss, ds = 0, 0

        for image in track(images, transient=True):
            resized = dst.joinpath(image.name)
            if s := self._config.format:
                resized = resized.with_suffix(f'.{s}')

            out = self._convert(src=image, dst=resized, capture=capture)
            if not resized.exists():
                raise RuntimeError(out.stderr)

            ss += image.stat().st_size
            ds += resized.stat().st_size

        self.log(src=src, ss=ss, ds=ds, size=self._config.size)

        return ds < ss


class MogrifyResizer(_ImageMagicResizer):
    def __init__(
        self,
        path: str | Path | None = None,
        config: Config | None = None,
    ) -> None:
        super().__init__(path=path, config=config)

        self._args = [self._magick, 'mogrify', '-verbose', *self._config.args()]

    @staticmethod
    def _mogrify(args):
        with sp.Popen(args=args, stdout=sp.PIPE, stderr=sp.DEVNULL) as process:
            assert process.stdout is not None
            while process.poll() is None:
                yield process.stdout.readline().decode().strip()

    def resize(self, src: Path, dst: Path, *, capture=True):
        args = [*self._args, '-path', dst, f'{src}/*']
        logger.debug(args)

        if not (total := sum(1 for _ in self.find_images(src))):
            raise NoImagesError(src)

        if not capture:
            sp.run(args=args, check=False)
        else:
            for line in track(
                sequence=self._mogrify(args),
                total=total,
                transient=True,
            ):
                logger.debug(line)

        ss = sum(x.stat().st_size for x in src.glob('*'))
        ds = sum(x.stat().st_size for x in dst.glob('*'))
        self.log(src=src, ss=ss, ds=ds, size=self._config.size)

        return ds < ss


def _resize(  # noqa: PLR0913
    *,
    src: Path,
    dst: Path,
    subdir: Path,
    resizer: _ImageMagicResizer,
    capture: bool = True,
    prefix: Literal['original', 'resized'] = 'original',
):
    logger.info('Target="{}"', subdir.name)
    if not any(True for _ in resizer.find_images(subdir)):
        raise NoImagesError(subdir)

    if src != dst:
        s = subdir
        d = dst.joinpath(subdir.name)
    elif prefix == 'original':
        s = src.joinpath(f'≪ORIGINAL≫{subdir.name}')
        d = dst.joinpath(subdir.name)
        subdir.rename(s)
    elif prefix == 'resized':
        if subdir.name.startswith('≪RESIZED≫'):
            logger.info('Pass resized directory: {}', subdir.relative_to(src))
            raise ResizedDirectoryError

        s = subdir
        d = dst.joinpath(f'≪RESIZED≫{subdir.name}')
    else:
        raise ValueError(prefix)

    d.mkdir(exist_ok=True)
    reduced = resizer.resize(src=s, dst=d, capture=capture)

    if not reduced:
        d.rename(d.parent.joinpath(f'≪NotReduced≫{d.name}'))

    return reduced


def resize(  # noqa: PLR0913
    src: str | Path,
    dst: str | Path | None = None,
    *,
    format: str | None = None,  # noqa: A002
    size=0,
    filter='Mitchell',  # noqa: A002
    quality: int | None = None,
    option: str | None = None,
    batch=True,
    capture=True,
    prefix: Literal['original', 'resized'] = 'original',
):
    if not batch and dst is None:
        msg = 'batch 모드가 아닌 경우 dst를 지정해야 합니다.'
        raise ValueError(msg)

    src = Path(src)
    dst = src if dst is None else Path(dst)

    if batch:
        subdirs: Iterable[Path] = (x for x in src.iterdir() if x.is_dir())
    else:
        subdirs = [src]

    config = Config(
        format=format,
        filter=filter,
        size=size,
        shrink_only=True,
        quality=quality,
        option=option,
    )
    resizer = MogrifyResizer(config=config)

    logger.info('SRC="{}"', src)
    logger.info('DST="{}"', dst)
    logger.info(
        'size={!r} | format={!r} | filter={!r} | quality={!r} | option={!r}',
        size,
        format,
        filter,
        quality,
        option,
    )

    for subdir in subdirs:
        try:
            _resize(
                src=src,
                dst=dst,
                subdir=subdir,
                resizer=resizer,
                capture=capture,
                prefix=prefix,
            )
        except ResizedDirectoryError:
            pass
        except NoImagesError as e:
            logger.warning(str(e))
            continue
        except (OSError, RuntimeError, ValueError) as e:
            logger.exception(e)
            break
