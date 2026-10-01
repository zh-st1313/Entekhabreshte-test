#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

PAGE = "https://www.kanoon.ir/Public/SuperiorsRankBased?type=3"
ENDPOINT = "https://www.kanoon.ir/Public/SuperiorsRankBasedShowSuperiors"

DEPT = 5  # زبان
GROUP = "زبان"
YEARS = {1401: 101, 1402: 102, 1403: 103, 1404: 104}
REGIONS = (1, 2, 3)
MAX_TARGET = 500_000

ROOT = Path(__file__).resolve().parents[1]
RAW_BASE = ROOT / "data" / "raw" / "kanoon" / "language"
RANK_BASE = ROOT / "data" / "rank_admissions"

DIGIT_TRANS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)

CSV_FIELDS = [
    "سال",
    "گروه آزمایشی",
    "رتبه کشوری",
    "رتبه در سهمیه",
    "سهمیه",
    "رشته قبولی",
    "دانشگاه قبولی",
]

RAW_FIELDS = (
    "kanoon_score",
    "national_rank",
    "quota_rank",
    "quota_region",
    "gender",
    "city",
    "accepted_raw",
)


def clean_text(value: str) -> str:
    value = (value or "").replace("\u200c", " ")
    return re.sub(r"\s+", " ", value).strip()


def parse_int(value: str) -> int | None:
    value = clean_text(value).translate(DIGIT_TRANS)
    value = value.replace(",", "").replace("٬", "")
    m = re.search(r"-?\d+", value)
    return int(m.group()) if m else None


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "Chrome/129 Safari/537.36"
        ),
        "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.7",
    })
    r = s.get(PAGE, timeout=30)
    print(f"bootstrap GET {r.status_code} bytes={len(r.content)}", flush=True)
    r.raise_for_status()
    return s


def fetch_html(
    s: requests.Session,
    *,
    year_code: int,
    region: int,
    target_rank: int,
    attempts: int = 4,
) -> str:
    payload = {
        "dept": str(DEPT),
        "sahmieh": str(region),
        "rank": str(target_rank),
        "reshte": None,
        "year": str(year_code),
        "univercity": None,
        "type": "3",
    }
    headers = {
        "Referer": PAGE,
        "Origin": "https://www.kanoon.ir",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/json; charset=UTF-8",
        "Accept": "*/*",
    }

    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            r = s.post(
                ENDPOINT,
                headers=headers,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                timeout=40,
            )
            if r.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"retryable HTTP {r.status_code}", response=r)
            r.raise_for_status()
            return r.text
        except requests.RequestException as exc:
            last_error = exc
            if attempt == attempts:
                break
            delay = min(8.0, 0.8 * (2 ** (attempt - 1)))
            print(
                f"retry year={year_code} region={region} rank={target_rank} "
                f"attempt={attempt} error={exc}; sleep={delay}s",
                flush=True,
            )
            time.sleep(delay)
            try:
                s.get(PAGE, timeout=30)
            except requests.RequestException:
                pass

    raise RuntimeError(
        f"request failed year={year_code} region={region} rank={target_rank}: {last_error}"
    )


def parse_rows(html: str, expected_region: int) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out = []

    for tr in soup.select("table.Superior tr"):
        cells = [clean_text(td.get_text(" ", strip=True)) for td in tr.find_all("td")]
        if len(cells) < 7:
            continue

        score = parse_int(cells[0])
        national = parse_int(cells[1])
        quota = parse_int(cells[2])
        region = parse_int(cells[3])

        if None in (score, national, quota, region):
            continue
        if region not in REGIONS or region != expected_region:
            continue

        out.append({
            "kanoon_score": score,
            "national_rank": national,
            "quota_rank": quota,
            "quota_region": region,
            "gender": cells[4],
            "city": cells[5],
            "accepted_raw": cells[6],
        })

    return out


def row_key(row: dict) -> tuple:
    return tuple(row.get(k) for k in RAW_FIELDS)


def target_sequence(max_target: int = MAX_TARGET):
    target = 1
    while target <= max_target:
        yield target
        half_window = max(100, int(math.floor(target * 0.10)))
        target += half_window


