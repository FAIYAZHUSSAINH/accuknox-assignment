# Q1 — API Data Retrieval and Storage

> You are tasked with fetching data from an external REST API, storing it in a local
> SQLite database, and displaying the retrieved data. The API provides a list of books
> in JSON format with attributes like title, author, and publication year.

## What I built

A pipeline of two scripts:

| File | Purpose |
|---|---|
| [`explore_data.py`](explore_data.py) | Exploration script, run **before** writing any storage code, to answer: which fields can actually be missing, how often, and is title alone safe as a unique key? Not part of the pipeline — this is the evidence behind the schema decisions below. |
| [`books_api.py`](books_api.py) | The actual pipeline: fetches book records from the Open Library search API, stores them in a local SQLite database, and prints them back out. |

`books_api.py` is split into five functions — `fetch_books`, `parse_books`, `init_db`,
`save_books`, `display_books` — tied together in `main()`, so each stage can fail and be
handled on its own terms rather than everything sitting in one block.

## API choice

Open Library's `search.json` endpoint. It needs no API key or authentication, returns
plain JSON, and supports a `fields=` parameter so I could request only `title`,
`author_name`, and `first_publish_year` instead of pulling the full record for every book.

## What I measured, before designing the schema

Before writing the storage code I checked how reliable those three fields actually are,
across five different queries (`explore_data.py`):

| query | total | missing author | missing year | duplicate titles |
|---|---|---|---|---|
| python | 100 | 1 | 2 | 13/100 |
| tamil literature | 100 | 6 | 1 | 9/100 |
| embedded systems design | 100 | 7 | 3 | 28/100 |
| victorian botany | 30 | 1 | 0 | 4/30 |
| obscure regional poetry | 0 | — | — | — |

**Title was never missing in any sample**, which is why the schema has
`title TEXT NOT NULL` while `author` and `first_publish_year` stay nullable. If I had
only tested `python`, the missing-author rate would have looked like 1%; on a less
popular query it was seven times that. The duplicate-title counts (up to 28%) are what
stopped me using `UNIQUE(title)` on its own — two different books with the same title
is common, not an edge case.

The zero-result query mattered too. Open Library returns HTTP 200 with an empty `docs`
array, so "no matches" is a *successful response containing nothing*. The code treats
that as a clean exit with a "no books found" message, kept separate from
`requests.RequestException`, which means the network or server actually failed.

`author_name` comes back as a list, since books can have several authors — one had 9.
I join them into one comma-separated string. That's enough for storing and displaying,
but it means you can't query for a single author without a `LIKE` scan. A proper fix
would be a separate `authors` table with a junction table, which felt out of proportion
for this task.

## The duplicate problem

My first schema used a plain `UNIQUE(title, author, first_publish_year)` constraint.
The first run against a fresh database parsed 100 rows and stored 99 — which looked
correct, the API had returned the same book twice in one page and the constraint caught it.

The second run is where it broke: the row count went from 99 to 102 instead of staying
at 99.

Two things were happening. Part of the growth was real — Open Library doesn't return an
identical result set between calls, so some records were genuinely new. But querying the
database directly showed the actual bug:

```sql
SELECT * FROM books WHERE title = 'Think Like a Programmer, Python Edition'
```

returned **two rows**, ids 94 and 194, with the same title, the same author, and
`first_publish_year` NULL in both.

The reason: in SQL, `NULL` is never equal to another `NULL`, including for uniqueness
checks. So any book missing its year or author could be inserted an unlimited number of
times without ever tripping the constraint — the constraint silently stopped
constraining on exactly the rows I'd measured as most likely to have gaps.

### The fix

Replaced the column-level `UNIQUE` with a separate index:

```sql
CREATE UNIQUE INDEX idx_books_dedup
ON books (title COLLATE NOCASE, COALESCE(author, ''), COALESCE(first_publish_year, -1))
```

`COALESCE(x, sentinel)` makes two `NULL`s compare as equal for the index, without the
sentinel ever being written into the stored row — the table still holds `NULL`.
`COLLATE NOCASE` was added on the title at the same time, because the live data had the
same book under different capitalization ("Core Python Programming" vs "Core Python
programming", "Starting Out with Python" vs "Starting out with Python").

Verified both parts:
- Wiping the database and running twice gave 99 rows both times, and grouping on the
  same `COALESCE` expression with `HAVING COUNT(*) > 1` returned nothing.
- For case-insensitivity: manually inserted `LEARNING PYTHON` against the existing
  `Learning Python` (same author, same year) — rejected, `rowcount = 0`.

One thing that caught me out: `CREATE INDEX IF NOT EXISTS` matches on the index **name**,
not its definition. A database created before the `COLLATE NOCASE` change keeps the old
index indefinitely — I had to delete `books.db` before the fix did anything visible.

## Other design decisions

- **Parameterized `?` placeholders**, never f-strings, in every insert. Titles and
  author names are untrusted external text and can contain quotes.
- **`save_books` wraps `executemany` in `with conn:`**, so the batch either commits
  fully or rolls back — no half-written table if something fails partway.
- **`fetch_books` sets `timeout=10` and calls `raise_for_status()`.** Without a timeout
  a stalled server hangs the process indefinitely; without the status check, a 404/500
  body would be parsed as if it were book data.
- **`try/finally` around the connection**, not `with sqlite3.connect(...)` — that
  context manager commits the transaction but does **not** close the connection.
- **`INSERT OR IGNORE`** makes reruns safe, and `main()` now prints the split explicitly:

  ```
  99 inserted, 1 skipped as duplicates      # first run, fresh db
  0 inserted, 100 skipped as duplicates     # second run, same db — proof it's idempotent
  ```

## Known limitations

- `COLLATE NOCASE` in SQLite only folds ASCII A–Z. The result set includes titles in
  Italian and Indonesian, so accented characters won't case-fold and those duplicates
  would still get through.
- Author names aren't normalized at all — `"J.K. Rowling"` and `"J. K. Rowling"` are
  stored as different authors.
- The `COALESCE` workaround is SQLite-specific. SQL Server treats NULLs as equal in a
  unique constraint by default, and PostgreSQL 15 added `UNIQUE NULLS NOT DISTINCT` to
  opt into that behavior — this would be written differently on another engine.
- The query is hardcoded to `"python"` rather than taking a CLI argument.
- `DB_PATH` is relative to the working directory, so running the script from a
  different folder silently creates a different database.
- Everything above was verified by hand against the live API — there's no automated
  test suite that would catch a regression.

## How to run

```bash
python -m venv venv
venv\Scripts\activate      # Windows
pip install -r requirements.txt

python explore_data.py     # optional: reproduces the missing-field measurements above
python books_api.py        # fetches, stores in books.db, prints the 20 most recent rows
```

## Sample output

```
Fetched 100 docs, parsed 100 rows
99 inserted, 1 skipped as duplicates
99 total rows now in books.db

The Practice of Computing Using Python - William F. Punch, Richard Enbody (2012)
Game Development Using Python - James R. Parker (2018)
Murach's Python for Data Analysis - Scott McCoy (2021)
Elements of programming interviews in Python - Adnan Aziz (2017)
Python Programming - Vijaya Kumara Sarma, Vimal Kumar, Swati Sharma, Shashwat Pathak (2021)
...
```

The full written submission (with screenshots of the API response, the exploration
script output, and the SQLite table view) is on Google Drive:
https://drive.google.com/drive/folders/1iuHjBjBw6iG-b9pHds8GTxgC9Pi-18Ct?usp=sharing
