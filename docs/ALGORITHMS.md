# CrawlOps — Core Algorithms

## 1. AI provider rotation (the "use until limit, move on" engine)

Two layers:

**Layer A — LiteLLM router (config, not code).** Each pipeline task maps to a *model group*
with an ordered fallback chain in `litellm/config.yaml`:

```
judge:   groq/llama-3.3-70b → openrouter :free → mistral-small (free) → hf → deepseek-chat → gpt-4o-mini
enrich:  groq/llama-3.1-8b-instant → openrouter :free → mistral-small → deepseek-chat
agent:   deepseek-chat → gpt-4o-mini            (browser agents need reliable tool-calling)
embed:   mistral-embed → openai text-embedding-3-small → local TF-IDF fallback
```

On HTTP 429 / quota errors LiteLLM marks the deployment "cooling" (`cooldown_time`) and
routes to the next entry. `num_retries` + `allowed_fails` control sensitivity. Every request
is logged to `LiteLLM_SpendLogs` with the model that actually served it.

**Layer B — CrawlOps gateway service (`backend/app/services/gateway.py`).** Wraps the proxy:
- one virtual key per pipeline task → spend segregation per task in the dashboard
- graceful degradation: if *all* providers are cooling/unset, enrichment marks posts
  `enrichment_status=pending` and a catch-up job re-runs them later — ingestion never blocks on AI
- test-connection: 1-token ping per provider, reports latency + served model
- reads LiteLLM spend tables to render the Token Monitor UI (per provider / per task / per day)

## 2. Proxy rotation algorithm (health-scored, sticky-aware)

State per proxy lives in Redis hash `proxy:{id}`: `score` (0..100, start 70), `cooldown_until`,
`success`, `blocked`, `last_used`, `sticky_sessions`.

**Selection** (`ProxyManager.acquire(purpose, sticky_key=None)`):
1. If `sticky_key` given (a Tier-3 platform session): return its bound proxy if healthy —
   a Facebook session must always exit through the same residential IP; IP-hopping mid-session
   is itself a bot signal. If the bound proxy died, retire the session with it.
2. Else filter pool: not cooling, score ≥ 30, tag matches purpose (`residential` for Tier-3,
   `datacenter|none` for Tier-2).
3. Weighted random choice, weight = `score² × recency_boost` — quadratic so healthy proxies
   dominate but sick ones still get probing traffic to recover. `recency_boost = 1 + minutes_idle/30`
   (capped 2×) spreads load and cools per-IP request rates.

**Feedback** (`report(proxy, outcome)`):
- `ok`: score += 2 (cap 100), streak reset
- `soft_block` (429/challenge page/captcha): score −15, cooldown = 5min × 2^consecutive_soft_blocks (cap 6h)
- `hard_block` (403/account flag): score −40, cooldown 12h; bound sticky sessions marked dead
- `net_error`: score −5, cooldown 60s

Empty pool ⇒ direct connection (fine for Tier 1/2; Tier-3 jobs refuse to run without a
residential proxy unless `ALLOW_DIRECT_STEALTH=1`).

## 3. Tier-3 stealth crawl loop (script-first, agent-heal)

```
job(platform, topic):
  session = SessionPool.get(platform)          # camofox tab + cookies + sticky proxy + human pacing profile
  try:
    posts = run_script(platform, topic, session)     # deterministic Playwright-style steps, 0 AI tokens
  except SelectorBroken:
    posts = run_agent(platform, topic, session)      # browser-use agent via gateway 'agent' group,
                                                     # extracts posts AND proposes new selectors
    store_selector_patch(platform, agent.selectors)  # next run tries patched script first
  human_pacing: randomized dwell 2-8s, scroll bursts, jittered intervals, per-session daily caps
  quota: max N pages/session/day; sessions rest ≥6h after cap → mimics human usage curve
```

Detection resistance = camofox fingerprint (C++-level) + sticky residential IP + human pacing
+ low per-identity volume. No single trick; the *budget discipline* is what keeps sessions alive.

## 4. Dedup (exact + near-duplicate)

1. **Identity key**: `sha1(platform + native_post_id)` — same post refetched updates engagement
   metrics in place (time-series table `post_metrics`) instead of duplicating.
2. **Near-dup (crossposts/spam farms)**: 64-bit SimHash over normalized text (lowercase,
   strip URLs/mentions/emoji, 3-gram shingles). Hamming distance ≤ 6 ⇒ same `dup_group`;
   4×16-bit band index in Postgres makes candidate lookup O(log n). Feed shows one card
   per dup_group with a "+N reposts" badge; analytics count the whole group toward reach.

## 5. Story clustering

- Embed title+text via gateway `embed` group (offline fallback: hashed TF-IDF vectors, pure Python).
- **Incremental**: new post joins nearest cluster centroid if cosine ≥ 0.82 (news) / 0.78 (social),
  else founds a new cluster. Centroid = running mean.
- **Nightly re-cluster** over a 72h sliding window with greedy agglomerative merge (centroid
  cosine ≥ 0.85) to fix drift. Cluster label = medoid post title, LLM-polished when budget allows.

## 6. Sentiment + relevance judge (OpenMagpie-style)

One combined LLM call per post (halves token cost vs two calls). Input: topic criteria +
post text (truncated 1,500 chars) + author + platform. Output (JSON, schema-validated):
`{relevant: bool, relevance: 0-100, sentiment: neg|neu|pos, sentiment_score: -1..1,
language, topics[≤3], is_spam_or_bot_suspect: bool}` — one retry on invalid JSON, then a
cheap-regex fallback marks it `enrichment_status=failed_llm` for the catch-up job.
Relevance < topic.threshold (default 55) ⇒ stored but hidden (auditable, like OpenMagpie).

## 7. Spike detection (alerts)

Per topic, hourly buckets. EWMA baseline (α=0.3, 7-day warmup) + residual MAD.
Alert when `count > baseline + max(4×MAD, 5)` for 2 consecutive buckets — the MAD floor
suppresses low-volume noise; a topic doing 2→7 posts/hour is a spike, 0→2 is not.

## 8. Reach & EMV (Radar-style heuristics)

- `reach ≈ followers × platform_view_rate` (FB 0.06, IG 0.09, Threads 0.05, X 0.12, Reddit
  subreddit_size × 0.01, news domain_authority-based table); engagement fallback when
  followers unknown: `(likes+3×comments+5×shares) × 15`.
- `EMV = reach × CPM_platform / 1000` — CPM table editable in Settings (defaults: news RM24,
  FB RM12, IG RM14, X RM8, Threads RM8, Reddit RM6). Honest heuristic, labeled as such in UI.

## 9. Geo pipeline (map view)

NER locations from judge output (`topics` prompt also extracts `locations[]`) → Nominatim
geocode (1 req/s, results cached forever in `geo_cache`) → post gets `lat/lon` + `geo_confidence`.
Map = Leaflet marker clusters, filterable by the same facets as the feed.

## 10. Suppression ("internal shadowban")

`suppressed_authors(platform, author_key, mode)` — `mode=hide` (excluded from feed+analytics),
`mode=watch` (visible, excluded from analytics, flagged badge). Enforced at query layer
(API + Meilisearch filter), never by deleting data — reversible, auditable.
