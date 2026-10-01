#!/usr/bin/env python3
import hashlib, html, json, re, time
from pathlib import Path
from urllib.parse import quote, urljoin
import requests
from bs4 import BeautifulSoup

OUT=Path("artifacts/gozine2-expanded")
MEDIA=OUT/"media"
OUT.mkdir(parents=True,exist_ok=True)
MEDIA.mkdir(parents=True,exist_ok=True)

S=requests.Session()
S.headers.update({"User-Agent":"Mozilla/5.0 Gozine2PublicTelegramArchiveResearch/2.0"})

CHANNELS=[
 "G2_konkur406","G2_konkur1407","G2_konkur1401"
]
QUERIES=[
 "#کارنامه_کنکور98","#کارنامه_کنکور۹۸",
 "#کارنامه_کنکور99","#کارنامه_کنکور۹۹",
 "#کارنامه_کنکور1401","#کارنامه_کنکور۱۴۰۱",
 "#کارنامه_کنکور1402","#کارنامه_کنکور۱۴۰۲",
 "#کارنامه_پذیرفته_شدگان"
]

def get(url, timeout=15):
    last=None
    for i in range(2):
        try:
            return S.get(url,timeout=timeout)
        except Exception as e:
            last=e; time.sleep(1+i)
    raise last

def parse(wrap,ch,q):
    msg=wrap.select_one(".tgme_widget_message")
    if not msg:return None
    post=msg.get("data-post","")
    if not post:return None
    text_el=wrap.select_one(".tgme_widget_message_text")
    text=text_el.get_text("\n",strip=True) if text_el else ""
    date=""
    da=wrap.select_one(".tgme_widget_message_date time")
    if da: date=da.get("datetime","")
    photos=[]
    for el in wrap.select('[style*="background-image"]'):
        st=el.get("style","")
        m=re.search(r'background-image\s*:\s*url\([\'"]?(.*?)[\'"]?\)',st)
        if m:
            u=html.unescape(m.group(1))
            if u.startswith("//"):u="https:"+u
            photos.append(u)
    photos=list(dict.fromkeys(photos))
    year=""
    m=re.search(r"کارنامه[_\s]*کنکور\s*([۰-۹0-9]{2,4})",text)
    if m: year=m.group(1)
    elif "کنکور\n۹۹" in text or "کنکور ۹۹" in text: year="۹۹"
    elif "کنکور\n۱۴۰۱" in text or "کنکور ۱۴۰۱" in text: year="۱۴۰۱"
    elif "کنکور\n۱۴۰۳" in text or "کنکور ۱۴۰۳" in text: year="۱۴۰۳"
    return {"post":post,"channel":ch,"query":q,"date":date,"year_text":year,
            "permalink":"https://t.me/"+post,"text":text,"photo_urls":photos}

def crawl(ch,q,max_pages=3):
    url=f"https://t.me/s/{ch}?q={quote(q)}"
    seen_urls=set(); seen_posts=set(); rows=[]
    for _ in range(max_pages):
        if url in seen_urls:break
        seen_urls.add(url)
        r=get(url)
        if r.status_code!=200:break
        soup=BeautifulSoup(r.text,"lxml")
        for wrap in soup.select(".tgme_widget_message_wrap"):
            row=parse(wrap,ch,q)
            if row and row["post"] not in seen_posts:
                seen_posts.add(row["post"]); rows.append(row)
        more=soup.select_one("a.tme_messages_more")
        if not more or not more.get("href"):break
        nxt=urljoin("https://t.me",more["href"])
        if "q=" not in nxt:
            nxt += ("&" if "?" in nxt else "?")+"q="+quote(q)
        url=nxt
        time.sleep(.15)
    return rows

def download(rows):
    manifest=[]; seen_hash={}
    for row in rows:
        for u in row.get("photo_urls",[]):
            try:
                r=get(u)
                ct=r.headers.get("content-type","")
                if r.status_code!=200 or "image" not in ct or len(r.content)<20000:continue
                h=hashlib.sha256(r.content).hexdigest()
                ext=".jpg"
                if "png" in ct:ext=".png"
                elif "webp" in ct:ext=".webp"
                fname=f"{row['channel']}_{row['post'].split('/')[-1]}{ext}"
                if h not in seen_hash:
                    (MEDIA/fname).write_bytes(r.content)
                    seen_hash[h]=fname
                manifest.append({**row,"image_sha256":h,"image_file":seen_hash[h],"bytes":len(r.content),"source_url":u})
                break
            except Exception as e:
                pass
    return manifest

def main():
    allrows=[]; failures=[]
    for ch in CHANNELS:
        for q in QUERIES:
            try:
                rs=crawl(ch,q)
                if rs:
                    print(ch,q,len(rs),flush=True)
                    allrows.extend(rs)
            except Exception as e:
                failures.append({"channel":ch,"query":q,"error":str(e)})
    # dedupe posts
    posts={}
    for r in allrows:
        p=r["post"]
        if p not in posts: posts[p]=r
        else:
            posts[p]["photo_urls"]=list(dict.fromkeys(posts[p].get("photo_urls",[])+r.get("photo_urls",[])))
            old=set(posts[p].get("queries",[])); old.add(r["query"]); posts[p]["queries"]=sorted(old)
    rows=list(posts.values())
    mani=download(rows)
    (OUT/"posts.json").write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"media_manifest.json").write_text(json.dumps(mani,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"failures.json").write_text(json.dumps(failures,ensure_ascii=False,indent=2),encoding="utf-8")
    years={}
    for m in mani:
        years[m.get("year_text","")]=years.get(m.get("year_text",""),0)+1
    unique_images=len(set(m["image_sha256"] for m in mani))
    summary={"unique_posts":len(rows),"posts_with_images":len(mani),"unique_images":unique_images,
             "year_mentions":years,"channels":sorted(set(r["channel"] for r in rows)),"failures":len(failures)}
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":
    main()
