# CrawlOps Connector (browser extension)

Log into Facebook / Instagram / TikTok / X / Threads normally in your own browser,
then push that logged-in session to CrawlOps with one click. No cookie copying,
no passwords stored, and it captures the secure `httpOnly` auth cookies that a
copy-paste or bookmarklet cannot read.

## Install (one time, per operator)

1. Chrome/Edge/Brave → `chrome://extensions` → enable **Developer mode**.
2. **Load unpacked** → select this `browser-extension/` folder.
3. Pin the CrawlOps Connector.

## Get your API token

In CrawlOps → **Settings → Browser extension** → copy the token. Paste it into the
extension's **Settings** (with your CrawlOps URL, e.g. `http://localhost:8400`).

## Use

1. Open the platform (e.g. facebook.com) and **log in** (handle any 2FA/CAPTCHA
   yourself — you are a real human here).
2. Click the CrawlOps Connector → **Send session to CrawlOps**.
3. That platform's session goes live; the crawler now browses logged-in as you.

Re-run whenever a session expires (CrawlOps flags it `needs_reauth`). Use a
dedicated account per platform, and add a residential proxy in CrawlOps → Sources
for durable crawling.
