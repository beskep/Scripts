from logging import LogRecord
from typing import ClassVar

import rich
from loguru import logger
from rich import progress
from rich.highlighter import ReprHighlighter
from rich.logging import RichHandler
from rich.theme import Theme


class _Highlighter(ReprHighlighter):
    highlights = [*ReprHighlighter.highlights, r'(?P<vb>\|)']  # noqa: RUF012


class _RichHandler(RichHandler):
    LEVELS: ClassVar[dict[str, int]] = {
        'TRACE': 5,
        'DEBUG': 10,
        'INFO': 20,
        'SUCCESS': 25,
        'WARNING': 30,
        'ERROR': 40,
        'CRITICAL': 50,
    }
    BLANK_NO = 21
    _NEW_LVLS: ClassVar[dict[int, str]] = {5: 'TRACE', 25: 'SUCCESS', BLANK_NO: ''}

    def emit(self, record: LogRecord) -> None:
        if name := self._NEW_LVLS.get(record.levelno, None):
            record.levelname = name

        return super().emit(record)


cnsl = rich.get_console()
cnsl.push_theme(Theme({'logging.level.success': 'blue', 'repr.vb': 'bold blue'}))


def set_logger(level: int | str = 20, *, rich_tracebacks=False, **kwargs):
    if isinstance(level, str):
        try:
            level = _RichHandler.LEVELS[level.upper()]
        except KeyError as e:
            msg = f'`{level}` not in {list(_RichHandler.LEVELS.keys())}'
            raise KeyError(msg) from e

    logger.remove()

    _handler = _RichHandler(
        console=cnsl,
        highlighter=_Highlighter(),
        markup=True,
        log_time_format='[%X]',
        rich_tracebacks=rich_tracebacks,
    )
    logger.add(_handler, level=level, format='{message}', **kwargs)
    logger.add(
        'script.log',
        level=min(20, level),
        rotation='1 month',
        retention='1 year',
        encoding='UTF-8-SIG',
    )


class Progress(progress.Progress):
    @classmethod
    def get_default_columns(cls) -> tuple[progress.ProgressColumn, ...]:
        return (
            progress.TextColumn('[progress.description]{task.description}'),
            progress.BarColumn(bar_width=60),
            progress.MofNCompleteColumn(),
            progress.TaskProgressColumn(),
            progress.TimeRemainingColumn(compact=True, elapsed_when_finished=True),
        )
