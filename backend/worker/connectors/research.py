"""Keyless specialized data-source connectors ported from radar-intelligence:
arXiv, SEC EDGAR, Wikipedia, GitHub, Stack Exchange, ClinicalTrials.gov.
All public/keyless. Each returns the unified RawMention; the central pipeline
applies boolean filtering + enrichment as usual.
"""
import html
import re
from datetime import datetime, timezone

import feedparser
from dateutil import parser as dtparse

from app.services.boolean_query import CompiledQuery, to_api_terms

from .base import Connector, RawMention, collect, fetch_json

_TAGS = re.compile(r"<[^>]+>")
SEC_UA = "CrawlOps research monitor contact@crawlops.local"


class ArXiv(Connector):
    key = "arxiv"
    platform = "arxiv"

    async def fetch(self, cq: CompiledQuery) -> list[RawMention]:
        return await collect(self._q(t) for t in to_api_terms(cq, 3))

    async def _q(self, term: str) -> list[RawMention]:
        import httpx
        from .base import UA
        sq = f'all:"{term}"' if " " in term else f"all:{term}"
        async with httpx.AsyncClient(timeout=25) as c:
            r = await c.get("http://export.arxiv.org/api/query",
                            params={"search_query": sq, "start": 0, "max_results": 25,
                                    "sortBy": "submittedDate", "sortOrder": "descending"},
                            headers={"User-Agent": UA})
        feed = feedparser.parse(r.text)
        out = []
        for e in feed.entries[:25]:
            authors = ", ".join(a.get("name", "") for a in e.get("authors", [])[:3])
            out.append(RawMention(
                platform="arxiv", native_id=e.get("id", ""), url=e.get("link", ""),
                title=_TAGS.sub(" ", e.get("title", ""))[:300],
                text=_TAGS.sub(" ", e.get("summary", ""))[:1500],
                author_name=authors or "arXiv", author_key=authors[:100],
                posted_at=dtparse.parse(e["published"]) if e.get("published") else None,
                lang="en", community="arXiv"))
        return out


class SecEdgar(Connector):
    key = "sec"
    platform = "sec"

    async def fetch(self, cq: CompiledQuery) -> list[RawMention]:
        return await collect(self._q(t) for t in to_api_terms(cq, 2))

    async def _q(self, term: str) -> list[RawMention]:
        data = await fetch_json("https://efts.sec.gov/LATEST/search-index",
                                params={"q": term}, headers={"User-Agent": SEC_UA})
        out = []
        for h in (data.get("hits", {}).get("hits", []) if isinstance(data, dict) else [])[:25]:
            src = h.get("_source", {})
            cik = (src.get("cik") or [""])[0] if isinstance(src.get("cik"), list) else src.get("cik", "")
            adsh = src.get("adsh", h.get("_id", "")).split(":")[0]
            out.append(RawMention(
                platform="sec", native_id=h.get("_id", ""),
                url=f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}",
                title=f"{src.get('display_names', ['SEC filing'])[0]} — {src.get('form', 'filing')}"[:300],
                text=" ".join(src.get("display_names", []))[:1500],
                author_name=(src.get("display_names") or ["SEC"])[0][:100],
                author_key=str(cik), domain="sec.gov",
                posted_at=dtparse.parse(src["file_date"]) if src.get("file_date") else None,
                lang="en", community="SEC EDGAR"))
        return out


class Wikipedia(Connector):
    key = "wikipedia"
    platform = "wikipedia"

    async def fetch(self, cq: CompiledQuery) -> list[RawMention]:
        return await collect(self._q(t) for t in to_api_terms(cq, 3))

    async def _q(self, term: str) -> list[RawMention]:
        data = await fetch_json("https://en.wikipedia.org/w/api.php",
                                params={"action": "query", "list": "search", "srsearch": term,
                                        "srsort": "last_edit_desc", "srlimit": 20, "format": "json"})
        out = []
        for s in (data.get("query", {}).get("search", []) if isinstance(data, dict) else []):
            title = s.get("title", "")
            out.append(RawMention(
                platform="wikipedia", native_id=f"wiki:{s.get('pageid')}",
                url=f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                title=title[:300],
                text=_TAGS.sub(" ", html.unescape(s.get("snippet", "")))[:1500],
                author_name="Wikipedia", author_key="wikipedia", domain="wikipedia.org",
                posted_at=dtparse.parse(s["timestamp"]) if s.get("timestamp") else None,
                lang="en", community="Wikipedia"))
        return out


