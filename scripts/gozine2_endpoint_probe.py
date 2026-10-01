#!/usr/bin/env python3
import json, re, time
from pathlib import Path
from urllib.parse import urlparse
import requests

OUT=Path("artifacts/gozine2-endpoints")
RAW=OUT/"raw"
OUT.mkdir(parents=True,exist_ok=True)
RAW.mkdir(parents=True,exist_ok=True)

S=requests.Session()
S.headers.update({"User-Agent":"Mozilla/5.0 Gozine2HistoricalPublicArchiveResearch/1.0"})

PATTERNS=[
 "student.gozine2.ir/KonkurResult/GetReshtehData*",
 "student.gozine2.ir/KonkurResult/GetPercentData*",
 "student.gozine2.ir/KonkurResult/GetSubGroupDataByFieldID*",
 "student.gozine2.ir/KonkurResultDetails*",
 "student.gozine2.ir/bundles/indexkonkurresultjs*",
]

def cdx(pattern):
    url="https://web.archive.org/cdx/search/cdx"
    params={
      "url":pattern,"output":"json",
      "fl":"timestamp,original,statuscode,mimetype,digest",
      "filter":"statuscode:200","collapse":"digest",
      "limit":"5000",
    }
    last=None
    for i in range(2):
        try:
            r=S.get(url,params=params,timeout=18)
            r.raise_for_status()
            d=r.json()
            if not d: return []
            head=d[0]
            return [dict(zip(head,x)) for x in d[1:]]
        except Exception as e:
            last=str(e); time.sleep(1*(i+1))
    return [{"pattern":pattern,"error":last}]

def fetch_capture(c):
    ts,orig=c.get("timestamp"),c.get("original")
    if not ts or not orig: return None
    replay=f"https://web.archive.org/web/{ts}id_/{orig}"
    try:
        r=S.get(replay,timeout=15)
        item={**c,"replay_url":replay,"fetch_status":r.status_code,
              "content_type":r.headers.get("content-type",""),"bytes":len(r.content)}
        if r.status_code==200:
            body=r.text
            name=re.sub(r"[^A-Za-z0-9._-]+","_",f"{ts}_{urlparse(orig).path.strip('/') or 'root'}")[:190]+".txt"
            (RAW/name).write_text(body,encoding="utf-8",errors="ignore")
            item["saved"]=str(RAW/name)
            item["preview"]=body[:1000]
            try:
                obj=r.json()
                item["is_json"]=True
                item["json_type"]=type(obj).__name__
                if isinstance(obj,dict):
                    item["json_keys"]=list(obj)[:40]
                    # Small structural summary only; full response is in raw/.
                    data=obj.get("data")
                    if isinstance(data,dict):
                        item["data_keys"]=list(data)[:40]
                        if isinstance(data.get("data"),list):
                            item["row_count"]=len(data["data"])
            except Exception:
                item["is_json"]=False
            # Discover endpoint/action strings from archived JS/HTML.
            strings=sorted(set(re.findall(r'["\\\']([^"\\\']*(?:KonkurResult|GetReshtehData|GetPercentData|GetSubGroupData)[^"\\\']*)["\\\']',body,re.I)))
            item["interesting_strings"]=strings[:100]
        return item
    except Exception as e:
        return {**c,"replay_url":replay,"error":str(e)}

def live_public_probe():
    url="https://student.gozine2.ir/KonkurResult/GetReshtehData"
    params={"rotbe":"1000","studentFieldID":"2","studentCategoryID":"1","captchaInputText":""}
    try:
        r=S.get(url,params=params,timeout=20,allow_redirects=False)
        out={"url":r.url,"status":r.status_code,"location":r.headers.get("location",""),
             "content_type":r.headers.get("content-type",""),"bytes":len(r.content)}
        body=r.text[:2000]
        try:
            obj=r.json()
            out["json"]=True
            out["top_keys"]=list(obj)[:20] if isinstance(obj,dict) else []
            if isinstance(obj,dict):
                out["success"]=obj.get("success")
                data=obj.get("data")
                if isinstance(data,dict):
                    out["data_keys"]=list(data)[:30]
                    dd=data.get("data")
                    if isinstance(dd,list):
                        out["row_count"]=len(dd)
                        out["sample_keys"]=list(dd[0])[:30] if dd and isinstance(dd[0],dict) else []
        except Exception:
            out["json"]=False
            out["body_preview"]=body.replace("\n"," ")[:500]
        return out
    except Exception as e:
        return {"error":str(e)}

def main():
    allcaps=[]
    by={}
    for p in PATTERNS:
        caps=cdx(p)
        by[p]=caps
        for c in caps:
            if c.get("timestamp") and c.get("original"):
                c["pattern"]=p
                allcaps.append(c)
        print(p,len([x for x in caps if x.get("timestamp")]))

    (OUT/"cdx_by_pattern.json").write_text(json.dumps(by,ensure_ascii=False,indent=2),encoding="utf-8")

    # Fetch every unique API capture when reasonably small; cap each pattern.
    fetched=[]
    per_pattern={}
    for p in PATTERNS:
        caps=[x for x in by[p] if x.get("timestamp") and x.get("original")]
        # Endpoint JSON captures are likely sparse; keep up to 120 each.
        selected=caps[:12]
        per_pattern[p]=len(selected)
        for c in selected:
            x=fetch_capture({**c,"pattern":p})
            if x: fetched.append(x)
            time.sleep(.05)

    (OUT/"fetched.json").write_text(json.dumps(fetched,ensure_ascii=False,indent=2),encoding="utf-8")
    json_caps=[x for x in fetched if x.get("is_json")]
    rows=sum(int(x.get("row_count") or 0) for x in json_caps)
    endpoints=sorted(set(x.get("original","") for x in fetched if "Get" in x.get("original","")))
    live=live_public_probe()
    summary={
      "cdx_capture_count":sum(len([x for x in v if x.get("timestamp")]) for v in by.values()),
      "fetched_count":len(fetched),
      "json_capture_count":len(json_caps),
      "rows_visible_in_archived_json":rows,
      "patterns_selected":per_pattern,
      "endpoint_originals_sample":endpoints[:100],
      "successful_files":len(list(RAW.glob("*"))),\n      "live_public_probe":live,
    }
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
