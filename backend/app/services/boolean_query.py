"""Boolean topic queries, Radar-style semantics.

Model: anchor terms (OR — at least one must hit; this is also what gets sent to
source APIs), AND-groups (each group needs >=1 hit), exclude terms (none may hit).
Matching is accent-folded case-insensitive substring — same fold on both sides.

String syntax accepted from the UI:
    (iphone OR "apple phone") AND (launch OR release) NOT (case OR wallpaper)
First parenthesized group = anchor. Bare words outside groups become 1-term AND groups.
"""
import re
import unicodedata
from dataclasses import dataclass, field


def fold(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


@dataclass
class CompiledQuery:
    anchor: list[str] = field(default_factory=list)
    groups: list[list[str]] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)

    def matches(self, text: str) -> bool:
        t = fold(text)
        has = lambda term: fold(term) in t  # noqa: E731
        if self.anchor and not any(has(x) for x in self.anchor):
            return False
        if not all(any(has(x) for x in g) for g in self.groups):
            return False
        return not any(has(x) for x in self.exclude)


_TOKEN = re.compile(r'"([^"]+)"|\(([^)]*)\)|(\bAND\b|\bOR\b|\bNOT\b|-)|([^\s()]+)', re.I)


def _terms(group_body: str) -> list[str]:
    out = []
    for m in re.finditer(r'"([^"]+)"|([^\s]+)', group_body):
        term = m.group(1) or m.group(2)
        if term.upper() != "OR":
            out.append(term)
    return out


def compile_query(q: str) -> CompiledQuery:
    cq = CompiledQuery()
    negate_next = False
    for m in _TOKEN.finditer(q or ""):
        quoted, group, op, word = m.groups()
        if op:
            negate_next = op.upper() == "NOT" or op == "-"
            continue
        terms = _terms(group) if group is not None else [quoted or word]
        terms = [t for t in terms if t]
        if not terms:
            continue
        if negate_next:
            cq.exclude.extend(terms)
            negate_next = False
        elif not cq.anchor:
            cq.anchor = terms
        else:
            cq.groups.append(terms)
    return cq


def to_api_terms(cq: CompiledQuery, cap: int = 4) -> list[str]:
    """Terms to send to a source API that lacks boolean support (per-term calls)."""
    return (cq.anchor or [t for g in cq.groups for t in g])[:cap]


def to_boolean_string(cq: CompiledQuery) -> str:
    """For APIs that DO understand boolean (GDELT, Google News)."""
    quote = lambda t: f'"{t}"' if " " in t else t  # noqa: E731
    parts = []
    if cq.anchor:
        parts.append("(" + " OR ".join(quote(t) for t in cq.anchor) + ")")
    for g in cq.groups:
        parts.append("(" + " OR ".join(quote(t) for t in g) + ")" if len(g) > 1 else quote(g[0]))
    out = " ".join(parts)
    if cq.exclude:
        out += " " + " ".join(f"-{quote(t)}" for t in cq.exclude)
    return out.strip()
