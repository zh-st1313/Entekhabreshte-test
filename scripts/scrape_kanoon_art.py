#!/usr/bin/env python3
import argparse, json, sys, re
from pathlib import Path
import requests
from bs4 import BeautifulSoup

PAGE = "https://www.kanoon.ir/Public/SuperiorsRankBased?type=3"
ENDPOINT = "https://www.kanoon.ir/Public/SuperiorsRankBasedShowSuperiors"

def session():
    s=requests.Session()
    s.headers.update({
        "User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/129 Safari/537.36",
        "Accept-Language":"fa-IR,fa;q=0.9,en;q=0.7",
    })
    r=s.get(PAGE,timeout=30)
    print("GET",r.status_code,len(r.text))
    r.raise_for_status()
    return s

def fetch(s, year_code, region, rank):
    payload={
        "dept":"4",
        "sahmieh":str(region),
        "rank":str(rank),
        "reshte":None,
        "year":str(year_code),
        "univercity":None,
        "type":"3",
    }
    h={
        "Referer":PAGE,
        "Origin":"https://www.kanoon.ir",
        "X-Requested-With":"XMLHttpRequest",
        "Content-Type":"application/json; charset=UTF-8",
        "Accept":"*/*",
    }
    r=s.post(ENDPOINT,headers=h,data=json.dumps(payload,ensure_ascii=False).encode("utf-8"),timeout=30)
    print("POST",payload,"=>",r.status_code,len(r.text),r.headers.get("content-type"))
    r.raise_for_status()
    return r.text

def inspect_html(html):
    soup=BeautifulSoup(html,"html.parser")
    print("TITLE", soup.title.get_text(" ",strip=True) if soup.title else None)
    trs=soup.find_all("tr")
    print("TR_COUNT",len(trs))
    for i,tr in enumerate(trs[:20]):
        cells=[x.get_text(" ",strip=True) for x in tr.find_all(["th","td"])]
        print("ROW",i,repr(cells))
    print("TEXT",repr(soup.get_text(" ",strip=True)[:3000]))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--probe",action="store_true")
    args=ap.parse_args()
    s=session()
    if args.probe:
        for y in [101,102,103,104]:
            html=fetch(s,y,1,100)
            print("\n=== YEAR",y,"===")
            print(html[:8000])
            inspect_html(html)
        return
    raise SystemExit("Use --probe for this bootstrap version.")

if __name__=="__main__":
    main()
