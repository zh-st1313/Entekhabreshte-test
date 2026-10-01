# Gozine2 recovered admissions dataset status

Public historical recovery only. No Norato login automation or query-limit bypassing was used.

## Current cleaned dataset

- Unique accepted-student report cards: **245**
- 1397: 31
- 1398: 86
- 1399: 48
- 1400: 52
- 1402: 28
- Experimental: 84
- Humanities: 81
- Mathematics: 80
- Rank-in-quota available: 245 / 245
- Country rank available: 126 / 245
- Admission type available from caption: 218 / 245
- Admission type not shown: 27 / 245 (mainly 1402)

All rank fields were manually visually transcribed from the recovered public report-card images and are marked `manual_visual_single_pass` pending a second QA pass.

## Recovery notes

A broad public Telegram recovery found 254 byte-unique images across historical Gozine2 channels. Promotional graphics and byte duplicates were excluded. Content-level deduplication used year, group, quota region, rank-in-quota, major and university. The current cleaned table contains 245 distinct report-card records.

The recovery tooling remains isolated on this research branch. Do not merge the tooling into the production dataset branch until QA is complete.
