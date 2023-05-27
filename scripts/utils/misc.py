def file_size_unit(size: float, suffix='B'):
    k = 1024.0
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(size) < k:
            return size, f'{unit}{suffix}'

        size /= k

    return size, f'Y{suffix}'


def file_size_string(size: float, suffix='B'):
    size, unit = file_size_unit(size=size, suffix=suffix)
    return f'{size:.2f} {unit}'
