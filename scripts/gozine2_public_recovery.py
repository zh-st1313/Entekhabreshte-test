#!/usr/bin/env python3
import csv, html, json, os, re, sys, time
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse
import requests
from bs4 import BeautifulSoup

OUT = Path("artifacts/gozine2")
MEDIA = OUT / "media"
ARCHIVE = OUT / "wayback_html"
OUT.mkdir(parents=True, exist_ok=True)
MEDIA.mkdir(parents=True, exist_ok=True)
ARCHIVE.mkdir(parents=True, exist_ok=True)

S = requests.Session()
S.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; Gozine2PublicArchiveResearch/1.0; +https://github.com/zh-st1313/Entekhabreshte-test)"
})

CHANNELS = [
    "gozine2", "G2_konkur99", "g2_old", "G2_konkur",
    "gozine2ahwaz", "gozine2neka", "gozine_dorost",
]

QUERIES = [
    "#کارنامه_کنکور97", "#کارنامه_کنکور۹۸",
    "#کارنامه_کنکور۱۴۰۰", "#کارنامه_کنکور۱۴۰۱",
    "#کارنامه_کنکور۱۴۰۲", "#کارنامه_کنکور۱۴۰۳",
    "#کارنامه_پذیرفته_شدگان",
]

KNOWN_SHORTS = [
    "https://bit.ly/2HCotVQ",
    "https://bit.ly/2nkXvy2",
    "https://bit.ly/2TOWf13",
]

WAYBACK_PATTERNS = [
    "student.gozine2.ir/KonkurResult/*",
    "student.gozine2.ir/konkurresult/*",
    "student.gozine2.ir/FieldStatistic/*",
    "student.gozine2.ir/fieldstatistic/*",
]

def get(url, **kw):
    kw.setdefault("timeout", 25)
    for attempt in range(3):
        try:
            r = S.get(url, **kw)
            return r
        except Exception:
            if attempt == 2:
                raise
            time.sleep(1.5 * (attempt + 1))

def clean_text(node):
    if not node:
        return ""
    txt = node.get_text("\n", strip=True)
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt

def parse_message(wrap, channel, query):
    msg = wrap.select_one(".tgme_widget_message")
    if not msg:
        return None
    post = msg.get("data-post", "")
    msg_id = post.split("/")[-1] if "/" in post else ""
    text_node = wrap.select_one(".tgme_widget_message_text")
    text = clean_text(text_node)
    date_a = wrap.select_one(".tgme_widget_message_date")
    date = ""
    permalink = ""
    if date_a:
        permalink = date_a.get("href", "")
        t = date_a.find("time")
        if t:
            date = t.get("datetime", "")
    if not permalink and post:
        permalink = "https://t.me/" + post

    photos = []
    for el in wrap.select('[style*="background-image"]'):
        style = el.get("style", "")
        m = re.search(r'background-image\s*:\s*url\([\'"]?(.*?)[\'"]?\)', style)
        if m:
            u = html.unescape(m.group(1))
            if u.startswith("//"):
                u = "https:" + u
            photos.append(u)
    photos = list(dict.fromkeys(photos))

    # Extract fields that remain in Telegram captions.
    def first(pats):
        for p in pats:
            m = re.search(p, text, re.I)
            if m:
                return m.group(1).strip()
        return ""

    year = first([r"کارنامه[_\s]*کنکور\s*([۰-۹0-9]{2,4})"])
    group = ""
    for g in ["تجربی", "ریاضی", "انسانی", "هنر", "زبان"]:
        if g in text:
            group = g
            break
    quota = first([r"#?منطقه\s*([۱۲۳123])", r"#?منطقه([۱۲۳123])"])
    major = first([
        r"📍\s*#?([^\n]+)",
        r"🎓\s*#?([^\n]+)",
    ])
    university = first([
        r"📌\s*([^\n]+)",
        r"🏫\s*([^\n]+)",
    ])
    return {
        "channel": channel,
        "query": query,
        "post": post,
        "message_id": msg_id,
        "permalink": permalink,
        "date": date,
        "year_text": year,
        "group": group,
        "quota_region": quota,
        "major_raw": major,
        "university_raw": university,
        "text": text,
        "photo_urls": photos,
    }

