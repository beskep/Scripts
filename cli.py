import click
from loguru import logger

from scripts.author_size import author_size as _size
from scripts.image_resize import resize as _resize
from scripts.remove_duplicate import remove_duplicate as _duplicate
from scripts.utils import WindowsMessage, set_logger

# ruff: noqa: PLR0913

_dir = click.Path(exists=True, file_okay=False)
sd = {'show_default': True}


@click.group()
@click.option('--debug', '-d', is_flag=True)
@click.option('--loglevel', '-l', default=20)
@click.option(
    '--notification',
    '-n',
    type=click.Choice(['none', 'sound', 'msgbox']),
    default='sound',
)
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


class RH:
    SIZE = 'Pixel size of smallest fitting dimension. `0` for original size.'
    PO = '`[ORIGINAL]` prefix when dst is not set. [default]'
    PR = '`[RESIZED]` prefix when dst is not set.'
    BATCH = 'Resize multiple directories.'
    CAPTURE = 'Capture ImageMagick output.'


@cli.command()
@click.option('--size', '-s', default=2000, **sd, help=RH.SIZE)
@click.option('--ext', '-e', help='Output image extension.')
@click.option('--resize-filter', '-f', default='Mitchell', **sd)
@click.option('--option', type=str, help='Additional options')
@click.option(
    '--prefix-original',
    '-o',
    'prefix',
    flag_value='original',
    default=True,
    help=RH.PO,
)
@click.option('--prefix-resized', '-r', 'prefix', flag_value='resized', help=RH.PR)
@click.option('--batch/--no-batch', default=True, **sd, help=RH.BATCH)
@click.option('--capture/--no-capture', default=True, **sd, help=RH.CAPTURE)
@click.argument('src', type=_dir)
@click.argument('dst', required=False)
def resize(size, ext, resize_filter, option, prefix, batch, capture, src, dst):
    """batch resize images/comics"""
    _resize(
        src=src,
        dst=dst,
        size=size,
        ext=ext,
        resize_filter=resize_filter,
        option=option,
        batch=batch,
        capture=capture,
        prefix_original=(prefix == 'original'),
    )


@cli.command()
@click.option('--keep', default='webp', **sd, help='Suffix of files to keep.')
@click.option('--remove', multiple=True, help='Suffixes of duplicate files to remove.')
@click.option('--batch/--no-batch', default=True, **sd)
@click.argument('src', type=_dir)
def duplicate(keep, remove, batch, src):
    _duplicate(src=src, batch=batch, keep=keep, remove=remove)


@cli.command()
@click.option('--viz', default='bar', type=click.Choice(['bar', 'gradient']), **sd)
@click.option('--na/--no-na', **sd, help='Drop N/A')
@click.argument('path', required=False)
def size(viz, na, path):
    _size(path=path, viz=viz, drop_na=(not na))


if __name__ == '__main__':
    # pylint: disable=no-value-for-parameter
    cli()
