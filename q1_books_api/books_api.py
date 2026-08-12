"""
Q1 — Fetch books from the Open Library API, store them in SQLite, and display them.
"""

import sqlite3
import requests

API_URL = "https://openlibrary.org/search.json"
DB_PATH = "books.db"


def fetch_books(query, limit=100):
    """
    Fetch book records from the Open Library search API.
    Returns a list of raw dicts, or raises requests.RequestException on failure.
    """
    params = {
        "q": query,
        "fields": "title,author_name,first_publish_year",  # ask only for what we store
        "limit": limit,
    }
    # timeout is not optional: without it a stalled server hangs this process forever.
    response = requests.get(API_URL, params=params, timeout=10)
    response.raise_for_status()  # turns a 404/500 body into an exception instead of fake data
    return response.json().get("docs", [])


def parse_books(docs):
    """
    Convert raw API dicts into clean (title, author, year) tuples ready for insertion.
    Drops records without a title; author/year are stored as NULL when absent
    (NULL means "unknown", which is different from 0 or an empty string).
    """
    rows = []
    skipped = 0

    for doc in docs:
        title = doc.get("title")
        if not title:
            skipped += 1
            continue

        # author_name is a list (co-authored books can have several); flatten to one string.
        authors = doc.get("author_name")
        author = ", ".join(authors) if authors else None

        year = doc.get("first_publish_year")  # already an int in the JSON when present

        rows.append((title, author, year))

    if skipped:
        print(f"Skipped {skipped} record(s) with no title.")

    return rows


def init_db(conn):
    """
    Create the books table and its dedup index if they don't already exist.
    Safe to call every run.

    Plain `UNIQUE(title, author, first_publish_year)` was tried first and
    failed in practice: SQL treats NULL as never equal to another NULL, so
    two rows with the same title/author and both missing a year are NOT
    considered duplicates by a UNIQUE constraint - they both get inserted.
    Confirmed this by re-running against a live query: a book with a NULL
    year landed twice under different ids. COALESCE(..., <sentinel>) forces
    NULLs to compare equal to each other for dedup purposes only - the
    stored value in the table stays NULL, only the index sees the sentinel.

    title COLLATE NOCASE: live data has the same book listed with different
    capitalization ("Core Python Programming" vs "Core Python programming"),
    which the default BINARY collation treats as distinct. NOCASE folds
    ASCII case for comparison only, so these collide instead of duplicating.

    Note: CREATE INDEX IF NOT EXISTS matches on the index NAME only, not its
    definition - changing this index's columns/collation has no effect on a
    books.db that already has an index called idx_books_dedup on disk. Drop
    the old index (or the db file) after editing this.
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            author TEXT,
            first_publish_year INTEGER
        )
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_books_dedup
        ON books (title COLLATE NOCASE, COALESCE(author, ''), COALESCE(first_publish_year, -1))
        """
    )


def save_books(conn, rows):
    """
    Insert parsed rows into the books table.
    - Parameterized query (?) instead of an f-string: titles/authors come from
      an external API and can contain quotes or other characters that would
      break (or inject into) a hand-built SQL string.
    - INSERT OR IGNORE + the UNIQUE constraint above: re-running the script
      with the same query won't duplicate rows already stored.
    - `with conn:` wraps the executemany in a transaction that commits on
      success and rolls back on any error, so a failure partway through
      never leaves the table half-written.
    """
    with conn:
        cursor = conn.executemany(
            "INSERT OR IGNORE INTO books (title, author, first_publish_year) VALUES (?, ?, ?)",
            rows,
        )
        return cursor.rowcount  # number of rows actually inserted (not ignored)


def display_books(conn, limit=20):
    """Print the most recently stored books."""
    cursor = conn.execute(
        "SELECT title, author, first_publish_year FROM books ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    for title, author, year in cursor.fetchall():
        author_display = author if author else "Unknown author"
        year_display = year if year is not None else "Unknown year"
        print(f"{title} - {author_display} ({year_display})")


def main():
    query = "python"

    try:
        docs = fetch_books(query)
    except requests.RequestException as e:
        # Network failure / bad response: a real error, distinct from "no results".
        print(f"Failed to reach Open Library: {e}")
        return

    if not docs:
        # A successful response with zero matches is not an error.
        print(f"No books found for query {query!r}.")
        return

    rows = parse_books(docs)

    conn = sqlite3.connect(DB_PATH)
    try:
        init_db(conn)
        inserted = save_books(conn, rows)
        total = conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
        print(f"\nFetched {len(docs)} docs, parsed {len(rows)} rows")
        print(f"{inserted} inserted, {len(rows) - inserted} skipped as duplicates")
        print(f"{total} total rows now in {DB_PATH}\n")
        display_books(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
