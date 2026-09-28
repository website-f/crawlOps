# CrawlOps — Architecture

```
                        ┌────────────────────────────────────────────┐
                        │            frontend (nginx :8400)          │
                        │  Vite/React dashboard — Feed · Topics ·    │
                        │  Analytics · Map · Sources · AI Engine ·   │
                        │  Suppression · Settings                    │
                        └───────────────┬────────────────────────────┘
                                        │ /api
                        ┌───────────────▼────────────────┐
                        │      backend-api (FastAPI)     │
                        │  topics · posts · analytics ·  │
                        │  ai-engine · proxies · sources │
                        └──┬──────────┬──────────┬───────┘
                           │          │          │
        ┌──────────────────▼──┐  ┌────▼─────┐  ┌─▼──────────┐
        │  Postgres (truth)   │  │Meilisearch│  │  Redis     │
        │  posts, topics,     │  │ (facets,  │  │ queues,    │
        │  metrics, clusters, │  │  instant  │  │ proxy state│
        │  spend, geo_cache   │  │  search)  │  │ rate limits│
        └─────────▲───────────┘  └────▲─────┘  └─▲──────────┘
                  │                   │          │
                ┌─┴───────────────────┴──────────┴─┐     ┌──────────────┐
                │        backend-worker            │────▶│    MinIO     │
                │ scheduler → connectors → pipeline│     │ media cache  │
                │ (normalize→dedup→judge→enrich→   │     └──────────────┘
                │  cluster→index→alert)            │
                └──┬──────────────┬────────────────┘
                   │              │
        ┌──────────▼───┐   ┌──────▼─────────────────────┐
        │   LiteLLM    │   │  camofox-browser (:9377)   │
        │  AI gateway  │   │  stealth Firefox REST      │
        │  6 providers │   │  + sticky proxy sessions   │
        └──────────────┘   └────────────────────────────┘
```

## Data model (Postgres)

- **topics** — id, name, query (boolean string), criteria (natural language for the judge),
  threshold, langs[], platforms[], schedule_minutes, active
- **sources** — id, platform, tier(1|2|3), config jsonb (endpoints, keys ref, rsshub route…),
  status, last_run_at, last_error
- **posts** — id, identity_key (unique), platform, native_id, topic_id, author_* (key, name,
  handle, avatar_url, followers, verified), text, html?, lang, url, posted_at, fetched_at,
  media jsonb [{kind, src_url, cache_key, thumb_key, width, height, duration}],
  engagement jsonb {likes, comments, shares, views, reactions{}}, relevance, sentiment,
  sentiment_score, topics[], locations[], lat, lon, geo_confidence, simhash, dup_group,
  cluster_id, is_hidden, enrichment_status
- **post_metrics** — post_id, captured_at, engagement jsonb (time series for growth charts)
- **clusters** — id, topic_id, label, centroid vector (pgvector later; float8[] v1), post_count, window
- **suppressed_authors** — platform, author_key, mode(hide|watch), reason, created_by, created_at
- **proxies** — id, url, tag(residential|datacenter), country, active (runtime state in Redis)
- **stealth_sessions** — id, platform, cookie_ref, proxy_id, status, daily_used, last_used_at
- **alerts** / **alert_events** — rule config + firings
- **geo_cache** — place text → lat/lon/confidence
- **provider_meta** — provider name, litellm model list, enabled, notes (keys live in LiteLLM env/DB, not here)

## Pipeline (worker)

```
every topic.schedule_minutes:
  for each active source matching topic.platforms:
    raw[] = connector.fetch(topic)            # tier 1/2/3 per source
    for raw in raw[]:
      post = normalize(raw)                    # unified Post schema
      if suppressed(post.author): continue     # mode=hide drops early
      if exists(identity_key): update_metrics; continue
      simhash → dup_group
      media[] → MinIO download + thumbnail (ffmpeg for video poster)
      judge+enrich via gateway (or mark pending)
      geo, cluster assign
      insert Postgres → index Meilisearch
  spike_detector(topic) → alert_events → notifiers (email/telegram/webhook)
catch-up job (15min): re-enrich enrichment_status=pending|failed_llm
nightly: re-cluster 72h window, refresh analytics rollups, purge dead sessions
```

## Frontend IA

- **Feed** — platform tabs (All/News/Facebook/Threads/X/Reddit/YouTube/Mastodon/Bluesky/HN),
  platform-native cards (see `frontend/src/components/cards/`), filter drawer (platform, date,
  sentiment, language, media type, engagement min, verified, bot-suspect), boolean chips,
  infinite scroll via Meilisearch
- **Topics** — CRUD, natural-language criteria + boolean query + AI "build query for me"
- **Analytics** — volume over time, sentiment trend, share of voice, top authors/domains, EMV, clusters
- **Map** — Leaflet cluster map of geolocated posts
- **Sources** — connector health, per-tier status, camofox session pool, proxy pool health
- **AI Engine** — provider cards (add key → test connection → latency/model), fallback chain
  editor, token/spend monitor (per provider/task/day), fallback event log
- **Suppression** — muted authors list, add/remove, hide vs watch
- **Settings** — CPM table, thresholds, schedules, notifier channels
