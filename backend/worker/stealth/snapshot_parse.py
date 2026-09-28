"""Keyless post extraction from a camofox ARIA snapshot.

The snapshot is Playwright's indented YAML-ish accessibility tree:

    - article "…":
      - link "Careta" [e45]:
        - /url: https://www.facebook.com/caretadotmy?__cft__[0]=…
      - link [e47]:
        - /url: https://www.facebook.com/caretadotmy/posts/pfbid02ah…
      - text: Perodua Bezza terus kekal sebagai model paling laris …
      - link "Santan S&P BELI & MENANG …" [e37]:      <- image alt text
        - /url: https://www.facebook.com/photo/?fbid=…

Each node is parsed on its own line (role, quoted name, refs, inline value), so a
stray quote can never swallow the tree around it — which is what the old
"any long quoted string" regex did, leaking `[e45]` / `- /url:` into post text.
"""
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import parse_qs, urljoin, urlsplit

from ..connectors.base import RawMention

_NODE = re.compile(
    r"""^(?P<indent>\s*)-\s+'?(?P<role>[/\w-]+)'?      # role, or /url
        (?:\s+"(?P<name>(?:[^"\\]|\\.)*)")?            # optional "accessible name"
        (?P<attrs>(?:\s*\[[^\]]*\])*)                  # [e45] [level=3] …
        \s*(?P<rest>.*)$""", re.X)

BODY_ROLES = {"text", "paragraph", "strong", "emphasis", "heading", "listitem", "code"}
# UI chrome that shows up as text nodes around every post
NOISE = re.compile(
    r"^(?:…|\.\.\.|·|see more|see less|see translation|follow|join|like|comment|share|"
    r"reply|send|more|most relevant|all reactions:?|write a comment…?|\d+[smhdw]|just now)$",
    re.I)
MEDIA_PATH = re.compile(r"/(?:photo|photos|video|videos|watch|reel)(?:/|\.php|\?|$)", re.I)

HOSTS = {"facebook": "https://www.facebook.com", "instagram": "https://www.instagram.com",
         "tiktok": "https://www.tiktok.com", "x": "https://x.com",
         "threads": "https://www.threads.net"}


@dataclass
class _Node:
    depth: int
    role: str
    name: str
    value: str
    url: str = ""


def _parse_nodes(block: str) -> list[_Node]:
    nodes: list[_Node] = []
    for line in block.splitlines():
        m = _NODE.match(line)
        if not m:
            continue
        role, rest = m["role"], m["rest"].strip()
        name = (m["name"] or "").replace('\\"', '"').strip()
        if role == "/url":
            # attach to the nearest shallower node (the link/img that owns it)
            url = rest.lstrip(":").strip()
            depth = len(m["indent"])
            for n in reversed(nodes):
                if n.depth < depth:
                    n.url = n.url or url
                    break
            continue
        value = rest[1:].strip() if rest.startswith(":") else ""
        if not name and rest and not rest.startswith(":"):
            # unquoted name glued after the ref, e.g. `- link [e37]Santan S&P …:`
            name = rest.rstrip(":").strip()
        nodes.append(_Node(len(m["indent"]), role, name, value))
    return nodes


def _clean_url(url: str, platform: str) -> str:
    """Absolute URL minus Facebook's per-view tracking params (__cft__, __tn__ …)."""
    if not url:
        return ""
    url = urljoin(HOSTS.get(platform, "https://example.com") + "/", url)
    parts = urlsplit(url)
    keep = {k: v for k, v in parse_qs(parts.query).items()
            if not k.startswith("__") and k not in ("hoisted_section_header_type", "ref")}
    query = "&".join(f"{k}={v[0]}" for k, v in keep.items())
    return f"{parts.scheme}://{parts.netloc}{parts.path}" + (f"?{query}" if query else "")


