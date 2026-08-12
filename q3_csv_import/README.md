# Q3 — CSV Data Import to a Database

> Write a Python script that reads data from a CSV file containing user information
> (e.g., name, email) and inserts it into a SQLite database.

## What I built

| File | Purpose |
|---|---|
| [`make_fixture.py`](make_fixture.py) | Generates `users.csv` — test fixture, not the assessed part. |
| [`csv_import.py`](csv_import.py) | The actual answer: read → validate → store → display. |

No third-party dependencies. `csv` and `sqlite3` are both stdlib, and nothing about a
name/email import needed more than that — see the `pandas` note at the bottom.

## The fixture — generated, not typed

`make_fixture.py` writes 11 data rows, deliberately seeding **nine** problems into an
11-row file — small enough to read in one glance, but built so a naive script fails
loudly instead of quietly getting the wrong answer.

## Problem #1: the BOM (found by trying the wrong thing first)

`make_fixture.py` writes with `encoding="utf-8-sig"`, which is what Excel does when you
"Save As → CSV UTF-8" — it prefixes the file with a byte-order mark. Read that file back
with plain `"utf-8"` and:

```python
>>> reader = csv.DictReader(open("users.csv", encoding="utf-8"))
>>> reader.fieldnames
['﻿name', 'email']
>>> next(reader)["name"]
KeyError: 'name'
```

The header *prints* as `name` — it looks completely normal in a text editor or in
`print(fieldnames)` if you're not looking closely — but the key is actually `'﻿name'`,
so any `row["name"]` lookup raises `KeyError`. Confirmed the raw bytes first
(`b'\xef\xbb\xbfnam...'`) so I knew the BOM was really there before blaming my code.
Fixed with `encoding="utf-8-sig"` in `read_users`, which strips it — verified `fieldnames`
comes back as `['name', 'email']` afterward. Probably the single most common real-world
CSV bug, and it's invisible until you go looking for it.

## The other eight problems

| line | row | issue |
|---|---|---|
| 3 | Bharath Kumar, `BHARATH.KUMAR@EXAMPLE.COM` | uppercase email |
| 4 | Chitra Devi, `"  chitra.devi@example.com  "` | whitespace padding |
| 5 | José Fernandes, jose.fernandes@example.com | non-ASCII name |
| 6 | Elango S, `elango.example.com` | malformed email (no `@`) |
| 7 | Fathima Begum, *(empty)* | missing email |
| 8 | *(empty)*, ganesh.iyer@example.com | missing name |
| 10 | Aarthi Raman, aarthi.raman@example.com | exact duplicate of line 2 |
| 11 | Janani P, janani.p@example.com, `9876543210` | ragged row — 3 fields, header declares 2 |

One thing I checked rather than assumed: the fixture does **not** actually contain a
*matching* case-variant pair. Bharath's row is uppercase, but nothing else in the file
shares his email in a different case — so on its own, this dataset never exercises
whether the dedup logic actually catches a case collision, only that normalization
doesn't crash on an uppercase value. I tested that separately — see below.

## The decision that matters most: transaction strategy is not "same as Q1"

Q1 wrapped `executemany` in `with conn:` for all-or-nothing inserts, and that was right
*there* — every row came from one API response, so a partial write would be an
incoherent snapshot. I tried the same pattern here first, unchanged, to see if it still
held.

**Naive version:** pull `tuple(row.values())` straight off the raw `DictReader` rows and
`executemany` them inside one transaction — no validation first.

```
read 11 raw rows
line 11 has 3 values instead of 2: ('Janani P', 'janani.p@example.com', ['9876543210'])

executemany raised: ProgrammingError: Incorrect number of bindings supplied. The current
statement uses 2, and there are 3 supplied.
rows actually in the table after the failed batch: 0
```

**Zero rows landed** — not just Janani's, all 11, including the 8 that were perfectly
fine. That's the concrete version of "a 10,000-row import with one bad row at line
8,000": one ragged row killed the entire batch.

**Fix:** it's not dropping the transaction, it's not letting a malformed row reach it in
the first place. `validate_users` filters out anything that could break the insert
*before* `save_users` ever sees it, so by the time rows reach `executemany`, "all rows"
and "all good rows" are the same set — `with conn:` is still the right call, just on a
pre-cleaned batch. The one thing validation deliberately doesn't handle is duplicates;
`INSERT OR IGNORE` absorbs those without raising at all, which is a cleaner mechanism
than a validation-time duplicate check would have been.

## Other decisions

