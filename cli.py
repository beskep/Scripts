import click
from loguru import logger

from scripts.author_size import author_size as _size
from scripts.copy_shutdown import copy_shutdown as _copy
from scripts.image_resize import resize as _resize
from scripts.utils import set_logger


@click.group()
@click.option('--debug', '-d', is_flag=True)
def cli(debug):
    set_logger(level=(10 if debug else 20))


@cli.command()
@click.option('--size', '-s', default=2000, show_default=True)
@click.option('--resize-filter', '-f', default='Mitchell', show_default=True)
@click.option('--ext', '-e', show_default=True)
@click.option('--prefix-original',
              '-o',
              'prefix',
              flag_value='original',
              default=True,
              help='[ORIGINAL] prefix when dst is not set [default]')
@click.option('--prefix-resized',
              '-r',
              'prefix',
              flag_value='resized',
              help='[RESIZED] prefix when dst is not set')
@click.option('--batch/--no-batch', default=True, show_default=True)
@click.option('--capture/--no-capture',
              default=True,
              help='Capture ImageMagick output')
@click.argument('src', type=click.Path(exists=True, file_okay=False))
@click.argument('dst', required=False)
def resize(size, ext, resize_filter, prefix, batch, capture, src, dst):
    """batch resize images/comics"""
    _resize(src=src,
            dst=dst,
            size=size,
            ext=ext,
            resize_filter=resize_filter,
            batch=batch,
            capture=capture,
            prefix_original=(prefix == 'original'),
            mogrify=True)


@cli.command()
@click.option('--viz', default='bar', type=click.Choice(['bar', 'gradient']))
@click.argument('path', required=False)
def size(viz, path):
    _size(path=path, viz=viz)


@cli.command()
@click.option('--shutdown/--no-shutdown', help='Shutdown after robocopy')
@click.option('--mirror/--no-mirror',
              help=('Deletes destination files and directories '
                    'that no longer exist in the source'))
@click.argument('src', type=click.Path(exists=True, file_okay=False))
@click.argument('dst', type=click.Path(exists=True, file_okay=False))
def copy(shutdown, mirror, src, dst):
    """robocopy"""
    logger.info('shutdown: {}', shutdown)
    logger.info('mirror: {}', mirror)

    click.confirm('Continue?', abort=True)

    _copy(src=src, dst=dst, shutdown=shutdown, mirror=mirror)


if __name__ == '__main__':
    # pylint: disable=no-value-for-parameter
    cli()