def crawl_search(channel, query, max_pages=5):
    url = f"https://t.me/s/{channel}?q={quote(query)}"
    seen_urls = set()
    seen_posts = set()
    rows = []
    for _ in range(max_pages):
        if url in seen_urls:
            break
        seen_urls.add(url)
        r = get(url)
        if r.status_code != 200:
            break
        soup = BeautifulSoup(r.text, "lxml")
        for wrap in soup.select(".tgme_widget_message_wrap"):
            row = parse_message(wrap, channel, query)
            if row and row["post"] and row["post"] not in seen_posts:
                seen_posts.add(row["post"])
                rows.append(row)

        more = soup.select_one("a.tme_messages_more")
        if not more or not more.get("href"):
            break
        nxt = urljoin("https://t.me", more["href"])
        # Keep pagination scoped to the same search query.
        if "q=" not in nxt:
            sep = "&" if "?" in nxt else "?"
            nxt += sep + "q=" + quote(query)
        url = nxt
        time.sleep(0.4)
    return rows

def download_photos(rows, max_downloads=80):
    n = 0
    manifest = []
    for row in rows:
        for i, url in enumerate(row.get("photo_urls") or []):
            if n >= max_downloads:
                return manifest
            try:
                r = get(url)
                ctype = r.headers.get("content-type", "")
                if r.status_code != 200 or "image" not in ctype:
                    continue
                ext = ".jpg"
                if "png" in ctype:
                    ext = ".png"
                elif "webp" in ctype:
                    ext = ".webp"
                channel = re.sub(r"[^A-Za-z0-9_-]+", "_", row["channel"])
                mid = row["message_id"] or str(n)
                name = f"{channel}_{mid}_{i}{ext}"
                path = MEDIA / name
                path.write_bytes(r.content)
                manifest.append({
                    "file": str(path),
                    "source_url": url,
                    "post": row["post"],
                    "permalink": row["permalink"],
                })
                n += 1
            except Exception as e:
                manifest.append({"error": str(e), "source_url": url, "post": row["post"]})
    return manifest

def resolve_shortlinks():
    out = []
    for u in KNOWN_SHORTS:
        try:
            r = get(u, allow_redirects=False)
            out.append({
                "short_url": u,
                "status": r.status_code,
                "location": r.headers.get("location", ""),
            })
        except Exception as e:
            out.append({"short_url": u, "error": str(e)})
    return out

def cdx(pattern):
    endpoint = "https://web.archive.org/cdx/search/cdx"
    params = {
        "url": pattern,
        "output": "json",
        "fl": "timestamp,original,statuscode,mimetype,digest",
        "filter": "statuscode:200",
        "collapse": "digest",
    }
    r = S.get(endpoint, params=params, timeout=45)
    r.raise_for_status()
    data = r.json()
    if not data:
        return []
    head = data[0]
    return [dict(zip(head, row)) for row in data[1:]]

def parse_archived_html(text, base_url):
    soup = BeautifulSoup(text, "lxml")
    forms = []
    for f in soup.find_all("form"):
        forms.append({
            "action": urljoin(base_url, f.get("action") or ""),
            "method": (f.get("method") or "GET").upper(),
            "inputs": [
                {"name": x.get("name", ""), "type": x.get("type", ""), "value": x.get("value", "")}
                for x in f.find_all(["input", "select", "textarea"])
            ],
        })
    scripts = [urljoin(base_url, x.get("src")) for x in soup.find_all("script") if x.get("src")]
    links = []
    for a in soup.find_all("a", href=True):
        h = urljoin(base_url, a["href"])
        if any(k.lower() in h.lower() for k in ["konkur", "result", "fieldstat", "accept"]):
            links.append(h)
    urls_in_text = sorted(set(re.findall(r'https?://[^\s"\'<>]+', text)))
    interesting = [u for u in urls_in_text if any(k in u.lower() for k in ["konkur", "result", "fieldstat", "ajax", "api"])]
    return {
        "forms": forms,
        "scripts": sorted(set(scripts)),
        "interesting_links": sorted(set(links + interesting)),
    }

