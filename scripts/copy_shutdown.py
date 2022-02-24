from pathlib import Path
import subprocess as sp

from loguru import logger


def _prep(path) -> Path:
    path = Path(path).resolve()
    if not path.is_dir():
        raise NotADirectoryError(path)

    path.stat()

    return path


def copy_shutdown(src,
                  dst,
                  run=True,
                  shutdown=False,
                  mirror=False,
                  hidden=False,
                  log_files=True):
    src = _prep(src)
    dst = _prep(dst)

    log = Path(__file__).parents[1].joinpath('copy.log').resolve()

    mir = '/MIR' if mirror else '/e'
    nfl = '' if log_files else '/nfl'
    xa = '/xa:st' + ('h' if hidden else '')
    args = (f'robocopy "{src}" "{dst}" {mir} {xa} /tee /np {nfl} '
            f'/unicode /unilog:"{log}" /eta')

    logger.info(args)
    if run:
        sp.run(args, check=False)

    if shutdown:
        logger.info('shutdown')
        sp.run('shutdown -s -t 120', check=False)
