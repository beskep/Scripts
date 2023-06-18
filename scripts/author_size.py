import re
from pathlib import Path

import pandas as pd
from loguru import logger

from scripts.utils import RichDataFrame, console
from scripts.utils import file_size_string as fss

p_author = re.compile(r'^\[.*\((.*?)\)].*')


def detect_author(file_name: str) -> str | None:
    m = p_author.match(file_name)

    return None if m is None else m.group(1)


def read_du(file):
    df = pd.read_csv(file)
    df['name'] = [Path(x).name for x in df['Path']]
    df['author'] = [detect_author(x) for x in df['name']]
    df['SizeMB'] = (df['DirectorySize'] / 1e6).round(2)

    return df


def read_wiztree(file: Path):
    raw = pd.read_csv(file, skiprows=1, encoding='UTF-8')

    df = raw.iloc[:, [0, 1]]
    df.columns = ['path', 'size']

    # dir only
    df = df.loc[df['path'].str.endswith('\\')]
    df = df.loc[~df['path'].str.endswith('_downloaded\\')]

    df['name'] = [Path(x).name for x in df['path']]
    df['author'] = [detect_author(x) for x in df['name']]
    df['SizeMB'] = (df['size'] / 1e6).round(2)

    return df[['name', 'author', 'SizeMB']].reset_index(drop=True)


def find_wiztree_file(root: Path | None):
    if root is None:
        root = Path('.')

    files = list(root.glob('WizTree*'))
    if not files:
        msg = 'Target file not found'
        raise FileNotFoundError(msg)

    files.sort(key=lambda x: -x.stat().st_mtime)

    return files[0]


def find_file(path) -> Path:
    if path is not None:
        path = Path(path)

    if path is None or path.is_dir():
        path = find_wiztree_file(path)

    path.stat()

    return path


class HtmlViz:
    VIZ = 'bar'
    ENC = 'UTF-8-SIG'
    _TEMPLATE = """
<html>
  <table style="font-size: 16px">
    <tr>{}</tr>
    <tr>{}</tr>
  </table>
</html>
"""

    @classmethod
    def to_html(cls, df: pd.DataFrame, subset='SizeMB'):
        dfs = df.sort_values(by=subset, ascending=False)

        match cls.VIZ:
            case 'bar':
                viz = dfs.style.bar(subset=subset)
            case 'gradient':
                viz = dfs.style.background_gradient(subset=subset)
            case _:
                msg = f'{cls.VIZ!r} not in ("bar", "gradient")'
                raise ValueError(msg)

        return viz.to_html()

    @classmethod
    def write_df(cls, path: Path, df: pd.DataFrame, subset='SizeMB'):
        text = cls.to_html(df=df, subset=subset)
        path.write_text(text, encoding=cls.ENC)

    @classmethod
    def write_dfs(cls, path: Path, df: pd.DataFrame, subset=('SizeMB', 'Count')):
        width = 1.0 / len(subset)
        th = ''.join(f'<th style="width: {width:%}">By {x}</th>' for x in subset)

        tds = (cls.to_html(df=df, subset=x) for x in subset)
        td = ''.join(f'<td>{x}</td>' for x in tds)

        text = cls._TEMPLATE.format(th, td)
        path.write_text(text, encoding=cls.ENC)


def _author_size(df: pd.DataFrame):
    file_size = df.groupby('author')['SizeMB'].sum().round(2).to_frame()
    count = df.groupby('author').size().to_frame(name='Count')

    file_size = file_size.join(count)
    file_size['Size'] = [fss(x * 1e6) for x in file_size['SizeMB']]
    file_size = file_size[['SizeMB', 'Size', 'Count']]

    return file_size


def author_size(path, *, viz, drop_na=True):
    HtmlViz.VIZ = viz

    # 대상 파일 찾기
    path = find_file(path)
    root = path.parent
    logger.info('File="{}"', path)

    # 파읽 불러오기
    size = read_wiztree(path) if 'WizTree' in path.name else read_du(path)
    size = size.sort_values(by='SizeMB', ascending=False)

    # 개별 파일 크기별로 정리
    console.print('Files by size')
    RichDataFrame.print(size)
    HtmlViz.write_df(path=root / 'Comics-Book.html', df=size, subset='SizeMB')

    # 작가 크기/개수별 정리
    if drop_na:
        size = size.loc[size['author'] != 'N／A']  # noqa: RUF001

    size_author = _author_size(df=size).sort_values(by='SizeMB', ascending=False)

    console.print('\nAuthors by size')
    RichDataFrame.print(size_author.reset_index())
    HtmlViz.write_dfs(
        path=root / 'Comics-Author.html',
        df=size_author,
        subset=('SizeMB', 'Count'),
    )
