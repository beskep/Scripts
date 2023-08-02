import re
import subprocess as sp
from pathlib import Path
from string import whitespace

from loguru import logger

RAR = r'C:\Program Files\WinRAR\Rar.exe'
BZ_COUNT = re.compile(r'.* (\d+) files, (\d+) folders')


class BzMatchError(ValueError):

    def __init__(self, *args: object) -> None:
        super().__init__(*args)

    def __str__(self) -> str:
        return '"bz l" 결과 형식 오류'


def count_rar(path: str | Path, rar: str | Path | None = None):
    rar = rar or RAR
    args = [str(rar), 'lb', str(path)]
    output = sp.check_output(args)

    try:
        lines = output.decode('UTF-8')
    except UnicodeDecodeError:
        lines = output.decode('EUC-KR')

    return sum(1 for x in lines.splitlines() if Path(x).suffix)


def count_bz(path: str | Path, bz: str | Path | None = None):
    if bz is None:
        bz = 'bz'
        bzp = sp.check_output('where bz').decode().rstrip(whitespace)
        if not Path(bzp).exists():
            raise FileNotFoundError(bz)

    args = [str(bz), 'l', str(path)]
    output = sp.check_output(args, encoding='UTF-8')

    for line in output.splitlines():
        if m := BZ_COUNT.match(line):
            return int(m.group(1)), int(m.group(2))

    raise BzMatchError(output)


def _files_dir(path: str | Path):
    path = Path(path)

    if path.is_dir():
        files = [x for x in path.glob('*') if x.suffix in {'.zip', '.rar', '.7z'}]
        directory = path
    elif path.is_file():
        files = [path]
        directory = path.parent
    else:
        raise AssertionError(path)

    return files, directory


def _comparison(count: int, threshold: int):
    if count < threshold:
        symbol = ' <'
        text = 'LessThan'
    else:
        symbol = '>='
        text = 'GreaterEqual'

    return f'{symbol} {threshold}', f'{text}{threshold}'


def count_archive_files(path: str | Path, *, classify=False, threshold=100):
    files, directory = _files_dir(path)

    if not files:
        logger.warning('No archives in "{}"', directory)
        return

    if len(files) == 1:
        classify = False

    try:
        for file in files:
            nf, nd = count_bz(file)
            cs, ct = _comparison(nf, threshold)
            logger.info('files={:03d} {} | dirs={:02d} | {}', nf, cs, nd, file.name)

            if classify:
                dst = directory / ct
                dst.mkdir(exist_ok=True)

                file.rename(dst / file.name)

    except BzMatchError as e:
        logger.error('{}:\n{}', e, e.args[0])
        raise
