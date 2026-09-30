"""Self-contained copy of the browser extension, zipped on demand.

The extension source lives at repo `/browser-extension`, which is OUTSIDE the
backend Docker build context (`./backend`), so it isn't in the image. Rather
than change the compose build context, we embed the four small files here and
build the .zip in memory (stdlib `zipfile`, no new dependency). Keep this in
sync with `/browser-extension/*` if that ever changes.
"""
import io
import zipfile

MANIFEST = r"""{
  "manifest_version": 3,
  "name": "CrawlOps Connector",
  "version": "1.0.0",
  "description": "Send your logged-in social session (Facebook, Instagram, TikTok, X, Threads) to CrawlOps with one click.",
  "permissions": ["cookies", "activeTab", "storage", "tabs"],
  "host_permissions": [
    "https://*.facebook.com/*",
    "https://*.instagram.com/*",
    "https://*.tiktok.com/*",
    "https://*.x.com/*",
    "https://*.twitter.com/*",
    "https://*.threads.net/*",
    "https://*.threads.com/*",
    "http://*/*",
    "https://*/*"
  ],
  "action": { "default_popup": "popup.html", "default_title": "CrawlOps Connector" }
}
"""

POPUP_HTML = r"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <style>
    body { font: 13px system-ui, -apple-system, "Segoe UI", sans-serif; width: 300px; margin: 0; padding: 14px; color: #0b0b0b; background: #fcfcfb; }
    h1 { font-size: 15px; margin: 0 0 2px; }
    h1 span { color: #2a78d6; }
    .sub { color: #898781; font-size: 11px; margin-bottom: 12px; }
    label { display: block; font-size: 11px; color: #52514e; margin: 8px 0 2px; }
    input { width: 100%; box-sizing: border-box; border: 1px solid #e1e0d9; border-radius: 8px; padding: 7px 9px; font: inherit; }
    button { width: 100%; margin-top: 12px; border: 0; border-radius: 10px; background: #0b0b0b; color: #fff; padding: 10px; font: inherit; font-weight: 600; cursor: pointer; }
    button:disabled { opacity: .5; }
    .platform { margin-top: 10px; padding: 8px 10px; border: 1px solid #e1e0d9; border-radius: 10px; background: #fff; }
    .platform b { text-transform: capitalize; }
    .status { margin-top: 10px; font-size: 12px; border-radius: 8px; padding: 8px 10px; display: none; }
    .ok { background: rgba(12,163,12,.1); color: #006300; display: block; }
    .err { background: rgba(208,59,59,.1); color: #d03b3b; display: block; }
    .muted { color: #898781; }
    details { margin-top: 10px; } summary { cursor: pointer; color: #52514e; font-size: 11px; }
  </style>
</head>
<body>
  <h1>Crawl<span>Ops</span> Connector</h1>
  <div class="sub">Log into a platform in this browser, then send the session to CrawlOps.</div>

  <div class="platform" id="platform-box">
    <span class="muted">Detecting current site…</span>
  </div>

  <button id="connect" disabled>Send session to CrawlOps</button>
  <div class="status" id="status"></div>

  <details id="settings">
    <summary>Settings (CrawlOps URL & token)</summary>
    <label>CrawlOps URL</label>
    <input id="url" placeholder="http://localhost:8400" />
    <label>API token</label>
    <input id="token" placeholder="paste from CrawlOps → Settings" />
  </details>

  <script src="popup.js"></script>
</body>
</html>
"""

POPUP_JS = r"""// Map a hostname to a CrawlOps platform + the cookie domains to collect.
const PLATFORMS = [
  { key: 'facebook', match: /(^|\.)facebook\.com$/, domains: ['.facebook.com'] },
  { key: 'instagram', match: /(^|\.)instagram\.com$/, domains: ['.instagram.com'] },
  { key: 'tiktok', match: /(^|\.)tiktok\.com$/, domains: ['.tiktok.com'] },
  { key: 'x', match: /(^|\.)(x|twitter)\.com$/, domains: ['.x.com', '.twitter.com'] },
  { key: 'threads', match: /(^|\.)threads\.(net|com)$/, domains: ['.threads.net', '.threads.com'] },
]

const $ = (id) => document.getElementById(id)
let current = null

function mapSameSite(s) {
  return s === 'no_restriction' ? 'None' : s === 'strict' ? 'Strict' : s === 'lax' ? 'Lax' : 'Lax'
}

async function collectCookies(domains) {
  const all = []
  for (const d of domains) {
    const ck = await chrome.cookies.getAll({ domain: d })
    for (const c of ck) {
      all.push({
        name: c.name, value: c.value, domain: c.domain, path: c.path || '/',
        secure: !!c.secure, httpOnly: !!c.httpOnly,
        sameSite: mapSameSite(c.sameSite),
        expires: c.expirationDate ? Math.floor(c.expirationDate) : -1,
      })
    }
  }
  return all
}

async function init() {
  const cfg = await chrome.storage.local.get(['url', 'token'])
  $('url').value = cfg.url || 'http://localhost:8400'
  $('token').value = cfg.token || ''
  if (!cfg.token) $('settings').open = true

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
  let host = ''
  try { host = new URL(tab.url).hostname } catch {}
  current = PLATFORMS.find((p) => p.match.test(host)) || null

  if (current) {
    $('platform-box').innerHTML = `Detected <b>${current.key}</b> — make sure you are logged in here.`
    $('connect').disabled = false
  } else {
    $('platform-box').innerHTML = '<span class="muted">Open a Facebook, Instagram, TikTok, X, or Threads tab, then click the extension.</span>'
  }
}

function setStatus(msg, ok) {
  const el = $('status'); el.textContent = msg; el.className = 'status ' + (ok ? 'ok' : 'err')
}

async function connect() {
  const url = $('url').value.replace(/\/$/, '')
  const token = $('token').value.trim()
  await chrome.storage.local.set({ url, token })
  if (!token) { setStatus('Add your CrawlOps API token in Settings.', false); $('settings').open = true; return }
  if (!current) return

  $('connect').disabled = true
  setStatus('Collecting session…', true)
  try {
    const cookies = await collectCookies(current.domains)
    if (!cookies.length) { setStatus('No cookies found — are you logged in on this tab?', false); $('connect').disabled = false; return }
    const r = await fetch(`${url}/api/sources/connect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ platform: current.key, cookies }),
    })
    if (r.ok) {
      const d = await r.json()
      setStatus(`Connected ${current.key} (${d.imported} cookies). You can crawl it now.`, true)
    } else {
      setStatus(`Failed: ${r.status} ${(await r.text()).slice(0, 120)}`, false)
    }
  } catch (e) {
    setStatus(`Error: ${e.message}. Check the CrawlOps URL.`, false)
  }
  $('connect').disabled = false
}

$('connect').addEventListener('click', connect)
init()
"""

README = r"""# CrawlOps Connector (browser extension)

Log into Facebook / Instagram / TikTok / X / Threads normally in your own browser,
then push that logged-in session to CrawlOps with one click. No cookie copying,
no passwords stored, and it captures the secure `httpOnly` auth cookies that a
copy-paste or bookmarklet cannot read.

## Install (one time, per operator)

1. Unzip this folder somewhere permanent (do not delete it after loading).
2. Chrome/Edge/Brave -> `chrome://extensions` -> enable **Developer mode**.
3. **Load unpacked** -> select the unzipped `crawlops-connector` folder.
4. Pin the CrawlOps Connector.

## Get your API token

In CrawlOps -> **Settings -> Browser extension** -> copy the token. Paste it into
the extension's **Settings** (with your CrawlOps URL).

## Use

1. Open the platform (e.g. facebook.com) and **log in** (handle any 2FA/CAPTCHA
   yourself -- you are a real human here).
2. Click the CrawlOps Connector -> **Send session to CrawlOps**.
3. That platform's session goes live; the crawler now browses logged-in as you.

Re-run whenever a session expires (CrawlOps flags it `needs_reauth`).
"""

FILES = {
    "crawlops-connector/manifest.json": MANIFEST,
    "crawlops-connector/popup.html": POPUP_HTML,
    "crawlops-connector/popup.js": POPUP_JS,
    "crawlops-connector/README.md": README,
}


def build_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, content in FILES.items():
            z.writestr(name, content)
    return buf.getvalue()