def archive_probe(captures, max_html=20):
    probes = []
    # Choose spread across time rather than blindly first N.
    if len(captures) > max_html:
        step = max(1, len(captures)//max_html)
        selected = captures[::step][:max_html]
    else:
        selected = captures[:max_html]
    for c in selected:
        ts = c["timestamp"]
        orig = c["original"]
        replay = f"https://web.archive.org/web/{ts}id_/{orig}"
        item = dict(c)
        item["replay_url"] = replay
        try:
            r = get(replay)
            item["fetch_status"] = r.status_code
            item["final_url"] = r.url
            if r.status_code == 200 and "html" in r.headers.get("content-type", ""):
                safe = re.sub(r"[^A-Za-z0-9._-]+", "_", f"{ts}_{urlparse(orig).path.strip('/') or 'root'}")[:180]
                p = ARCHIVE / (safe + ".html")
                p.write_text(r.text, encoding="utf-8")
                item["saved_html"] = str(p)
                item.update(parse_archived_html(r.text, orig))
        except Exception as e:
            item["error"] = str(e)
        probes.append(item)
        time.sleep(0.5)
    return probes

def write_outputs(rows, media_manifest, shortlinks, captures, probes):
    # Deduplicate posts across repeated search queries.
    dedup = {}
    for r in rows:
        key = r["post"] or r["permalink"] or json.dumps(r, ensure_ascii=False)
        if key not in dedup:
            dedup[key] = r
        else:
            existing = dedup[key]
            qs = set((existing.get("query") or "").split(" | "))
            qs.add(r.get("query") or "")
            existing["query"] = " | ".join(sorted(x for x in qs if x))
            existing["photo_urls"] = list(dict.fromkeys((existing.get("photo_urls") or []) + (r.get("photo_urls") or [])))
    rows = list(dedup.values())

    (OUT / "telegram_posts.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    with (OUT / "telegram_posts.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    fields = ["channel","message_id","date","year_text","group","quota_region","major_raw","university_raw","permalink","query","text"]
    with (OUT / "telegram_posts.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})

    (OUT / "media_manifest.json").write_text(json.dumps(media_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "shortlink_resolution.json").write_text(json.dumps(shortlinks, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "wayback_cdx.json").write_text(json.dumps(captures, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "wayback_probe.json").write_text(json.dumps(probes, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {
        "unique_telegram_posts": len(rows),
        "downloaded_or_attempted_media": len(media_manifest),
        "wayback_captures": len(captures),
        "wayback_pages_probed": len(probes),
        "shortlinks": shortlinks,
        "years_seen": sorted(set(r.get("year_text") for r in rows if r.get("year_text"))),
        "channels_seen": sorted(set(r.get("channel") for r in rows if r.get("channel"))),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

def main():
    all_rows = []
    failures = []
    for ch in CHANNELS:
        for q in QUERIES:
            try:
                rows = crawl_search(ch, q)
                if rows:
                    print(f"{ch} | {q}: {len(rows)}")
                    all_rows.extend(rows)
            except Exception as e:
                failures.append({"channel": ch, "query": q, "error": str(e)})
    (OUT / "crawl_failures.json").write_text(json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")

    shortlinks = resolve_shortlinks()

    captures = []
    for pat in WAYBACK_PATTERNS:
        try:
            captures.extend(cdx(pat))
        except Exception as e:
            captures.append({"pattern": pat, "error": str(e)})
    uniq = {}
    for c in captures:
        key = (c.get("timestamp"), c.get("original"), c.get("digest"))
        uniq[key] = c
    captures = list(uniq.values())
    good_caps = [c for c in captures if c.get("timestamp") and c.get("original")]
    probes = archive_probe(good_caps)

    media_manifest = download_photos(all_rows)
    write_outputs(all_rows, media_manifest, shortlinks, captures, probes)

if __name__ == "__main__":
    main()