def _permalink(url: str, platform: str) -> tuple[str, str] | None:
    """(canonical permalink, stable post id) if the URL points at a single post."""
    u = _clean_url(url, platform)
    parts = urlsplit(u)
    q = parse_qs(parts.query)
    path = parts.path
    if platform == "facebook":
        if "multi_permalinks" in q:  # group feed link to one post
            g = re.search(r"/groups/([^/]+)", path)
            pid = q["multi_permalinks"][0]
            if g:
                return f"https://www.facebook.com/groups/{g.group(1)}/posts/{pid}/", pid
        if "story_fbid" in q:
            return u, q["story_fbid"][0]
        m = re.search(r"/(?:posts|permalink)/([\w-]+)", path)
        if m:
            return u, m.group(1)
        return None
    patterns = {"x": r"/status/(\d+)", "instagram": r"/(?:p|reel)/([\w-]+)",
                "tiktok": r"/video/(\d+)", "threads": r"/post/([\w-]+)"}
    m = re.search(patterns.get(platform, r"$^"), path)
    return (u, m.group(1)) if m else None


def _author(nodes: list[_Node], platform: str) -> tuple[str, str]:
    """(display name, stable key). The first named link to a profile/page/group."""
    for n in nodes:
        if n.role != "link" or not n.name or not n.url:
            continue
        if MEDIA_PATH.search(n.url) or _permalink(n.url, platform):
            continue
        name = re.sub(r",\s*view story$", "", n.name, flags=re.I).strip()
        if len(name) > 80 or NOISE.match(name):
            continue
        path = urlsplit(_clean_url(n.url, platform)).path.strip("/")
        return name, path or name
    return "", ""


def _body(nodes: list[_Node]) -> str:
    """Post text: the text-ish nodes in document order, UI chrome dropped."""
    parts: list[str] = []
    for n in nodes:
        if n.role not in BODY_ROLES:
            continue
        t = (n.value or n.name).strip().strip("'\"")
        if not t or NOISE.match(t):
            continue
        t = re.sub(r"\s*…\s*(see more)?$", "…", t, flags=re.I)
        if parts and t == parts[-1]:
            continue
        parts.append(t)
    return "\n".join(parts).strip()


def split_articles(snapshot: str) -> list[str]:
    """Top-level `- article` blocks: each runs until the next line at or above its indent."""
    lines = snapshot.splitlines()
    blocks, cur, cur_indent = [], None, 0
    for line in lines:
        m = re.match(r"^(\s*)-\s+article\b", line)
        indent = len(line) - len(line.lstrip())
        if m:
            if cur:
                blocks.append("\n".join(cur))
            cur, cur_indent = [line], len(m.group(1))
            continue
        if cur is not None:
            if line.strip() and indent <= cur_indent:
                blocks.append("\n".join(cur))
                cur = None
            else:
                cur.append(line)
    if cur:
        blocks.append("\n".join(cur))
    return blocks


def extract_posts(platform: str, snapshot: str, limit: int = 20) -> list[RawMention]:
    out: list[RawMention] = []
    seen: set[str] = set()
    for block in split_articles(snapshot)[:limit * 2]:
        nodes = _parse_nodes(block)
        text = _body(nodes)
        if len(text) < 20:
            continue
        link = next((pl for n in nodes if n.url and (pl := _permalink(n.url, platform))), None)
        url, post_id = link if link else ("", "")
        # stable across runs so the central dedup recognises a re-crawled post
        # (the old abs(hash(text)) changed every process start: PYTHONHASHSEED)
        native = post_id or hashlib.sha1(text.encode()).hexdigest()[:16]
        if native in seen:
            continue
        seen.add(native)
        name, key = _author(nodes, platform)
        out.append(RawMention(
            platform=platform, native_id=f"{platform}:{native}", url=url,
            text=text[:3000], author_name=name or "unknown", author_key=key or name or "unknown",
            posted_at=datetime.now(timezone.utc)))
        if len(out) >= limit:
            break
    return out
