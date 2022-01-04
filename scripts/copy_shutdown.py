from pathlib import Path
import subprocess as sp

from loguru import logger


def _prep(path) -> Path:
    path = Path(path).absolute()
    path.stat()
    if not path.is_dir():
        raise NotADirectoryError(path)

    return path


def copy_shutdown(src, dst, shutdown: bool, mirror=False):
    src = _prep(src)
    dst = _prep(dst)

    log = Path(__file__).parents[1].joinpath('copy.log').absolute()

    mir = '/MIR' if mirror else '/e'
    args = f'robocopy "{src}" "{dst}" {mir} /tee /log:"{log}" /eta'

    logger.info(args)
    sp.run(args, check=False)

    if shutdown:
        logger.info('shutdown')
        sp.run('shutdown -s', check=False)
