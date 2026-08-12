# AccuKnox Assignment — Faiyaz Hussain H

## Questions

| # | Task | Solution |
|---|---|---|
| 1 | Fetch books from a REST API, store them in SQLite, display them back | [`q1_books_api/`](q1_books_api/) — see its [README](q1_books_api/README.md) for the full write-up: API choice, what was measured about missing/duplicate fields, a real duplicate-row bug caused by SQL's `NULL != NULL` semantics and how it was fixed and verified, and known limitations. |
| 2 | Fetch student test scores from an API, calculate the average, chart it | [`q2_scores_api/`](q2_scores_api/) — see its [README](q2_scores_api/README.md) for the full write-up: a deliberately messy mock fixture (missing score, string score, out-of-range score, outlier), how each was handled with the measured effect on the average, and mean-vs-median. |
| 3 | Import a CSV of user info into SQLite | [`q3_csv_import/`](q3_csv_import/) — see its [README](q3_csv_import/README.md) for the full write-up: a BOM bug reproduced and fixed, a naive all-or-nothing insert that dropped an entire good batch because of one bad row and the validate-first fix, and case-insensitive email dedup carried over from Q1. |

The original written submission (PDF, with screenshots) is on Google Drive: https://drive.google.com/drive/folders/1iuHjBjBw6iG-b9pHds8GTxgC9Pi-18Ct?usp=sharing
