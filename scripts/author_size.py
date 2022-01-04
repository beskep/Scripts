from collections import defaultdict
from pathlib import Path
import re
from typing import Optional

from loguru import logger
import pandas as pd

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
            if not cols[0].endswith('\\'):
                continue

            p = Path(cols[0])
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

    return path


def _viz_and_save(df: pd.DataFrame, path, viz_style='bar'):
    if viz_style == 'bar':
        viz = df.style.bar(subset='SizeMB')
    elif viz_style == 'gradient':
        viz = df.style.background_gradient(subset='SizeMB')
    else:
        raise ValueError(f'{viz_style} not in ("bar", "gradient")')

    viz.to_html(path)


def author_size(path, viz):
    # 대상 파일 찾기
    path = find_file(path)
    path.stat()
    logger.info(f'File: "{path.as_posix()}"')

    # 파읽 불러오기
    if 'WizTree' in path.name:
        df = read_wiztree(path)
    else:
        df = read_du(path)
    df.sort_values(by='SizeMB', inplace=True, ascending=False)

    # 개별 파일 크기별로 정리
    logger.info('Files by size')
    print('\n', df.head(10))
    _viz_and_save(df=df, path='Size-Book.html', viz_style=viz)

    # 작가 크기별로 정리
    df_author: pd.DataFrame = (
        df.groupby('author')['SizeMB'].sum().round(2).to_frame())
    df_author.sort_values(by='SizeMB', inplace=True, ascending=False)

    print('\n', df_author.head(10))
    _viz_and_save(df=df_author, path='Size-Author.html', viz_style=viz)

    # 작가 NA 제외 크기별 정리
    df_wona: pd.DataFrame = (df.loc[df['author'] != 'N／A'].groupby('author')
                             ['SizeMB'].sum().round(2).to_frame())
    df_wona.sort_values(by='SizeMB', inplace=True, ascending=False)
    _viz_and_save(df=df_wona, path='Size-Author-withoutNA.html', viz_style=viz)
