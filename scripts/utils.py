from os import PathLike
from typing import Union

from loguru import logger
from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

StrPath = Union[str, PathLike]
console = Console(theme=Theme({'logging.level.success': 'blue'}))
_handler = RichHandler(console=console, log_time_format='[%X]')
_levels = {
    'TRACE': 5,
    'DEBUG': 10,
    'INFO': 20,
    'SUCCESS': 25,
    'WARNING': 30,
    'ERROR': 40,
    'CRITICAL': 50
}


def set_logger(level: Union[int, str] = 20):
    if isinstance(level, str):
        try:
            level = _levels[level.upper()]
        except KeyError as e:
            raise KeyError(f'`{level}` not in {_levels.keys()}') from e

    if getattr(logger, 'lvl', -1) != level:
        logger.remove()
        logger.add(_handler, level=level, format='{message}', backtrace=False)
        logger.add('script.log',
                   level='DEBUG',
                   rotation='1 week',
                   retention='1 year',
                   encoding='UTF-8-SIG')

        setattr(logger, 'lvl', level)


def file_size_string(size, suffix='B'):
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(size) < 1024.0:
            return f'{size:3.2f} {unit}{suffix}'

        size /= 1024.0

    return f'{size:.2f}Yi {suffix}'
