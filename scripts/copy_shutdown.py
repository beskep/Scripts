from pathlib import Path
import subprocess as sp

from loguru import logger


def _prep(path) -> Path:
    path = Path(path).resolve()
    if not path.is_dir():
        raise NotADirectoryError(path)

    path.stat()

    return path


def copy_shutdown(src, dst, shutdown: bool, mirror=False, log_file_list=True):
    src = _prep(src)
    dst = _prep(dst)

    log = Path(__file__).parents[1].joinpath('copy.log').resolve()

    mir = '/MIR' if mirror else '/e'
    nfl = '' if log_file_list else '/nfl'
    args = (f'robocopy "{src}" "{dst}" {mir} /tee /np {nfl} '
            f'/unicode /unilog:"{log}" /eta')

    logger.info(args)
    sp.run(args, check=False)

    if shutdown:
        logger.info('shutdown')
        sp.run('shutdown -s', check=False)
