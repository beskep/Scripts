# ruff: noqa: UP007 PLR0913 FBT003

from enum import Enum
from pathlib import Path
from typing import Optional

import typer
from click.globals import get_current_context
from ffmpeg_normalize import FFmpegNormalize
from loguru import logger
from typer import Argument, Option

from scripts import utils
from scripts.author_size import author_size as _size
from scripts.count_archive import count_archive_files as _count
from scripts.image_resize import resize as _resize
from scripts.remove_duplicate import remove_duplicate as _duplicate
from scripts.ruff import RuffRules


def callback(
    *,
    debug: bool = Option(False, '--debug', rich_help_panel='Log level'),
    loglevel: int = Option(20, '--loglevel', '-l', rich_help_panel='Log level'),
):
    loglevel = min(10 if debug else 20, loglevel)
    utils.set_logger(level=loglevel)


def result_callback(*_args, **_kwargs):
    ctx = get_current_context()
    subcommand = ctx.invoked_subcommand

    notifier = utils.WindowsNotifier()
    notifier.send(title='Completed', message=f'Command: {subcommand}')
    logger.info('Completed {}', subcommand)


app = typer.Typer(callback=callback, result_callback=result_callback)
_dir: dict = {'show_default': False, 'exists': True, 'file_okay': False}


class RH:
    SRC = 'Source directory'
    DST = 'Destination directory'
    SIZE = 'Pixel size of smallest fitting dimension. `0` for original size.'
    OPTION = 'Additional options for ImageMagick.'
    PREFIX = 'Prefix of directory when `dst` is not set.'
    BATCH = 'Resize multiple directories.'
    CAPTURE = 'Capture ImageMagick output.'


class Prefix(Enum):
    original = 'original'
    resized = 'resized'


@app.command()
def resize(
    *,
    src: Path = Argument(..., help=RH.SRC, **_dir),
    dst: Optional[Path] = Argument(None, help=RH.DST, **_dir),
    size: Optional[int] = Option(2000, '--size', '-s', help=RH.SIZE),
    ext: str = Option('webp', '--ext', '-e', help='Output image extension.'),
    resize_filter: str = Option('Mitchell', '--resize-filter', '-f'),
    prefix: Prefix = Option('original', help=RH.PREFIX),
    batch: bool = Option(True, help=RH.BATCH),
    capture: bool = Option(True, help=RH.CAPTURE),
    option: Optional[str] = Option(None, help=RH.OPTION),
):
    _resize(
        src=src,
        dst=dst,
        size=size or 0,
        ext=ext,
        resize_filter=resize_filter,
        option=option,
        batch=batch,
        capture=capture,
        prefix_original=prefix is prefix.original,
    )


@app.command()
def duplicate(
    *,
    src: Path = Argument(..., **_dir),
    keep: str = Option('webp', help='Suffix of files to keep.'),
    remove: Optional[list[str]] = Option(
        None, help='Suffixes of duplicate files to remove.'
    ),
    batch: bool = Option(True),
):
    _duplicate(src=src, batch=batch, keep=keep, remove=remove)


class Visualization(Enum):
    bar = 'bar'
    gradient = 'gradient'


@app.command()
def size(
    *,
    path: Optional[Path] = Argument(None, exists=True),
    viz: Visualization = Option('bar'),
    na: bool = Option(False, '--na/--drop-na', help='Drop N/A'),
):
    _size(path=path, viz=viz.value, drop_na=not na)


@app.command()
def count(
    *,
    path=Argument(..., show_default=False, exists=True),
    classify: bool = Option(False),
    threshold: int = Option(100, '--threshold', '-t'),
):
    _count(path=path, classify=classify, threshold=threshold)


class AudioCodec(Enum):
    libopus = 'libopus'
    aac = 'aac'


@app.command()
def loudnorm(
    *,
    src: Path = Argument(..., show_default=False, exists=True),
    dst: Optional[Path] = Argument(None, show_default=True),
    codec: AudioCodec = Option('libopus', show_default=True),
    ext: str = Option('mkv', '--ext', '-e'),
    progress: bool = Option(default=True),
):
    if dst is None:
        dst = src.with_name(f'{src.stem}-loudnorm.{ext}')

    if dst.exists():
        raise FileExistsError(dst)

    logger.info('src="{}"', src)
    logger.info('dst="{}"', dst)

    normalize = FFmpegNormalize(audio_codec=codec.value, progress=progress)
    normalize.add_media_file(str(src), str(dst))
    normalize.run_normalization()

    if s := normalize.stats:
        utils.cnsl.print(s)


class RuffMode(Enum):
    linter = 'linter'
    setting = 'setting'


@app.command()
def ruff(
    *,
    conf: Optional[Path] = Option(None, show_default=True),
    mode: RuffMode = Option('setting', show_default=True),
):
    rules = RuffRules()

    if mode is RuffMode.linter:
        rules.print_linters()
    elif mode is RuffMode.setting:
        rules.print_settings(conf)


if __name__ == '__main__':
    app()
