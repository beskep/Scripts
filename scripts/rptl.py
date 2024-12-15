import dataclasses as dc
import re
import shutil
import tomllib
from collections.abc import Collection
from functools import cached_property
from itertools import batched, chain
from pathlib import Path

from loguru import logger

from scripts.utils import Progress


@dc.dataclass
class RpyReader:
    path: str | Path
    n: int = 100

    def iter_chunk(self):
        lines: list[str] = []

        with Path(self.path).open('r', encoding='UTF-8') as f:
            for line in f:
                lines.append(line)

                if not line.strip():
                    yield lines
                    lines = []

        yield lines

    def __iter__(self):
        for lines in batched(self.iter_chunk(), n=self.n):
            yield ''.join(chain.from_iterable(lines))


@dc.dataclass
class TranslationMatch:
    match: re.Match
    full: str
    head: str
    src: str
    dst: str


@dc.dataclass
class Pattern:
    translation: Collection[str] = (
        # e.g.
        #    old "src"
        #    new "dst"
        r'(?P<head>old \"(?P<src>.*)\"(\s+)new )\"(?P<dst>.*)\"',
        # e.g.
        #    # character "src"
        #    character "dst"
        r'(?P<head># (?P<char>[\w_]*)\s*\"(?P<src>.*)\"(\s+)(?P=char) )\"(?P<dst>.*)\"',
    )

    # `script.rpy` 파일에 있는 캐릭터 목록
    character: str = r'.*Character\(\"(.+?)\",.*'

    # translate [language] ...:
    language: tuple[str, str] | None = None

    _tl: tuple[re.Pattern, ...] = dc.field(init=False)

    def __post_init__(self):
        self._tl = tuple(re.compile(p) for p in self.translation)

    def iter_tl(self, text: str):
        for match in chain.from_iterable(p.finditer(text) for p in self._tl):
            yield TranslationMatch(match, *match.group(0, 'head', 'src', 'dst'))


@dc.dataclass
class Preserve:
    # 번역하지 않을 파일, 단어 목록
    files: set[str]
    words: set[str]


@dc.dataclass
class Config:
    batch_size: int
    linebreak_threshold: int
    backup: str | None
    dev_mode: str
    dev_script: str | None

    preserve: Preserve

    @classmethod
    def read(cls, path: str | Path = 'config.toml'):
        conf = tomllib.loads(Path(path).read_text('UTF-8'))['rptl']
        preserve = Preserve(**{k: set(v) for k, v in conf.pop('preserve').items()})
        return cls(**conf, preserve=preserve)


@dc.dataclass(frozen=True)
class RenpyTranslation:
    path: Path
    tl: str = 'game/tl'
    script_rpy: str | None = 'game/script.rpy'
    characters_rpy: str | None = None
    language: str = 'Korean'

    pattern: Pattern = dc.field(default_factory=Pattern)
    conf: Config = dc.field(default_factory=Config.read)

    @cached_property
    def characters(self) -> set[str]:
        if not (rpy := self.characters_rpy or self.script_rpy):
            return set()

        if not (path := self.path / rpy).exists():
            raise FileNotFoundError(path)

        text = path.read_text('UTF-8')
        return {m.group(1) for m in re.finditer(self.pattern.character, text)}

    def _edit_side_by_side(self, text: str, m: TranslationMatch) -> str | None:
        """
        원문, 번역 복수 표기

        Parameters
        ----------
        text : str
        m : TranslationMatch

        Returns
        -------
        str | None
        """
        # 캐릭터 이름
        if m.src in self.characters:
            if re.match(r'^\[.*\]$', m.src):
                # "[캐릭터]" -> 원문 유지
                return text.replace(m.full, f'{m.head}"{m.src}"')

            # 대사창 표기: "원문 (번역)"
            return text.replace(m.full, f'{m.head}"{m.src} ({m.dst})"')

        # 짧은 글
        if len(m.src) <= self.conf.linebreak_threshold:
            return text.replace(m.full, f'{m.head}"{m.src}  |  {m.dst}"')

        src = m.src.replace('{w}', '').replace('{p}', ' / ')  # 원문 줄바꿈 제거

        if not m.dst.startswith(src):
            # 일반 대사: "원문\n번역"
            return text.replace(m.full, f'{m.head}"{src}\\n{m.dst}"')

        return None

    def _edit(
        self,
        text: str,
        m: TranslationMatch,
        *,
        preserve: bool,
    ) -> str | None:
        # TODO dst에서 `%` -> `%%`

        if (
            m.dst.startswith(m.src)  ##
            or (m.src.startswith('old:') and m.dst.startswith('new:'))
        ):
            return None

        # 원문 유지
        if preserve or m.src.strip().strip('.') in self.conf.preserve.words:
            return text.replace(m.full, f'{m.head}"{m.src}"')

        return self._edit_side_by_side(text=text, m=m)

    def _rpy(self, text: str, *, preserve: bool):
        for match in self.pattern.iter_tl(text):
            if t := self._edit(text=text, m=match, preserve=preserve):
                text = t

        return text

    def rpy(self, path: Path):
        preserve = path.stem in self.conf.preserve.files

        reader = RpyReader(path=path, n=self.conf.batch_size)
        texts = (self._rpy(text=text, preserve=preserve) for text in reader)
        return ''.join(texts)

    def execute(self):
        tl = self.path / self.tl
        language = tl / self.language

        # backup
        backup = tl / f'{self.language}{self.conf.backup}'
        if self.conf.backup and not backup.with_suffix('.zip').exists():
            logger.info('backup="{}"', backup)
            shutil.make_archive(base_name=str(backup), format='zip', root_dir=language)

        # rpy
        if not (paths := list(language.rglob('*.rpy'))):
            raise FileNotFoundError(language)

        with Progress() as p:
            for rpy in p.track(paths):
                logger.debug(rpy.relative_to(tl))

                text = self.rpy(rpy)
                if rpy.read_text('UTF-8') != text:
                    rpy.write_text(text, 'UTF-8')
                    rpy.with_suffix('.rpyc').unlink(missing_ok=True)

        # dev
        if not self.conf.dev_script:
            return

        dev = (self.path / self.conf.dev_mode).with_suffix('.rpy')
        if dev.exists():
            logger.warning('dev mode already exists: "{}"', dev)
        else:
            logger.info('dev_mode="{}"', dev)
            dev.write_text(self.conf.dev_script, 'UTF-8')

    def __call__(self):
        self.execute()
