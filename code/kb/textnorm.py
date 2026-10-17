"""Polish text normalisation + tokenisation for lexical (BM25) retrieval.

No neural models. Pipeline per text:
  lowercase -> fold diacritics (ą->a, ł->l, ...) -> \\w+ tokens -> drop stopwords
  -> light Polish suffix stripping -> prefix truncation (default 7 chars).
Numbers (years!) and roman numerals are kept verbatim.

The same `Tokenizer` config MUST be used for indexing and querying; it is stored
in the index dir (tokenizer.json) and restored by kb.search.KB.
"""
from __future__ import annotations

import re
import unicodedata

_WORD = re.compile(r"\w+", re.UNICODE)

_FOLD_SRC = "ąćęłńóśźżĄĆĘŁŃÓŚŹŻäöüßéèêëáàâíìîóòôúùûýÿčďěňřšťžůñçœæ"
_FOLD_DST = "acelnoszzACELNOSZZaousseeeeaaaiiiooouuuyycdenrstzuncoa"
_FOLD = str.maketrans({s: d for s, d in zip(_FOLD_SRC, _FOLD_DST)})


def fold(text: str) -> str:
    """Lowercase + strip Polish (and common Latin) diacritics."""
    t = text.lower().translate(_FOLD)
    if not t.isascii():
        # rare chars: NFKD + drop combining marks (keeps Cyrillic/Greek letters as-is)
        t = "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c))
    return t


# Polish stopwords (function words); folded at import time.
_STOP_RAW = """
a aby ach acz aczkolwiek aj albo ale ależ ani aż bardziej bardzo bez bo bowiem by byli bym
być był była było były będzie będą cali cała cały chce ci cię ciebie co cokolwiek coś czasami
czasem czemu czy czyli daleko dla dlaczego dlatego do dobrze dokąd dość dużo dwa dwaj dwie
dwoje dziś dzisiaj gdy gdyby gdyż gdzie gdziekolwiek gdzieś go i ich ile im inna inne inny
innych iż ja ją jak jakaś jakby jaki jakichś jakie jakiś jakiż jakkolwiek jako jakoś je jeden
jedna jedno jednak jednakże jego jej jemu jest jestem jeszcze jeśli jeżeli już ją każdy kiedy
kilka kimś kto ktokolwiek ktoś która które którego której który których którym którzy ku lat
lecz lub ma mają mam mi mimo między mną mnie mogą moi moim moja moje może możliwe można mój mu
musi my na nad nam nami nas nasi nasz nasza nasze naszego naszych natomiast natychmiast nawet
nią nic nich nie niech niego niej niemu nigdy nim nimi niż no o obok od około on ona one oni
ono oraz oto owszem pan pana pani po pod podczas pomimo ponad ponieważ powinien powinna powinni
powinno poza prawie przecież przed przede przedtem przez przy roku również sam sama są się
skąd sobie sobą sposób swoje ta tak taka taki takie także tam te tego tej temu ten teraz też
to tobą tobie toteż trzeba tu tutaj twoi twoim twoja twoje twym twój ty tych tylko tym u w
wam wami was wasz wasza wasze we według wiele wielu więc więcej wszyscy wszystkich wszystkie
wszystkim wszystko wtedy wy właśnie z za zapewne zawsze ze zł znowu znów został żaden żadna
żadne żadnych że żeby oraz jako którą którymi tą tę owego owej owych
"""
# Extra words that are noise in *questions* (exam phrasing) but not dropped from documents.
_QSTOP_RAW = """
podaj wskaż wymień napisz wyjaśnij określ uzasadnij odpowiedź odpowiedzi poprawna poprawną
prawidłowa prawidłową prawdziwe fałszywe zdanie zdania zaznacz wybierz uzupełnij tekst tekstu
źródło źródła źródłem pytanie pytania informacja informacje nazwa nazwę nazwisko imię
jakim jakiej jakich jakiego jaką kogo komu kim czym czego ilu który którym którego
rok roku latach wieku wiek
oceń prawdziwość poniższych poniższe poniższego zdań dotyczących dotyczące dotyczącej jeśli albo
fałszywe prawdziwe odpowiedz formacie przyporządkuj przyporządkowanie opisy opis opisów zbędny
jeden literę litery poprawnej poprawne luki lukę spośród podanych podane wpisz uzupełnij
odpowiednie odpowiednią właściwą właściwe dokończ następujących następujące wydarzenia
chronologicznej kolejności uporządkuj
"""
STOPWORDS = frozenset(fold(w) for w in _STOP_RAW.split())
QUERY_STOPWORDS = STOPWORDS | frozenset(fold(w) for w in _QSTOP_RAW.split())

# light inflectional suffixes (already folded), longest first
_SUFFIXES = sorted(
    """owego owych owymi owej owie iego iemu ymi imi ach ami ego emu owi iej ich ow om em
    ie ia ii ym im ej a e i o u y""".split(),
    key=len,
    reverse=True,
)


class Tokenizer:
    """Configurable, picklable tokenizer.

    mode: 'stem' (suffix strip + truncation), 'trunc' (truncation only), 'none' (folded words)
    """

    def __init__(self, mode: str = "stem", prefix: int = 7, min_stem: int = 4):
        self.mode = mode
        self.prefix = prefix
        self.min_stem = min_stem
        self._cache: dict[str, str] = {}

    def config(self) -> dict:
        return {"mode": self.mode, "prefix": self.prefix, "min_stem": self.min_stem, "fold": True}

    @classmethod
    def from_config(cls, cfg: dict) -> "Tokenizer":
        return cls(mode=cfg.get("mode", "stem"), prefix=cfg.get("prefix", 7), min_stem=cfg.get("min_stem", 4))

    def __getstate__(self):
        return self.config()

    def __setstate__(self, st):
        self.__init__(st.get("mode", "stem"), st.get("prefix", 7), st.get("min_stem", 4))

    def _stem(self, w: str) -> str:
        if w.isdigit() or self.mode == "none":
            return w
        if self.mode == "stem" and len(w) > self.min_stem:
            for s in _SUFFIXES:
                if w.endswith(s) and len(w) - len(s) >= self.min_stem:
                    w = w[: -len(s)]
                    break
        if self.prefix and len(w) > self.prefix:
            w = w[: self.prefix]
        return w

    def tokens(self, text: str, query: bool = False) -> list[str]:
        stop = QUERY_STOPWORDS if query else STOPWORDS
        cache = self._cache
        if len(cache) > 3_000_000:
            cache.clear()
        out = []
        for w in _WORD.findall(fold(text)):
            if w in stop or (len(w) == 1 and not w.isdigit()) or w.startswith("_"):
                continue
            s = cache.get(w)
            if s is None:
                s = self._stem(w)
                cache[w] = s
            out.append(s)
        return out
