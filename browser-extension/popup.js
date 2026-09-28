// Map a hostname to a CrawlOps platform + the cookie domains to collect.
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
