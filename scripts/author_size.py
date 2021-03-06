from collections import defaultdict
from pathlib import Path
import re
from typing import Optional

from loguru import logger
import pandas as pd

from .utils import file_size_string as fss

p_author = re.compile(r'^\[.*\((.*?)\)].*')


def detect_author(file_name: str) -> Optional[str]:
    m = p_author.match(file_name)

    return None if m is None else m.group(1)


def read_du(file):
    df: pd.DataFrame = pd.read_csv(file)
    df['name'] = [Path(x).name for x in df['Path']]
    df['author'] = [detect_author(x) for x in df['name']]
    df['SizeMB'] = df['DirectorySize'] / 1e6

    return df


def read_wiztree(file):
    dd = defaultdict(list)

    with open(file, 'r', encoding='utf-8') as f:
        for line in f:
            cols = line.replace('"', '').split(',')
            p = Path(cols[0])

            if not (p.is_dir() or p.suffix.lower() in ('.rar', '.zip')):
                continue

            if '_downloaded' in p.name:
                continue

            dd['author'].append(detect_author(p.name))
            dd['SizeMB'].append(float(cols[1]) / 1e6)
            dd['name'].append(p.name)

    return pd.DataFrame(dd)


def find_wiztree_file(root: Optional[Path]):
    if root is None:
        root = Path('.')

    files = list(root.glob('WizTree*'))
    if not files:
        raise FileNotFoundError('Target file not found')

    files.sort(key=lambda x: -x.stat().st_mtime)

    return files[0]


def find_file(path) -> Path:
    if path is not None:
        path = Path(path)

    if path is None or path.is_dir():
        path = find_wiztree_file(path)

    path.stat()

    return path


def _visualize(df: pd.DataFrame, path, subset='SizeMB', viz_style='bar'):
    df_vis = df.sort_values(by=subset, ascending=False)

    if viz_style == 'bar':
        viz = df_vis.style.bar(subset=subset)
    elif viz_style == 'gradient':
        viz = df_vis.style.background_gradient(subset=subset)
    else:
        raise ValueError(f'{viz_style} not in ("bar", "gradient")')

    viz.to_html(path)


def _author_size(df: pd.DataFrame):
    file_size: pd.DataFrame = (
        df.groupby('author')['SizeMB'].sum().round(2).to_frame())
    count: pd.DataFrame = df.groupby('author').size().to_frame(name='Count')

    file_size = file_size.join(count)
    file_size['Size'] = [fss(x * 1e6) for x in file_size['SizeMB']]
    file_size = file_size[['SizeMB', 'Size', 'Count']]

    return file_size


def author_size(path, viz, drop_na=True):
    # ?????? ?????? ??????
    path = find_file(path)
    root = path.parent
    logger.info(f'File: "{path.as_posix()}"')

    # ?????? ????????????
    if 'WizTree' in path.name:
        df = read_wiztree(path)
    else:
        df = read_du(path)
    df.sort_values(by='SizeMB', inplace=True, ascending=False)

    # ?????? ?????? ???????????? ??????
    logger.info('Files by size')
    print('\n', df.head(10))
    _visualize(df=df,
               path=root.joinpath('Comics-Book-Size.html'),
               viz_style=viz)

    # ?????? ??????/????????? ??????
    df_author = _author_size(
        df=(df.loc[df['author'] != 'N???A'] if drop_na else df))
    df_author.sort_values(by='SizeMB', inplace=True, ascending=False)

    print('\n', df_author.head(10))
    _visualize(df=df_author,
               path=root.joinpath('Comics-Author-Size.html'),
               subset='SizeMB',
               viz_style=viz)
    _visualize(df=df_author,
               path=root.joinpath('Comics-Author-Count.html'),
               subset='Count',
               viz_style=viz)
