# ruff: noqa: DOC501

from pathlib import Path
from typing import Annotated, Literal

import rich
from cyclopts import App, Group, Parameter
from ffmpeg_normalize import FFmpegNormalize
from loguru import logger

from scripts import utils
from scripts.author_size import author_size as _size
from scripts.count_archive import count_archive_files as _count
from scripts.image_resize import resize as _resize
from scripts.remove_duplicate import remove_duplicate as _duplicate
from scripts.rptl import RenpyTranslation
from scripts.ruff import RuffRules

app = App(help_format='markdown')
app.meta.group_parameters = Group('Options', sort_key=0)


@app.meta.default
def launcher(
    *tokens: Annotated[str, Parameter(show=False, allow_leading_hyphen=True)],
    debug: Annotated[bool, Parameter(name=['--debug', '-d'], negative=[])] = False,
):
    utils.set_logger(level=10 if debug else 20)

    app(tokens)

    if tokens:
        notifier = utils.WindowsNotifier()
        notifier.send(title=f'Completed {tokens[0]}')
        logger.info('Completed {}', tokens[0])


@app.command(group='Images')
def resize(  # noqa: PLR0913
    src: Path,
    dst: Path | None = None,
    *,
    format_: Annotated[str, Parameter('--format')] = 'webp',
    size: int = 0,
    filter_: Annotated[str, Parameter('--filter')] = 'Mitchell',
    quality: int | None = None,
    option: str | None = None,
    batch: bool = True,
    prefix: Literal['original', 'resized'] = 'original',
    capture: bool = True,
):
    """
    ImageMagick 이용 영상파일 해상도 변환, 압축.

    Parameters
    ----------
    src : Path
        대상 경로.
    dst : Path | None, optional
        저장 경로. 미입력 시 `src`와 같은 경로.
    format_ : Annotated[str, Parameter, optional
        변환되는 영상 형식. jpg, webp, avif, ...
    size : int, optional
        변환되는 영상의 가장 작은 dimension 크기. 0이면 원본 크기 보존.
    filter_ : Annotated[str, Parameter, optional
        크기 변환 필터. Mitchell, Hermite, Lanczos, ...
    quality : int | None, optional
        영상 품질 (0-100).
    option : str | None, optional
        ImageMagick 부가 옵션.
    batch : bool, optional
        여러 폴더 일괄 변환.
    prefix : Literal['original', 'resized'], optional
        batch 변환 시 prefix를 적용할 대상.
    capture : bool, optional
        ImageMagick 출력 캡처.
    """
    _resize(
        src=src,
        dst=dst,
        format=format_,
        size=size,
        filter=filter_,
        quality=quality,
        option=option,
        batch=batch,
        capture=capture,
        prefix=prefix,
    )


@app.command(group='Images')
def duplicate(
    src: Path,
    *,
    keep: str = 'webp',
    remove: list[str] | None = None,
    batch: bool = True,
):
    """확장자가 다르고 중복된 영상 파일 삭제."""
    if not src.is_dir():
        raise NotADirectoryError(src)

    _duplicate(src=src, batch=batch, keep=keep, remove=remove)


@app.command(group='Images')
def size(
    path: Path | None = None,
    *,
    viz: Literal['bar', 'gradient'] = 'bar',
    na: Annotated[bool, Parameter(negative_bool='--drop-')] = False,
):
    """폴더, 작가별 용량 및 폴더 개수 시각화."""
    _size(path=path, viz=viz, drop_na=not na)


@app.command
def count_archive(
    path: Path,
    *,
    classify: bool = False,
    threshold: int = 100,
):
    """압축파일 내 파일 개수 체크."""
    _count(path=path, classify=classify, threshold=threshold)


@app.command
def loudnorm(
    src: Path,
    *,
    dst: Path | None = None,
    codec: Literal['libopus', 'aac'] = 'libopus',
    ext: str = 'mkv',
    progress: bool = True,
):
    """ffmpeg-normalize."""
    dst = dst or src.with_name(f'{src.stem}-loudnorm.{ext}')
    if dst.exists():
        raise FileExistsError(dst)

    logger.info('src="{}"', src)
    logger.info('dst="{}"', dst)

    normalize = FFmpegNormalize(audio_codec=codec, progress=progress)
    normalize.add_media_file(str(src), str(dst))
    normalize.run_normalization()

    if s := normalize.stats:
        rich.print(s)


@app.command
def rptl(path: Path, language: str = 'Korean'):
    """
    Renpy 번역 원문·번역어 동시 출력

    Parameters
    ----------
    path : Path
        게임 경로.
    language : str, optional
        번역 대상 언어.
    """
    RenpyTranslation(path=path, language=language).execute()


@app.command
def ruff(
    *,
    conf: Path | None = None,
    mode: Literal['linter', 'setting'] = 'setting',
):
    """ruff linter/setting"""
    rules = RuffRules()

    if mode == 'linter':
        rules.print_linters()
    elif mode == 'setting':
        rules.print_settings(conf)
    else:
        raise ValueError(mode)


if __name__ == '__main__':
    app.meta()
