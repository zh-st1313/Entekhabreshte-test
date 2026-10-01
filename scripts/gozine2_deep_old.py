#!/usr/bin/env python3
import hashlib, html, json, re, time
from pathlib import Path
from urllib.parse import quote, urljoin
import requests
from bs4 import BeautifulSoup

OUT=Path("artifacts/gozine2-deep-old")
MEDIA=OUT/"media"
OUT.mkdir(parents=True,exist_ok=True); MEDIA.mkdir(parents=True,exist_ok=True)

S=requests.Session()
S.headers.update({"User-Agent":"Mozilla/5.0 Gozine2HistoricalArchiveDeepRecovery/1.0"})

CHANNELS=["g2_old","G2_konkur99","G2_konkur406","kousarhighschool","gozined"]
GROUPS=["تجربی","ریاضی","انسانی"]
YEARS=[
 ("1397",["97","۹۷"]),
 ("1398",["98","۹۸"]),
 ("1399",["99","۹۹"]),
 ("1400",["1400","۱۴۰۰"]),
]
QUERIES=[]
for year,forms in YEARS:
    for f in forms:
        for g in GROUPS:
            QUERIES.append((year,g,f"#کارنامه_کنکور{f}_{g}"))

def get(url,timeout=15):
    last=None
    for i in range(3):
        try:return S.get(url,timeout=timeout)
        except Exception as e:last=e; time.sleep(1+i)
    raise last

def parse(wrap,ch,q,year_hint,group_hint):
    msg=wrap.select_one(".tgme_widget_message")
    if not msg:return None
    post=msg.get("data-post","")
    if not post:return None
    t=wrap.select_one(".tgme_widget_message_text")
    text=t.get_text("\n",strip=True) if t else ""
    tm=wrap.select_one(".tgme_widget_message_date time")
    date=tm.get("datetime","") if tm else ""
    photos=[]
    for el in wrap.select('[style*="background-image"]'):
        st=el.get("style","")
        m=re.search(r'background-image\s*:\s*url\([\'"]?(.*?)[\'"]?\)',st)
        if m:
            u=html.unescape(m.group(1))
            if u.startswith("//"):u="https:"+u
            photos.append(u)
    photos=list(dict.fromkeys(photos))
    return {"post":post,"channel":ch,"query":q,"year_hint":year_hint,"group_hint":group_hint,
            "date":date,"text":text,"permalink":"https://t.me/"+post,"photo_urls":photos}

def crawl(ch,year_hint,group_hint,q,max_pages=80):
    url=f"https://t.me/s/{ch}?q={quote(q)}"
    seen_urls=set(); seen_posts=set(); rows=[]
    for page in range(max_pages):
        if url in seen_urls:break
        seen_urls.add(url)
        r=get(url)
        if r.status_code!=200:break
        soup=BeautifulSoup(r.text,"lxml")
        added=0
        for wrap in soup.select(".tgme_widget_message_wrap"):
            row=parse(wrap,ch,q,year_hint,group_hint)
            if row and q in row.get("text","") and row["post"] not in seen_posts:
                seen_posts.add(row["post"]); rows.append(row); added+=1
        more=soup.select_one("a.tme_messages_more")
        if not more or not more.get("href"):break
        nxt=urljoin("https://t.me",more["href"])
        if "q=" not in nxt:
            nxt += ("&" if "?" in nxt else "?")+"q="+quote(q)
        url=nxt
        time.sleep(.10)
    return rows

def download(rows):
    manifest=[]; stored={}
    for idx,row in enumerate(rows):
        for u in row.get("photo_urls",[]):
            try:
                r=get(u)
                ct=r.headers.get("content-type","")
                if r.status_code!=200 or "image" not in ct or len(r.content)<20000:continue
                h=hashlib.sha256(r.content).hexdigest()
                ext=".jpg"
                if "png" in ct:ext=".png"
                elif "webp" in ct:ext=".webp"
                if h not in stored:
                    fn=f"{row['year_hint']}_{row['group_hint']}_{row['channel']}_{row['post'].split('/')[-1]}{ext}"
                    (MEDIA/fn).write_bytes(r.content); stored[h]=fn
                manifest.append({**row,"image_sha256":h,"image_file":stored[h],"bytes":len(r.content),"source_url":u})
                break
            except Exception:
                pass
    return manifest

def main():
    rows=[]; failures=[]
    for ch in CHANNELS:
        for year,g,q in QUERIES:
            try:
                rs=crawl(ch,year,g,q)
                if rs:
                    print(ch,year,g,q,len(rs),flush=True)
                    rows.extend(rs)
            except Exception as e:
                failures.append({"channel":ch,"year":year,"group":g,"query":q,"error":str(e)})
    bypost={}
    for r in rows:
        if r["post"] not in bypost:bypost[r["post"]]=r
        else:
            old=set(bypost[r["post"]].get("queries",[])); old.add(r["query"]); bypost[r["post"]]["queries"]=sorted(old)
            bypost[r["post"]]["photo_urls"]=list(dict.fromkeys(bypost[r["post"]]["photo_urls"]+r["photo_urls"]))
    rows=list(bypost.values())
    mani=download(rows)
    unique=set(m["image_sha256"] for m in mani)
    counts={}
    for m in mani:
        k=f"{m['year_hint']}-{m['group_hint']}"
        counts[k]=counts.get(k,0)+1
    summary={"unique_posts":len(rows),"posts_with_images":len(mani),"unique_images":len(unique),"counts":counts,"failures":len(failures)}
    (OUT/"posts.json").write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"media_manifest.json").write_text(json.dumps(mani,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"failures.json").write_text(json.dumps(failures,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":
    main()
