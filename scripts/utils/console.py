from loguru import logger
from rich.console import Console
from rich.highlighter import ReprHighlighter
from rich.logging import RichHandler
from rich.theme import Theme


class CustomHighlighter(ReprHighlighter):
    highlights = [*ReprHighlighter.highlights, r'(?P<vb>\|)']  # noqa: RUF012


theme = Theme({'logging.level.success': 'blue', 'repr.vb': 'bold blue'})
cnsl = Console(theme=theme)
_handler = RichHandler(
    console=cnsl,
    highlighter=CustomHighlighter(),
    markup=True,
    log_time_format='[%X]',
)
_LEVELS = {
    'TRACE': 5,
    'DEBUG': 10,
    'INFO': 20,
    'SUCCESS': 25,
    'WARNING': 30,
    'ERROR': 40,
    'CRITICAL': 50,
}


def set_logger(level: int | str = 20):
    if isinstance(level, str):
        try:
            level = _LEVELS[level.upper()]
        except KeyError as e:
            msg = f'`{level}` not in {list(_LEVELS.keys())}'
            raise KeyError(msg) from e

    logger.remove()
    logger.add(_handler, level=level, format='{message}', backtrace=False)
    logger.add(
        'script.log',
        level=min(20, level),
        rotation='1 month',
        retention='1 year',
        encoding='UTF-8-SIG',
    )
