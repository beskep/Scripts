from collections.abc import Collection
from pathlib import Path
from typing import Literal

import pandas as pd
import polars as pl
import rich
from loguru import logger

from scripts.utils import FileSize

console = rich.get_console()


def find_wiztree(root: Path | None):
    root = root or Path()

    if not (files := list(root.glob('WizTree*'))):
        raise FileNotFoundError(root)

    files.sort(key=lambda x: -x.stat().st_mtime)

    return files[0]


def _bytes(size):
    return str(FileSize(size, digits=2))


class Expr:
    MIB = 'MiB'
    READABLE = 'HumanReadable'

    _MEBI = 2**20

    mebibyte = pl.col('size').truediv(_MEBI).round(2).alias(MIB)
    readable = pl.col('size').map_elements(_bytes, return_dtype=pl.Utf8).alias(READABLE)


def read_wiztree(path: str | Path):
    # work/book > file/page
    data = (
        pl.scan_csv(path, skip_rows=1)
        .rename({'파일 이름': 'path', '크기': 'size'})
        .with_columns(pl.col('path').str.len_chars().alias('pl'))
        .filter(pl.col('pl') != pl.col('pl').min())  # filter root dir
        .with_columns(
            pl.col('path').str.extract_groups(r'.*\\(?<work>.*)\\(?<file>[^\\]*)')
        )
        .unnest('path')
        .with_columns(pl.col('file').replace({'': None}))
    )

    count = data.filter(pl.col('file').is_not_null()).group_by('work').len('files')

    return (
        data.filter(pl.col('file').is_null())
        .join(count, on='work', how='left', validate='1:1')
        .select(
            'work',
            pl.col('work').str.extract(r'^\[.*\((.*?)\)]').alias('author'),
            'files',
            'size',
            Expr.mebibyte,
            Expr.readable,
        )
        .sort('size', descending=True)
        .collect()
    )


Viz = Literal['bar', 'gradient']


class HtmlViz:
    VIZ: Viz = 'bar'
    UTF8SIG = 'UTF-8-SIG'

    _TEMPLATE = """
<html>
  <table style="font-size: 16px">
    <tr>{}</tr>
    <tr>{}</tr>
  </table>
</html>
"""

    @classmethod
    def to_html(cls, df: pd.DataFrame | pl.DataFrame, subset: str | Collection[str]):
        if isinstance(df, pl.DataFrame):
            df = pd.DataFrame(
                df.sort(subset, descending=True)
                .fill_null('[null]')
                .to_dict(as_series=False)
            )

        match cls.VIZ:
            case 'bar':
                styler = df.style.bar(subset=subset)
            case 'gradient':
                styler = df.style.background_gradient(subset=subset)
            case _:
                msg = f'{cls.VIZ!r} not in ("bar", "gradient")'
                raise ValueError(msg)

        styler = (
            styler.format({'size': '{:.2e}', Expr.MIB: '{:.2f}'})
            .set_table_styles([{'selector': 'td, th', 'props': 'padding: 0 10px;'}])
            .set_table_styles(
                {'size': [{'selector': '', 'props': [('text-align', 'right')]}]},
                overwrite=False,
            )
        )

        return styler.to_html()

    @classmethod
    def write_df(cls, path: Path, df: pd.DataFrame | pl.DataFrame, subset: str):
        text = cls.to_html(df=df, subset=subset)
        path.write_text(text, encoding=cls.UTF8SIG)

    @classmethod
    def write_dfs(
        cls,
        path: Path,
        df: pd.DataFrame | pl.DataFrame,
        subset: Collection[str],
    ):
        width = 1.0 / len(subset)
        th = ''.join(f'<th style="width: {width:%}">By {x}</th>' for x in subset)

        tds = (cls.to_html(df=df, subset=x) for x in subset)
        td = ''.join(f'<td>{x}</td>' for x in tds)

        text = cls._TEMPLATE.format(th, td)
        path.write_text(text, encoding=cls.UTF8SIG)


def _author_size(df: pl.DataFrame):
    return (
        df.with_columns(pl.col('author').fill_null('NA'))
        .group_by('author')
        .agg(pl.sum('files'), pl.count('size').alias('count'), pl.sum('size'))
        .with_columns(Expr.mebibyte, Expr.readable)
        .sort('size', descending=True)
    )


@pl.Config(
    set_tbl_hide_column_data_types=True,
    set_fmt_str_lengths=console.width // 2,
)
def author_size(path: Path | None, *, viz: Viz = 'bar', drop_na=True):
    HtmlViz.VIZ = viz

    # 대상 파일 찾기
    path = find_wiztree(path) if path is None or path.is_dir() else path
    root = path.parent

    logger.info('File="{}"', path)
    if 'WizTree' not in path.name:
        logger.warning('대상이 WizTree 파일이 아닐 수 있음: "{}"', path)

    # 파일 불러오기
    work = read_wiztree(path)

    # 개별 파일 크기별로 정리
    console.print('Files by size:', style='blue bold')
    console.print(work.drop('size'))
    HtmlViz.write_df(path=root / 'Comics-Book.html', df=work, subset=Expr.MIB)

    # 작가 크기/개수별 정리
    if drop_na:
        work = work.filter(pl.col('author') != 'N／A')  # noqa: RUF001

    author = _author_size(work)
    console.print('\nAuthors by size:', style='blue bold')
    console.print(author.drop('size'))
    HtmlViz.write_dfs(
        path=root / 'Comics-Author.html',
        df=author,
        subset=(Expr.MIB, 'files', 'count'),
    )
