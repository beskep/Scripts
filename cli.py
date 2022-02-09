import click
from loguru import logger

from scripts.author_size import author_size as _size
from scripts.copy_shutdown import copy_shutdown as _copy
from scripts.image_resize import resize as _resize
from scripts.remove_duplicate import remove_duplicate
from scripts.utils import set_logger

_dir = click.Path(exists=True, file_okay=False)


@click.group()
@click.option('--debug', '-d', is_flag=True)
@click.option('--loglevel', '-l', default=20)
def cli(debug, loglevel):
    set_logger(level=min((10 if debug else 20), loglevel))


@cli.command()
@click.option('--size',
              '-s',
              default=2000,
              show_default=True,
              help=('Pixel size of smallest fitting dimension. '
                    '`0` for original size.'))
@click.option('--ext', '-e', show_default=True, help='Output image extension.')
@click.option('--resize-filter', '-f', default='Mitchell', show_default=True)
@click.option('--option', type=str, help='Additional options')
@click.option('--prefix-original',
              '-o',
              'prefix',
              flag_value='original',
              default=True,
              help='`[ORIGINAL]` prefix when dst is not set. [default]')
@click.option('--prefix-resized',
              '-r',
              'prefix',
              flag_value='resized',
              help='`[RESIZED]` prefix when dst is not set.')
@click.option('--batch/--no-batch',
              default=True,
              show_default=True,
              help='Resize multiple directories.')
@click.option('--capture/--no-capture',
              default=True,
              show_default=True,
              help='Capture ImageMagick output.')
@click.argument('src', type=_dir)
@click.argument('dst', required=False)
def resize(size, ext, resize_filter, option, prefix, batch, capture, src, dst):
    """batch resize images/comics"""
    _resize(src=src,
            dst=dst,
            size=size,
            ext=ext,
            resize_filter=resize_filter,
            option=option,
            batch=batch,
            capture=capture,
            prefix_original=(prefix == 'original'))


@cli.command()
@click.option('--keep',
              default='webp',
              show_default=True,
              help='Suffix of files to keep.')
@click.option('--remove',
              multiple=True,
              help='Suffixes of duplicate files to remove.')
@click.option('--batch/--no-batch', default=True, show_default=True)
@click.argument('src', type=_dir)
def duplicate(keep, remove, batch, src):
    remove_duplicate(src=src, batch=batch, keep=keep, remove=remove)


@cli.command()
@click.option('--viz',
              default='bar',
              show_default=True,
              type=click.Choice(['bar', 'gradient']))
@click.option('--na/--no-na', show_default=True, help='Drop N/A')
@click.argument('path', required=False)
def size(viz, na, path):
    _size(path=path, viz=viz, drop_na=(not na))


@cli.command()
@click.option('--shutdown/--no-shutdown',
              show_default=True,
              help='Shutdown after robocopy.')
@click.option('--mirror/--no-mirror',
              show_default=True,
              help=('Deletes destination files and directories '
                    'that no longer exist in the source.'))
@click.argument('src', type=_dir)
@click.argument('dst', type=_dir)
def copy(shutdown, mirror, src, dst):
    """robocopy"""
    logger.info('shutdown: {}', shutdown)
    logger.info('mirror: {}', mirror)

    click.confirm('Continue?', abort=True)

    _copy(src=src, dst=dst, shutdown=shutdown, mirror=mirror)


if __name__ == '__main__':
    # pylint: disable=no-value-for-parameter
    cli()
