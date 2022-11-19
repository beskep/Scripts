import click
from loguru import logger

from scripts.author_size import author_size as _size
from scripts.copy_shutdown import copy_shutdown as _copy
from scripts.image_resize import resize as _resize
from scripts.remove_duplicate import remove_duplicate as _duplicate
from scripts.utils import WindowsMessage, set_logger

_dir = click.Path(exists=True, file_okay=False)


@click.group()
@click.option('--debug', '-d', is_flag=True)
@click.option('--loglevel', '-l', default=20)
@click.option('--notification',
              '-n',
              type=click.Choice(['none', 'sound', 'msgbox']),
              default='sound')
def cli(debug, loglevel, notification):
    set_logger(level=min((10 if debug else 20), loglevel))


@cli.result_callback()
def notification(*args, **kwargs):
    n = kwargs['notification']

    if n == 'sound':
        WindowsMessage.msg_beep()
    elif n == 'msgbox':
        WindowsMessage.msg_box(message='Done', title='scripts')

    logger.info('Done')


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
    _duplicate(src=src, batch=batch, keep=keep, remove=remove)


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
@click.option('--run/--no-run',
              show_default=True,
              help='no-run: Do NOT run command and just log the arguments.')
@click.option('--shutdown/--no-shutdown',
              show_default=True,
              help='Shutdown after robocopy.')
@click.option('--mirror/--no-mirror',
              show_default=True,
              help=('Deletes destination files and directories '
                    'that no longer exist in the source.'))
@click.option('--hidden/--no-hidden',
              show_default=True,
              help='no-run: Copy hidden files.')
@click.option('--fl/--nfl',
              default=True,
              show_default=True,
              help='/nfl: Specifies that file names are not to be logged.')
@click.argument('src', type=_dir)
@click.argument('dst', type=_dir)
def copy(run, shutdown, mirror, hidden, fl, src, dst):
    """robocopy"""
    logger.info('run: {}', run)
    logger.info('shutdown: {}', shutdown)
    logger.info('mirror: {}', mirror)
    logger.info('hidden: {}', hidden)
    logger.info('fl: {}', fl)

    click.confirm('Continue?', abort=True)

    _copy(src=src,
          dst=dst,
          run=run,
          shutdown=shutdown,
          mirror=mirror,
          hidden=hidden,
          log_files=fl)


if __name__ == '__main__':
    # pylint: disable=no-value-for-parameter
    cli()
