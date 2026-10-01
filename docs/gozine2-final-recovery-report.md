# Gozine2 recovery final QA status

Public historical recovery only. No Norato login automation or query-limit bypassing was used.

## Final cleaned dataset

- Final unique records: **642**
- Previous structured records: **245**
- New real report-card images with rank extracted before semantic dedupe: **401**
- Promotional images excluded: **2**
- Semantic duplicate records merged: **4**
- Net new unique records added: **397**
- Rank-in-quota present: **642 / 642**
- Country rank present where the historical card exposes it: **169 / 642**
- QA invariant country-rank < quota-rank violations: **0**

## Final coverage

- 1397: **165**
- 1398: **306**
- 1399: **91**
- 1400: **52**
- 1402: **28**

By group:
- Experimental: **221**
- Humanities: **210**
- Mathematics: **211**

## Wave-2 rank extraction QA

Of the 397 newly-added unique records:
- **208** rank readings were visually checked directly from the recovered report-card image.
- **189** came from the fixed 800x600 historical card layout digit extractor.
- That fixed-layout extractor achieved **100% full-rank sequence accuracy** in grouped cross-validation against the previously verified historical cards.
- Low-confidence fixed-layout samples were additionally spot-checked after correcting character segmentation.

Two square images were confirmed to be promotional graphics rather than student report cards and were excluded:
- `gozine_dorost/3666`
- `karname_konkur/5408`

Four repost/content duplicate pairs were merged after rank extraction.

## Important

This research branch should remain unmerged until the cleaned dataset is intentionally imported into the production Entekhab-Reshte data structure.
