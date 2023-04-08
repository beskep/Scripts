import ctypes
import winsound
from os import PathLike

import pandas as pd
from loguru import logger
from rich.console import Console
from rich.highlighter import ReprHighlighter
from rich.logging import RichHandler
from rich.table import Table
from rich.theme import Theme

StrPath = str | PathLike


class CustomHighlighter(ReprHighlighter):

    highlights = ReprHighlighter.highlights.copy()
    highlights.append(r'(?P<vb>\|)')


theme = Theme({'logging.level.success': 'blue', 'repr.vb': 'bold'})
console = Console(theme=theme)
_handler = RichHandler(console=console,
                       highlighter=CustomHighlighter(),
                       markup=True,
                       log_time_format='[%X]')
_LEVELS = {
    'TRACE': 5,
    'DEBUG': 10,
    'INFO': 20,
    'SUCCESS': 25,
    'WARNING': 30,
    'ERROR': 40,
    'CRITICAL': 50
}


def set_logger(level: int | str = 20):
    if isinstance(level, str):
        try:
            level = _LEVELS[level.upper()]
        except KeyError as e:
            raise KeyError(f'`{level}` not in {list(_LEVELS.keys())}') from e

    if getattr(logger, 'lvl', -1) != level:
        logger.remove()
        logger.add(_handler, level=level, format='{message}', backtrace=False)
        logger.add('script.log',
                   level=min(20, level),
                   rotation='1 month',
                   retention='1 year',
                   encoding='UTF-8-SIG')

        setattr(logger, 'lvl', level)


def file_size_unit(size: float, suffix='B'):
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(size) < 1024.0:
            return size, f'{unit}{suffix}'

        size /= 1024.0

    return size, f'Y{suffix}'


def file_size_string(size: float, suffix='B'):
    size, unit = file_size_unit(size=size, suffix=suffix)
    return f'{size:.2f} {unit}'


def df_table(df: pd.DataFrame,
             table: Table | None = None,
             show_index=True,
             index_name: str | None = None) -> Table:
    if table is None:
        table = Table()

    if show_index:
        index_name = str(index_name) if index_name else ''
        table.add_column(index_name)

    for column in df.columns:
        table.add_column(str(column))

    for index, value_list in enumerate(df.values.tolist()):
        row = [str(index)] if show_index else []
        row += [str(x) for x in value_list]
        table.add_row(*row)

    return table


def print_df(df: pd.DataFrame,
             table: Table | None = None,
             show_index=True,
             index_name: str | None = None):
    table = df_table(df=df,
                     table=table,
                     show_index=show_index,
                     index_name=index_name)
    console.print(table)


class WindowsMessage:
    WS_EX_TOPMOST = 0x40000

    @staticmethod
    def msg_beep(ok=True):
        if hasattr(winsound, 'MessageBeep'):
            t = winsound.MB_OK if ok else winsound.MB_ICONHAND
            winsound.MessageBeep(t)

    @classmethod
    def msg_box(cls, message: str, title: str | None = None):
        ctypes.windll.user32.MessageBoxExW(None, message, title,
                                           cls.WS_EX_TOPMOST)
