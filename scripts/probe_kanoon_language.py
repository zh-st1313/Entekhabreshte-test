#!/usr/bin/env python3
import json, re, requests
from bs4 import BeautifulSoup

PAGE="https://www.kanoon.ir/Public/SuperiorsRankBased?type=3"
ENDPOINT="https://www.kanoon.ir/Public/SuperiorsRankBasedShowSuperiors"
DEPT=5

s=requests.Session()
s.headers.update({"User-Agent":"Mozilla/5.0","Accept-Language":"fa-IR,fa;q=0.9"})
r=s.get(PAGE,timeout=30); print("GET",r.status_code,len(r.text)); r.raise_for_status()

for year in (101,102,103,104):
  payload={"dept":str(DEPT),"sahmieh":"1","rank":"100","reshte":None,"year":str(year),"univercity":None,"type":"3"}
  h={"Referer":PAGE,"Origin":"https://www.kanoon.ir","X-Requested-With":"XMLHttpRequest","Content-Type":"application/json; charset=UTF-8"}
  rr=s.post(ENDPOINT,headers=h,data=json.dumps(payload).encode(),timeout=30)
  print("YEAR",year,"STATUS",rr.status_code,"BYTES",len(rr.text))
  soup=BeautifulSoup(rr.text,"html.parser")
  rows=[]
  for tr in soup.select("table.Superior tr"):
    cells=[re.sub(r"\s+"," ",x.get_text(" ",strip=True)).strip() for x in tr.find_all("td")]
    if cells: rows.append(cells)
  print("ROWS",rows[:10])
