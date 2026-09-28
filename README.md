# CrawlOps — self-hosted social intelligence

Meltwater-class monitoring: topic-based crawling across news + social platforms, one
dashboard, platform-native post rendering, AI relevance/sentiment via a rotating
multi-provider gateway, clustering, map view, and internal account suppression.

Docs: [PLAN.md](PLAN.md) · [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · [docs/ALGORITHMS.md](docs/ALGORITHMS.md)

## Quick start

```bash
cp .env.example .env          # add AI provider keys (any subset; blanks are skipped)
docker compose up -d --build
# dashboard: http://localhost:8400
```

Create a topic in the UI (or let the "✨ AI build" button write the boolean query +
judge criteria) — the worker starts crawling within 30 seconds. Six connectors work
with zero keys: Bluesky, Mastodon, Reddit, Hacker News, GDELT, Google News.

## Optional pieces

| Piece | Enable with |
|---|---|
| Threads (official keyword API) | `THREADS_ACCESS_TOKEN` in .env |
| YouTube | `YOUTUBE_API_KEY` in .env |
| Stealth tier (Facebook/Instagram via camofox) | `docker compose --profile stealth up -d` + residential proxies in Sources UI + session cookies |
| RSSHub feed multiplier | `docker compose --profile extras up -d` |

## Services

frontend :8400 (nginx, the only port the reverse proxy needs) · backend-api :8401 ·
LiteLLM :8402 · Meilisearch :8403 · MinIO console :8404 · postgres/redis/worker internal.

## Ops notes

- AI rotation order and model IDs live in `litellm/config.yaml` (free tiers first).
- Free-tier model names churn — when a provider 400s on a model, update it there and
  `docker compose restart litellm`.
- The stealth tier scrapes **public content only**, violates Meta/X ToS, and needs
  residential proxies; sessions have daily caps and rest periods by design.
- `reference/` holds the two upstream repos studied for this build (radar-intelligence
  is AGPL — patterns were re-implemented, not copied).