def split_admission(raw: str) -> tuple[str, str]:
    raw = clean_text(raw)

    # Kanoon 1401 format: major | institution | course/type
    if "|" in raw:
        parts = [clean_text(p) for p in raw.split("|")]
        parts = [p for p in parts if p]
        if len(parts) >= 2:
            major = parts[0]
            university = parts[1]
            if len(parts) >= 3:
                major = f"{major} - {' - '.join(parts[2:])}"
            return major, university

    markers = [
        "دانشگاه",
        "دانشکده",
        "مؤسسه",
        "موسسه",
        "آموزشکده",
        "اموزشکده",
        "مرکز آموزش عالی",
    ]
    hits = [(raw.find(marker), marker) for marker in markers if raw.find(marker) > 0]
    if not hits:
        return raw, ""

    idx, _ = min(hits, key=lambda x: x[0])
    return clean_text(raw[:idx]), clean_text(raw[idx:])


def extract_region(
    s: requests.Session,
    *,
    year: int,
    year_code: int,
    region: int,
) -> tuple[list[dict], dict]:
    unique = {}
    nonzero_queries = 0
    zero_queries = 0
    query_count = 0
    last_nonzero_target = None
    last_targets = []

    for target in target_sequence():
        query_count += 1
        html = fetch_html(
            s,
            year_code=year_code,
            region=region,
            target_rank=target,
        )
        rows = parse_rows(html, region)

        if rows:
            nonzero_queries += 1
            last_nonzero_target = target
        else:
            zero_queries += 1

        for row in rows:
            unique[row_key(row)] = row

        last_targets.append({"target": target, "rows": len(rows)})
        last_targets = last_targets[-8:]

        if query_count % 25 == 0:
            print(
                f"progress year={year} region={region} target={target} "
                f"queries={query_count} unique={len(unique)} rows_now={len(rows)}",
                flush=True,
            )
        time.sleep(0.06)

    far_probes = (600_000, 750_000, 1_000_000)
    far_results = []
    for target in far_probes:
        html = fetch_html(
            s,
            year_code=year_code,
            region=region,
            target_rank=target,
        )
        rows = parse_rows(html, region)
        far_results.append({"target": target, "rows": len(rows)})
        for row in rows:
            unique[row_key(row)] = row
        time.sleep(0.06)

    rows = sorted(
        unique.values(),
        key=lambda r: (
            r["quota_rank"],
            r["national_rank"],
            r["accepted_raw"],
            r["city"],
            r["gender"],
            r["kanoon_score"],
        ),
    )

    meta = {
        "year": year,
        "year_code": year_code,
        "dept": DEPT,
        "group": GROUP,
        "region": region,
        "query_count": query_count + len(far_probes),
        "nonzero_queries": nonzero_queries,
        "zero_queries": zero_queries,
        "unique_rows": len(rows),
        "quota_rank_min": min((r["quota_rank"] for r in rows), default=None),
        "quota_rank_max": max((r["quota_rank"] for r in rows), default=None),
        "national_rank_min": min((r["national_rank"] for r in rows), default=None),
        "national_rank_max": max((r["national_rank"] for r in rows), default=None),
        "last_nonzero_target": last_nonzero_target,
        "last_sweep_targets": last_targets,
        "far_tail_probes": far_results,
    }
    return rows, meta


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def normalize_language_rows(year: int, rows: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for row in rows:
        major, university = split_admission(row["accepted_raw"])
        record = {
            "سال": str(year),
            "گروه آزمایشی": GROUP,
            "رتبه کشوری": str(row["national_rank"]),
            "رتبه در سهمیه": str(row["quota_rank"]),
            "سهمیه": f"منطقه {row['quota_region']}",
            "رشته قبولی": major,
            "دانشگاه قبولی": university,
        }
        key = tuple(record[k] for k in CSV_FIELDS)
        if key not in seen:
            seen.add(key)
            out.append(record)
    return out


def merged_csv_write(path: Path, year: int, language_rows: list[dict]) -> tuple[int, int]:
    existing = []
    if path.exists():
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            existing = list(csv.DictReader(f))

    # Idempotent: preserve every existing group except language, then rebuild language.
    preserved = [r for r in existing if clean_text(r.get("گروه آزمایشی", "")) != GROUP]
    normalized = normalize_language_rows(year, language_rows)

    merged = preserved + normalized
    seen = set()
    deduped = []
    for r in merged:
        rr = {k: clean_text(str(r.get(k, ""))) for k in CSV_FIELDS}
        key = tuple(rr[k] for k in CSV_FIELDS)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(rr)

    group_order = {"تجربی": 1, "ریاضی": 2, "انسانی": 3, "هنر": 4, "زبان": 5}
    def to_int(v):
        try:
            return int(str(v).replace(",", "").replace("٬", ""))
        except Exception:
            return 10**12

    deduped.sort(key=lambda r: (
        group_order.get(r["گروه آزمایشی"], 99),
        to_int(r["رتبه در سهمیه"]),
        to_int(r["رتبه کشوری"]),
        r["سهمیه"],
        r["رشته قبولی"],
        r["دانشگاه قبولی"],
    ))

    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(deduped)

    return len(normalized), len(deduped)


def full_extract() -> None:
    RAW_BASE.mkdir(parents=True, exist_ok=True)
    RANK_BASE.mkdir(parents=True, exist_ok=True)

    session = make_session()
    all_summary = {
        "source_page": PAGE,
        "post_endpoint": ENDPOINT,
        "dept": DEPT,
        "group": GROUP,
        "coverage_method": (
            "Overlapping adaptive quota-rank sweep from 1 through 500000; "
            "step=max(100,floor(10% of target)); plus far-tail probes."
        ),
        "years": {},
    }

    grand_language_total = 0

    for year, year_code in YEARS.items():
        print(f"\n===== LANGUAGE {year} (source year={year_code}) =====", flush=True)
        year_rows = {}
        region_meta = {}

        for region in REGIONS:
            try:
                session.get(PAGE, timeout=30)
            except requests.RequestException:
                session = make_session()

            rows, meta = extract_region(
                session,
                year=year,
                year_code=year_code,
                region=region,
            )
            region_meta[str(region)] = meta
            write_jsonl(RAW_BASE / str(year) / f"region-{region}.jsonl", rows)

            for row in rows:
                year_rows[row_key(row)] = row

            print(
                f"DONE year={year} region={region} unique_rows={len(rows)} "
                f"quota_range={meta['quota_rank_min']}..{meta['quota_rank_max']}",
                flush=True,
            )

        combined = sorted(
            year_rows.values(),
            key=lambda r: (
                r["quota_region"],
                r["quota_rank"],
                r["national_rank"],
                r["accepted_raw"],
            ),
        )

        language_count, merged_count = merged_csv_write(
            RANK_BASE / f"rank_to_admission_{year}.csv",
            year,
            combined,
        )

        if language_count == 0:
            raise RuntimeError(
                f"No language records extracted for {year}; refusing to publish empty output"
            )

        summary = {
            "dataset": f"kanoon_language_{year}",
            "source_page": PAGE,
            "post_endpoint": ENDPOINT,
            "dept": DEPT,
            "year": year,
            "year_code": year_code,
            "type": 3,
            "regions": region_meta,
            "combined_unique_rows": len(combined),
            "normalized_language_rows": language_count,
            "merged_year_csv_rows": merged_count,
        }
        (RAW_BASE / str(year) / "stage-summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        all_summary["years"][str(year)] = {
            "raw_unique_rows": len(combined),
            "normalized_language_rows": language_count,
            "merged_year_csv_rows": merged_count,
            "regions": {
                str(r): region_meta[str(r)]["unique_rows"] for r in REGIONS
            },
        }
        grand_language_total += language_count

    all_summary["total_normalized_language_rows"] = grand_language_total
    (RANK_BASE / "LANGUAGE_1401_1404_SUMMARY.json").write_text(
        json.dumps(all_summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("\nFINAL LANGUAGE SUMMARY", flush=True)
    print(json.dumps(all_summary, ensure_ascii=False, indent=2), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()
    if args.full:
        full_extract()
        return
    parser.error("use --full")


if __name__ == "__main__":
    main()
