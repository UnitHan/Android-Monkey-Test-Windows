"""App search adapted from C:/appkium's HangulSearch.kt; pure matching and ranking."""

import re
import unicodedata

CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
CHO_R = ("g", "kk", "n", "d", "tt", "r", "m", "b", "pp", "s", "ss", "", "j", "jj", "ch", "k", "t", "p", "h")
JUNG_R = (
    "a",
    "ae",
    "ya",
    "yae",
    "eo",
    "e",
    "yeo",
    "ye",
    "o",
    "wa",
    "wae",
    "oe",
    "yo",
    "u",
    "weo",
    "we",
    "wi",
    "yu",
    "eu",
    "ui",
    "i",
)
JONG_R = (
    "",
    "g",
    "kk",
    "gs",
    "n",
    "nj",
    "nh",
    "d",
    "l",
    "lg",
    "lm",
    "lb",
    "ls",
    "lt",
    "lp",
    "lh",
    "m",
    "b",
    "bs",
    "s",
    "ss",
    "ng",
    "j",
    "ch",
    "k",
    "t",
    "p",
    "h",
)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    return "".join(CHO[ord(c) - 0x1100] if 0x1100 <= ord(c) <= 0x1112 else c for c in text)


def has_hangul(text: str) -> bool:
    return any("가" <= c <= "힣" or c in CHO for c in text)


def choseong(text: str) -> str:
    return "".join(CHO[(ord(c) - 0xAC00) // 588] if "가" <= c <= "힣" else c if c in CHO else "" for c in text)


def romanize(text: str) -> str:
    result = []
    for c in text:
        if "가" <= c <= "힣":
            index = ord(c) - 0xAC00
            result.append(CHO_R[index // 588] + JUNG_R[index % 588 // 28] + JONG_R[index % 28])
        elif not c.isspace():
            result.append(c.casefold())
    return "".join(result)


def sound_norm(text: str) -> str:
    value = text.casefold().replace("ph", "p")
    value = re.sub(r"c(?=[eiy])", "s", value).replace("c", "k").replace("q", "k")
    value = value.replace("f", "p").replace("v", "b").replace("r", "l")
    value = re.sub(r"(?<=[bcdfghjklmnpqrstvz])y(?=[aeiou])", "", value)  # 튜 → tu, YouTube
    return re.sub(r"w(?=[aeiou])", "", value).replace("eo", "o")


def phonetic_prefix(query: str, name: str) -> bool:
    if not query or not name or query[0] != name[0]:
        return False
    cursor = 0
    for c in query:
        if cursor < len(name) and name[cursor] == c:
            cursor += 1
        elif c not in "aeiou":
            at = name.find(c, cursor)
            if at < 0:
                return False
            cursor = at + 1
    return True


def phonetic_match(query: str, name: str) -> bool:
    # Preserve camelCase boundaries before lowercasing the candidate.
    words = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name).split()
    roma = re.sub(r"(.)\1+", r"\1", sound_norm(romanize(query)))
    return any(phonetic_prefix(roma, sound_norm("".join(words[i:]))) for i in range(len(words)))


def match_rank(name: str, package: str, query: str) -> int | None:
    """Name prefix, name substring, package, initial prefix/substring, phonetic; None = no match."""
    name, query = normalize(name), normalize(query).strip()
    if not query:
        return 0
    lowered, q = name.casefold(), query.casefold()
    if lowered.startswith(q):
        return 0
    if q in lowered:
        return 1
    if q in package.casefold():
        return 2
    if all(c in CHO or c.isspace() for c in query):
        initials = "".join(c for c in query if c in CHO)
        candidate = choseong(name)
        if initials and candidate.startswith(initials):
            return 3
        if initials and initials in candidate:
            return 4
    if has_hangul(query) and phonetic_match(query, name):
        return 5
    if has_hangul(name) and q in romanize(name):
        return 5
    return None
