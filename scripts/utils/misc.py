_K = 1024.0


def bytes_unit(size: float, suffix='B'):
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(size) < _K:
            return size, f'{unit}{suffix}'

        size /= _K

    return size, f'Y{suffix}'


def bytes_str(size: float, suffix='B', digits=1):
    size, unit = bytes_unit(size=size, suffix=suffix)
    return f'{size:.{digits}f} {unit}'
