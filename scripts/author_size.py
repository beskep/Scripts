from collections.abc import Collection
from pathlib import Path
from typing import Literal

import pandas as pd
import polars as pl
import rich
from loguru import logger

from scripts.utils import FileSize

cnsl = rich.get_console()


def find_wiztree(root: Path | None):
    if root is None:
        root = Path()

    if not (files := list(root.glob('WizTree*'))):
        raise FileNotFoundError(root)

    files.sort(key=lambda x: -x.stat().st_mtime)

    return files[0]


def _bytes(size):
    return str(FileSize(size, digits=2))


class Expr:
    MEGABYTE = 'Megabyte'
    READABLE = 'HumanReadable'

    path = pl.col('path')
    name = pl.col('name')
    author = pl.col('author')
    size = pl.col('size')

    _MEBI = 2**20

    alias_name = path.apply(lambda x: Path(x).name).alias('name')
    alias_author = name.str.extract(r'^\[.*\((.*?)\)]').alias('author')
    alias_megabyte = size.truediv(_MEBI).round(2).alias(MEGABYTE)
    alias_humanize = size.apply(_bytes, return_dtype=pl.Utf8).alias(READABLE)

    dir_or_archive = path.str.extract(r'(([^\]]\\)|(\.((rar)|(zip))))$').is_not_null()


def read_wiztree(path: str | Path):
    return (
        pl.scan_csv(path, skip_rows=1)
        .rename({'파일 이름': 'path', '크기': 'size'})
        .with_columns(pl.col('path').str.len_chars().alias('pl'))
        .filter(pl.col('pl') != pl.col('pl').min())  # filter root dir
        .filter(Expr.dir_or_archive)
        .with_columns(Expr.alias_name)
        .select(
            Expr.name,
            Expr.alias_author,
            Expr.size,
            Expr.alias_megabyte,
            Expr.alias_humanize,
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
            styler.format({'size': '{:.2e}', Expr.MEGABYTE: '{:.2f}'})
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
        df.with_columns(Expr.author.fill_null('NA'))
        .group_by(Expr.author)
        .agg([pl.count('size').alias('count'), pl.sum('size')])
        .with_columns(Expr.alias_megabyte, Expr.alias_humanize)
        .sort('size', descending=True)
    )


@pl.Config(
    set_tbl_hide_column_data_types=True,
    set_fmt_str_lengths=cnsl.width // 2,
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
    dfs = read_wiztree(path)

    # 개별 파일 크기별로 정리
    cnsl.print('Files by size:', style='blue bold')
    cnsl.print(dfs.drop('size'))
    HtmlViz.write_df(
        path=root / 'Comics-Book.html',
        df=dfs,
        subset=Expr.MEGABYTE,
    )

    # 작가 크기/개수별 정리
    if drop_na:
        dfs = dfs.filter(pl.col('author') != 'N／A')  # noqa: RUF001

    dfa = _author_size(dfs)
    cnsl.print('\nAuthors by size:', style='blue bold')
    cnsl.print(dfa.drop('size'))
    HtmlViz.write_dfs(
        path=root / 'Comics-Author.html',
        df=dfa,
        subset=(Expr.MEGABYTE, 'count'),
    )
