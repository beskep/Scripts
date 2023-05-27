import pandas as pd
from loguru import logger
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


def df_table(
    df: pd.DataFrame,
    table: Table | None = None,
    *,
    index=True,
    index_name: str | None = None,
) -> Table:
    if table is None:
        table = Table()

    if index:
        index_name = str(index_name) if index_name else ''
        table.add_column(index_name)

    for column in df.columns:
        table.add_column(str(column))

    for row in df.itertuples(index=index):
        table.add_row(*map(str, row))

    return table


def print_df(
    df: pd.DataFrame,
    table: Table | None = None,
    *,
    index=True,
    index_name: str | None = None,
):
    table = df_table(df=df, table=table, index=index, index_name=index_name)
    console.print(table)
