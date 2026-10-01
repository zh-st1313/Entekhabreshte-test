#!/usr/bin/env python3
import hashlib, html, json, re, time
from pathlib import Path
from urllib.parse import quote, urljoin
import requests
from bs4 import BeautifulSoup

OUT=Path("artifacts/gozine2-mirrors")
MEDIA=OUT/"media"
OUT.mkdir(parents=True,exist_ok=True); MEDIA.mkdir(parents=True,exist_ok=True)
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 Gozine2PublicMirrorRecovery/1.0"})

CHANNELS=[
 "karname_konkur","kousarhighschool","gozined","gozine2kangavar",
 "gozine2_roshtkhar","gozine2tabas","gozine2ahwaz","gozine2neka"
]
GROUPS=["تجربی","ریاضی","انسانی"]
YEAR_FORMS={
 "1397":["97","۹۷"],"1398":["98","۹۸"],"1399":["99","۹۹"],
 "1400":["1400","۱۴۰۰"],"1401":["1401","۱۴۰۱"],"1402":["1402","۱۴۰۲"],"1403":["1403","۱۴۰۳"]
}
QUERIES=[]
for y,forms in YEAR_FORMS.items():
    for f in forms:
        for g in GROUPS:
            QUERIES.append((y,g,f"#کارنامه_کنکور{f}_{g}"))
for y in ["1401","1402","1403"]:
    fy={"1401":"۱۴۰۱","1402":"۱۴۰۲","1403":"۱۴۰۳"}[y]
    QUERIES.append((y,"",f"#کارنامه_پذیرفته_شدگان_کنکور {fy}"))

def get(url,timeout=12):
    for i in range(2):
        try:return S.get(url,timeout=timeout)
        except Exception:
            if i: raise
            time.sleep(1)

def parse(wrap,ch,q,y,g):
    msg=wrap.select_one(".tgme_widget_message")
    if not msg:return None
    post=msg.get("data-post","")
    if not post:return None
    te=wrap.select_one(".tgme_widget_message_text")
    text=te.get_text("\n",strip=True) if te else ""
    tm=wrap.select_one(".tgme_widget_message_date time")
    date=tm.get("datetime","") if tm else ""
    photos=[]
    for el in wrap.select('[style*="background-image"]'):
        m=re.search(r'background-image\s*:\s*url\([\'"]?(.*?)[\'"]?\)',el.get("style",""))
        if m:
            u=html.unescape(m.group(1))
            if u.startswith("//"):u="https:"+u
            photos.append(u)
    return {"post":post,"channel":ch,"query":q,"year_hint":y,"group_hint":g,"date":date,
            "text":text,"permalink":"https://t.me/"+post,"photo_urls":list(dict.fromkeys(photos))}

def crawl(ch,y,g,q,max_pages=30):
    url=f"https://t.me/s/{ch}?q={quote(q)}"; seen=set(); posts=set(); out=[]
    for _ in range(max_pages):
        if url in seen:break
        seen.add(url)
        r=get(url)
        if r.status_code!=200:break
        soup=BeautifulSoup(r.text,"lxml")
        for w in soup.select(".tgme_widget_message_wrap"):
            x=parse(w,ch,q,y,g)
            if x and x["post"] not in posts:posts.add(x["post"]); out.append(x)
        more=soup.select_one("a.tme_messages_more")
        if not more or not more.get("href"):break
        nxt=urljoin("https://t.me",more["href"])
        if "q=" not in nxt:nxt+=("&" if "?" in nxt else "?")+"q="+quote(q)
        url=nxt; time.sleep(.08)
    return out

def download(rows):
    mani=[]; stored={}
    for x in rows:
        for u in x["photo_urls"]:
            try:
                r=get(u); ct=r.headers.get("content-type","")
                if r.status_code!=200 or "image" not in ct or len(r.content)<20000:continue
                h=hashlib.sha256(r.content).hexdigest()
                if h not in stored:
                    ext=".png" if "png" in ct else ".webp" if "webp" in ct else ".jpg"
                    fn=f"{x['year_hint']}_{x['group_hint'] or 'all'}_{x['channel']}_{x['post'].split('/')[-1]}{ext}"
                    (MEDIA/fn).write_bytes(r.content); stored[h]=fn
                mani.append({**x,"image_sha256":h,"image_file":stored[h],"bytes":len(r.content),"source_url":u})
                break
            except Exception:pass
    return mani

def main():
    rows=[]; failures=[]
    for ch in CHANNELS:
        for y,g,q in QUERIES:
            try:
                rs=crawl(ch,y,g,q)
                if rs: print(ch,y,g,q,len(rs),flush=True); rows+=rs
            except Exception as e:failures.append({"channel":ch,"query":q,"error":str(e)})
    ded={}
    for x in rows:
        ded.setdefault(x["post"],x)
    rows=list(ded.values()); mani=download(rows)
    summary={"unique_posts":len(rows),"posts_with_images":len(mani),
             "unique_images":len(set(x["image_sha256"] for x in mani)),
             "by_channel":{},"by_year":{},"failures":len(failures)}
    for x in mani:
        summary["by_channel"][x["channel"]]=summary["by_channel"].get(x["channel"],0)+1
        summary["by_year"][x["year_hint"]]=summary["by_year"].get(x["year_hint"],0)+1
    for name,obj in [("posts.json",rows),("media_manifest.json",mani),("failures.json",failures),("summary.json",summary)]:
        (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