- **Email: stored as-given, deduplicated case-insensitively.** `BHARATH.KUMAR@EXAMPLE.COM`
  isn't lowercased on the way in — original casing is kept for display — but uniqueness
  is enforced with `CREATE UNIQUE INDEX ... ON users (email COLLATE NOCASE)`, the exact
  same fix as Q1's title dedup. `NOCASE` only folds ASCII, which was a real limitation
  in Q1 (Italian/Indonesian titles), but isn't one here — email local-parts and domains
  are ASCII by construction, even José's (`jose.fernandes@example.com`).
- **Whitespace: stripped, not preserved.** Unlike Q1's `NULL`, incidental padding around
  an email carries no information — `"  x  "` and `"x"` are the same value, and stripping
  is what lets the later `@`-count check work correctly on Chitra's row at all.
- **Missing email is fatal; missing name is not.** Email is the natural key — a row with
  no email can't be identified or contacted, so it's rejected outright. A name is a
  label, not an identity; Ganesh's row (empty name, valid email) is stored with `NULL`
  name rather than thrown away, since the useful, keyable half of the record is intact.
- **Malformed email: "exactly one `@`, non-empty on both sides."** Not RFC 5322 — that's
  famously near-impossible to get right with a regex — but a rule that catches a real
  typo (`elango.example.com`) without inventing rules the task doesn't ask for (no
  domain/TLD format checking, no length limits).
- **Ragged row: rejected, not silently ignored.** `restkey="extra"` surfaces Janani's
  phone number as `row["extra"] = ['9876543210']` instead of raising. Dropping the extra
  field silently would hide a possible schema mismatch in the source file; rejecting and
  reporting it keeps that visible.

## Results

First run, fresh `users.db`:

```
Read 11 rows, 8 valid, 3 rejected
  line 6: {'name': 'Elango S', 'email': 'elango.example.com'} -> malformed email
  line 7: {'name': 'Fathima Begum', 'email': ''} -> missing email
  line 11: {'name': 'Janani P', 'email': 'janani.p@example.com', 'extra': ['9876543210']} -> unexpected extra field(s): ['9876543210']
1 valid row(s) accepted with no name

7 inserted, 1 skipped as duplicates
7 total rows now in users.db
```

The 1 skipped duplicate is Aarthi's exact repeat (line 10 vs line 2).

Second run, same `users.db`, no changes to the CSV:

```
0 inserted, 8 skipped as duplicates
7 total rows now in users.db
```

Idempotent — confirms the dedup index actually works, not just on the first pass.

Manual test for the case collision the fixture itself doesn't contain: inserted
`bharath.kumar@example.com` (lowercase) against the already-stored
`BHARATH.KUMAR@EXAMPLE.COM`.

```
rows inserted for the lowercase variant (should be 0): 0
all Bharath rows now in the table: [('BHARATH.KUMAR@EXAMPLE.COM',)]
```

Rejected as a duplicate, original casing preserved — the `NOCASE` index catches a case
collision this specific fixture never actually produced on its own.

One more thing worth recording: querying José's stored name back showed `Jos� Fernandes`
in this terminal. Checked the actual bytes rather than trusting the display:
`name.encode('utf-8')` gives `b'Jos\xc3\xa9 Fernandes'` — correct UTF-8 for "José
Fernandes". The mangling is this Windows terminal's rendering, not corrupted data — same
class of issue as the em dash in Q1's output.

## Why stdlib instead of `pandas.read_csv().to_sql()`

That's a real two-line alternative, and worth naming rather than pretending it doesn't
exist. I didn't use it because this task wants **row-level control over rejections** —
`to_sql()` either writes a row or the whole call fails, it doesn't let you say "these 3
rows were rejected, here's why, here's the line number." `csv.DictReader` streams
row-by-row rather than loading the whole file into memory (`read_users` does return a
list up front for simplicity here, so this file doesn't get that benefit in full — it
would for a much larger CSV processed as a generator instead), and it's zero
dependencies for an 11-row name/email import. I'd flip to `pandas` for a large,
analytics-shaped CSV — wide, numeric, meant for aggregation — where `chunksize` and
dtype handling earn the dependency; a validation-heavy, narrow user import is exactly
the case stdlib is proportionate for.

## Known limitations

- `read_users` materializes the whole file into a list before validation runs, so the
  "streaming" argument above only fully holds if it's changed to yield rows lazily —
  fine at 11 rows, not a guarantee at import sizes where memory actually matters.
- Malformed-email checking is intentionally shallow: `a@b` passes even though `b` isn't
  a real domain. That's a deliberate line, not an oversight, but worth stating plainly.
- No normalization beyond stripping whitespace — `José` and a hypothetical accent-stripped
  `Jose` would be stored as different names, same as Q1's author-casing limitation.
- No automated tests; verified by hand against the fixture, same as Q1 and Q2.

## How to run

```bash
python make_fixture.py   # writes users.csv
python csv_import.py     # reads it, stores in users.db, prints what's stored
```
