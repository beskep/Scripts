class FileSize:
    B = 'bytes'
    UNITS = ('K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')

    def __init__(self, size: float, *, binary=True, digits: int | None = 2) -> None:
        self._bytes = size
        self._f = f'.{digits}f' if digits else ''

        self._s, self._u = self.human_readable(size=size, binary=binary)

    def __str__(self) -> str:
        return f'{self._s:{self._f}} {self._u}'

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self._bytes})'

    @property
    def size(self):
        return self._s

    @property
    def unit(self):
        return self._u

    @classmethod
    def human_readable(cls, size: float, *, binary=True) -> tuple[float, str]:
        k = 1024.0 if binary else 1000.0
        suffix = 'iB' if binary else 'B'

        for unit in (cls.B, *cls.UNITS[:-1]):
            if abs(size) < k:
                return size, unit if unit == cls.B else f'{unit}{suffix}'

            size /= k

        return size, f'{cls.UNITS[-1]}{suffix}'
