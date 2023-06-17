import numpy as np
import pandas as pd
from loguru import logger
from rich import box
from rich.console import Console
from rich.highlighter import ReprHighlighter
from rich.logging import RichHandler
from rich.table import Table
from rich.theme import Theme


class CustomHighlighter(ReprHighlighter):
    highlights = ReprHighlighter.highlights.copy()
    highlights.append(r'(?P<vb>\|)')


theme = Theme({'logging.level.success': 'blue', 'repr.vb': 'bold'})
console = Console(theme=theme)
_handler = RichHandler(
    console=console,
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


class RichDataFrame:
    BOX = box.SQUARE_DOUBLE_HEAD
    INDEX = True
    MIN_COL_WIDTH = 4

    COLLAPSE = True
    MAX_ROW = 20
    ELLIPSIS_STYLE = 'live.ellipsis'

    @classmethod
    def collapse(cls, df: pd.DataFrame):
        return cls.COLLAPSE and len(df.index) > cls.MAX_ROW

    @classmethod
    def _justify(cls, dtype):
        numeric = np.issubdtype(dtype, np.number)
        return 'right' if numeric else 'left'

    @classmethod
    def table(cls, df: pd.DataFrame, table: Table | None = None):
        if table is None:
            table = Table(box=cls.BOX)

        if cls.INDEX:
            table.add_column(justify=cls._justify(df.index.dtype))

        dtypes = df.dtypes
        for column in df.columns:
            table.add_column(
                str(column),
                justify=cls._justify(dtypes[column]),
                min_width=cls.MIN_COL_WIDTH,
            )

        collapse = cls.collapse(df)
        for row in (df.head() if collapse else df).itertuples(index=cls.INDEX):
            table.add_row(*map(str, row))

        if collapse:
            table.add_row(*['...' for _ in table.columns], style=cls.ELLIPSIS_STYLE)

            for row in df.tail().itertuples(index=cls.INDEX):
                table.add_row(*map(str, row))

        return table

    @classmethod
    def print(cls, df: pd.DataFrame, table: Table | None = None):  # noqa: A003
        table = cls.table(df=df, table=table)
        console.print(table)
