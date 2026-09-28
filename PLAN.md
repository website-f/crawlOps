# CrawlOps — Development Plan

Self-hosted social intelligence platform (Meltwater-class): topic-based crawling across
social platforms + news, unified into one dashboard with platform-native post rendering,
AI enrichment (relevance judging, sentiment, clustering), advanced filtering, map view,
and an internal account-suppression system.

## Design lineage

| Borrowed from | What we take |
|---|---|
| `reference/radar-intelligence` (AGPL-3.0) | Connector-per-file pattern, boolean query model, analytics formulas (EMV, share of voice), dashboard IA |
| `reference/openmagpie` (Apache-2.0) | LLM judge pipeline (score posts against natural-language topic criteria), poll→judge→deliver orchestration |
| LiteLLM (proxy service) | Multi-provider AI rotation: fallback chains, cooldowns, virtual keys, spend logs |
| camofox-browser (MIT, service) | Stealth browser tier for platforms without free APIs (Facebook, Instagram, TikTok) |

> AGPL note: Radar code is *reference only* — we re-implement patterns in our own stack.
> If actual Radar code is ever copied in, CrawlOps inherits AGPL obligations when offered as a service.

## Stack

- **frontend/** — Vite + React 18 + TypeScript + Tailwind. Single dashboard. nginx-served in prod, proxies `/api` → backend.
- **backend/** — Python 3.12 FastAPI (API) + worker process (scheduler, connectors, pipeline). One image, two containers.
- **Postgres 16** — source of truth. **Meilisearch** — faceted instant search. **Redis** — queues, proxy/session state, rate limiting. **MinIO** — media cache (FB/IG CDN URLs are signed + expire; we must own copies).
- **LiteLLM** — AI gateway (openai, deepseek paid; groq, openrouter, mistral, huggingface free tiers).
- **camofox-browser** — stealth browser REST server on :9377 (Tier-3 fetching).
- **RSSHub** (optional profile) — converts hundreds of API-less sites into feeds.

## Ingestion tiers

1. **Tier 1 — free official APIs**: Bluesky (public search, keyless), Mastodon (public tag/search),
   Reddit (public JSON), Hacker News (Algolia), GDELT (doc API), Google News (RSS),
   Threads (official keyword_search, needs Meta app), YouTube (Data API key), Telegram (MTProto creds).
2. **Tier 2 — feed/HTTP scraping**: RSSHub routes + direct RSS + plain HTTP fetch for news/blogs.
3. **Tier 3 — stealth browser**: camofox sessions + per-platform scripts (Facebook public pages,
   Instagram, TikTok) + AI-agent fallback when selectors break. Public content only. Sticky
   proxy binding per session (see ALGORITHMS.md).

## Phases

- [x] **P0 scaffold** — compose stack, docs, schemas, gateway, dashboard shell
- [ ] **P1 Tier-1 ingestion** — 6 keyless connectors live, judge+sentiment pipeline, Meilisearch indexing, media cache
- [ ] **P2 Feed UI** — platform-native cards, filter drawer, boolean builder, saved topics
- [ ] **P3 Tier-3 stealth** — camofox scripts FB/IG/TikTok, twscrape X, proxy pool mgmt UI, agent fallback
- [ ] **P4 Analytics** — sentiment trends, share of voice, clusters, spike alerts, map view, exports
- [ ] **P5 Hardening + deploy** — VPS behind /opt/reverse-proxy, ports 8400-8409, backups

## Port allocation (prod)

| Port | Service |
|---|---|
| 8400 | frontend (nginx) — the only port the reverse proxy needs |
| 8401 | backend API (debug access) |
| 8402 | LiteLLM (admin, LAN only) |
| 8403 | Meilisearch (LAN only) |
| 8404 | MinIO console (LAN only) |

Everything else stays on the internal compose network.
