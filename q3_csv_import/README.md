# Q3 — CSV Data Import to a Database

> Write a Python script that reads data from a CSV file containing user information
> (e.g., name, email) and inserts it into a SQLite database.

**What I built**

`csv_import.py` reads a CSV of user records, validates each row, and inserts the valid
ones into SQLite. Structured as `read_users` → `validate_users` → `init_db` /
`save_users` → `display_users`. `make_fixture.py` generates the test data — a fixture,
not the assessed part.

I generated the fixture deliberately dirty — duplicate rows, case-variant email, padded
whitespace, a non-ASCII name, a malformed email, a missing name, a missing email, a
ragged row, and a UTF-8 BOM — because clean input leaves the error handling untested.

**The BOM**

The file was written the way Excel writes UTF-8 CSVs, with a byte-order mark. Reading it
with `encoding="utf-8"` produced `fieldnames == ['﻿name', 'email']`, so
`row["name"]` raised `KeyError` while a printed header still looked like `name`. I
confirmed the BOM at byte level (`b'\xef\xbb\xbfnam...'`) before changing the parser,
then fixed it with `encoding="utf-8-sig"`, which strips it.

This is worth calling out because the failure is invisible in a text editor and the
error message points at the wrong thing.

**Why the transaction strategy changed from Q1**

In Q1 I wrapped `executemany` in a single all-or-nothing transaction. That was right
there: every row came from one API response, so a partial write would have stored an
incoherent snapshot.

I tested whether the same pattern held here by feeding raw, unvalidated tuples straight
into `executemany` inside one transaction. It raised
`ProgrammingError: Incorrect number of bindings supplied` on the ragged row — and
**zero rows were inserted**, not ten valid ones and one rejection. One malformed line at
the end of a file discards everything before it.

That's the wrong behaviour for a bulk import. A user file is a set of independent
records, not a single atomic snapshot, and a real 10,000-row import shouldn't be
destroyed by one bad line at row 8,000.

So the pipeline validates first and inserts only clean rows. Rejected rows are reported
with their reason and line number rather than dropped silently — if records disappear
between the file and the database, that has to be visible.

The same tool was correct in Q1 and wrong here. What changed is whether the rows are one
unit of meaning or many.

**Results**

First run against an empty database: 11 rows read, 8 valid, 3 rejected (malformed email
with no `@`, missing email, ragged row with three fields against a two-column header),
7 inserted, 1 skipped as an exact duplicate.

The 8 valid rows include Ganesh's — email present, name empty. That's the "missing
email is fatal, missing name isn't" rule below being exercised, not a validator gap: his
row can't be identified by name, but it's still a keyable, storable record by email, so
it's counted in the 8, not the 3 rejections.

Second run, same file, same database: 0 inserted, 8 skipped. Idempotent.

**Validation decisions**

*Email as the key.* Email is the natural identifier, so a row without one is rejected. A
row with an email but no name is kept — the record is still identifiable and a name is a
label rather than a key.

*Whitespace* is stripped from both fields. Padding is a formatting artifact, and
`"  x@y.com  "` and `"x@y.com"` are the same address.

*Email validation* checks for exactly one `@` with content on both sides. Full RFC 5322
compliance is effectively unachievable with a regex, and stricter validation risks
rejecting valid addresses. This catches real typos, which is what it's for.

*Ragged rows* are rejected rather than truncated. `DictReader(restkey="extra")` surfaces
the surplus fields, but an unexpected column count means the row's structure doesn't
match the header, and silently discarding the extra assumes the first two fields are the
right ones.

*Duplicate emails* are handled by a case-insensitive unique constraint, since email
addresses are case-insensitive in practice.

Worth being precise about how I verified that last one: my fixture had an uppercase
email but nothing colliding with it, so the dedup path was never actually exercised by
the test data. Rather than assume it worked, I manually inserted a lowercase variant of
the existing address and confirmed it was rejected with rowcount 0.

**stdlib over pandas**

`pandas.read_csv().to_sql()` does this in two lines. I used `csv` and `sqlite3` because
this task needs per-row rejection with reasons, which means touching each row
individually anyway — and the stdlib streams rather than loading the file into memory,
with no dependency.

I'd flip for a large analytics-shaped CSV, where `chunksize` handles files bigger than
RAM cleanly and dtype inference and vectorised operations earn the dependency. The
deciding factor is whether you need row-level control or column-level throughput.

**Known limitations**

- `COLLATE NOCASE` folds ASCII only. Email addresses are ASCII in practice, so this is
  safe here in a way it wasn't in Q1's book titles.
- Email validation is structural, not deliverable — `a@b` passes.
- Rows with an email but no name are accepted, which is a deliberate choice about what
  identifies a record, not an oversight.
- Rejections are printed rather than written to a rejects file, which is what a real
  import would do so the source data could be corrected and re-run.
- Non-ASCII names displayed as mojibake in my terminal; checking the bytes confirmed
  they were stored correctly as UTF-8 (`b'Jos\xc3\xa9 Fernandes'`). That's a terminal
  encoding default on Windows, not a data problem — but it's the reason to verify at
  byte level rather than trusting the screen.
- No test suite; all verification was manual.

**How to run**

```bash
python make_fixture.py   # writes users.csv
python csv_import.py     # reads it, stores in users.db, prints what's stored
```