class GitHub(Connector):
    key = "github"
    platform = "github"

    async def fetch(self, cq: CompiledQuery) -> list[RawMention]:
        return await collect(self._q(t) for t in to_api_terms(cq, 2))

    async def _q(self, term: str) -> list[RawMention]:
        data = await fetch_json("https://api.github.com/search/repositories",
                                params={"q": term, "sort": "updated", "order": "desc", "per_page": 20},
                                headers={"Accept": "application/vnd.github+json"})
        out = []
        for it in (data.get("items", []) if isinstance(data, dict) else [])[:20]:
            owner = it.get("owner", {}).get("login", "")
            out.append(RawMention(
                platform="github", native_id=str(it.get("id")),
                url=it.get("html_url", ""), title=it.get("full_name", "")[:300],
                text=(it.get("description") or it.get("full_name") or "")[:1500],
                author_name=owner, author_key=owner, domain="github.com",
                posted_at=dtparse.parse(it["updated_at"]) if it.get("updated_at") else None,
                lang="en", community="GitHub",
                engagement={"likes": it.get("stargazers_count", 0)}))
        return out


class StackExchange(Connector):
    key = "stackexchange"
    platform = "stackexchange"

    async def fetch(self, cq: CompiledQuery) -> list[RawMention]:
        return await collect(self._q(t) for t in to_api_terms(cq, 2))

    async def _q(self, term: str) -> list[RawMention]:
        data = await fetch_json("https://api.stackexchange.com/2.3/search/advanced",
                                params={"order": "desc", "sort": "creation", "q": term,
                                        "site": "stackoverflow", "pagesize": 20})
        out = []
        for it in (data.get("items", []) if isinstance(data, dict) else [])[:20]:
            out.append(RawMention(
                platform="stackexchange", native_id=str(it.get("question_id")),
                url=it.get("link", ""), title=html.unescape(it.get("title", ""))[:300],
                text=html.unescape(it.get("title", ""))[:1500],
                author_name=it.get("owner", {}).get("display_name", ""),
                author_key=str(it.get("owner", {}).get("user_id", "")),
                domain="stackoverflow.com", community="Stack Overflow",
                posted_at=datetime.fromtimestamp(it.get("creation_date", 0), tz=timezone.utc),
                engagement={"likes": it.get("score", 0), "comments": it.get("answer_count", 0)}))
        return out


class ClinicalTrials(Connector):
    key = "clinicaltrials"
    platform = "clinicaltrials"

    async def fetch(self, cq: CompiledQuery) -> list[RawMention]:
        return await collect(self._q(t) for t in to_api_terms(cq, 2))

    async def _q(self, term: str) -> list[RawMention]:
        data = await fetch_json("https://clinicaltrials.gov/api/v2/studies",
                                params={"query.term": term, "pageSize": 20,
                                        "sort": "LastUpdatePostDate:desc"})
        out = []
        for st in (data.get("studies", []) if isinstance(data, dict) else [])[:20]:
            ps = st.get("protocolSection", {})
            idm = ps.get("identificationModule", {})
            nct = idm.get("nctId", "")
            status = ps.get("statusModule", {})
            out.append(RawMention(
                platform="clinicaltrials", native_id=nct,
                url=f"https://clinicaltrials.gov/study/{nct}",
                title=(idm.get("briefTitle") or "")[:300],
                text=(ps.get("descriptionModule", {}).get("briefSummary") or idm.get("briefTitle") or "")[:1500],
                author_name=(idm.get("organization", {}) or {}).get("fullName", "")[:100],
                author_key="clinicaltrials", domain="clinicaltrials.gov", community="ClinicalTrials.gov",
                posted_at=dtparse.parse(status["lastUpdatePostDateStruct"]["date"])
                if status.get("lastUpdatePostDateStruct", {}).get("date") else None,
                lang="en"))
        return out
