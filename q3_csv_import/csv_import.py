import csv
import sqlite3

CSV_PATH = "users.csv"
DB_PATH = "users.db"


def read_users(path):
    """
    Read the CSV with DictReader. Returns raw dicts, unvalidated.

    encoding="utf-8-sig" matters: Excel's "CSV UTF-8" export writes a byte-order
    mark before the header. Read with plain "utf-8" and that BOM glues itself
    onto the first field name, so fieldnames becomes ['﻿name', 'email']
    and row["name"] raises KeyError - while printing the header still looks
    like plain "name". utf-8-sig strips it.

    restkey="extra": if a row has more fields than the header declares,
    DictReader stuffs the leftovers into a list under this key instead of
    raising. Ragged rows get handled explicitly in validate_users - not
    silently dropped, not silently ignored.
    """
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, restkey="extra")
        return list(reader)


def validate_users(raw):
    """
    Return (clean, rejected). clean holds (name, email) tuples ready for
    insertion; rejected holds (line_number, row, reason) so every dropped
    row is accountable, not just silently gone.

    Deliberately asymmetric: a missing email is fatal (it's the natural key -
    there's no way to identify or contact this "user" at all), a missing name
    is not (it's a label, not an identity - a name-less row can still be
    stored and fixed later). Whitespace is stripped since it's incidental,
    not meaningful data (unlike Q1's NULL, which meant something).
    """
    clean = []
    rejected = []

    for line_num, row in enumerate(raw, start=2):  # line 1 is the header
        if row.get("extra"):
            rejected.append((line_num, row, f"unexpected extra field(s): {row['extra']}"))
            continue

        name = (row.get("name") or "").strip() or None
        email = (row.get("email") or "").strip()

        if not email:
            rejected.append((line_num, row, "missing email"))
            continue

        # "Exactly one @ with something on each side" - not RFC 5322, which is
        # famously near-impossible to validate with a regex, but it catches
        # real typos (no @, or an empty local-part/domain) without
        # over-engineering a rule this task doesn't need.
        local, _, domain = email.partition("@")
        if email.count("@") != 1 or not local or not domain:
            rejected.append((line_num, row, "malformed email"))
            continue

        clean.append((name, email))

    return clean, rejected


def init_db(conn):
    """
    Create the users table and a case-insensitive uniqueness index on email.

    Email is the natural key, but "BHARATH.KUMAR@EXAMPLE.COM" and
    "bharath.kumar@example.com" are the same mailbox. Stored as-given (not
    lowercased) so the original casing is preserved for display, with
    uniqueness enforced via COLLATE NOCASE - the same fix as Q1's title dedup.
    NOCASE only folds ASCII, which was a real limitation for Q1's
    non-English book titles; it isn't one here, since email local-parts and
    domains are ASCII by construction.
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT,
            email TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users (email COLLATE NOCASE)"
    )


def save_users(conn, rows):
    """
    Insert already-validated rows inside one transaction.

    This looks like Q1's save_books, but the reasoning is different, not
    copied. In Q1, all-or-nothing was correct because every row came from one
    API response - a partial write would be an incoherent snapshot. Here, a
    naive version of this same line (raw CSV rows straight into executemany)
    was tried first and it rolled back the entire batch to 0 rows because of
    one ragged row - see README. The fix isn't dropping the transaction, it's
    that validate_users() already rejected anything that could break the
    insert, so by the time rows gets here, "all rows" and "all good rows"
    are the same set. INSERT OR IGNORE handles the one remaining case
    (duplicate email) without raising at all.
    """
    with conn:
        cursor = conn.executemany(
            "INSERT OR IGNORE INTO users (name, email) VALUES (?, ?)",
            rows,
        )
        return cursor.rowcount


def display_users(conn):
    """Print stored users."""
    cursor = conn.execute("SELECT name, email FROM users ORDER BY id")
    for name, email in cursor.fetchall():
        print(f"{name or 'Unknown name'} <{email}>")


def main():
    raw = read_users(CSV_PATH)
    clean, rejected = validate_users(raw)

    print(f"Read {len(raw)} rows, {len(clean)} valid, {len(rejected)} rejected")
    for line_num, row, reason in rejected:
        print(f"  line {line_num}: {row} -> {reason}")

    missing_name = sum(1 for name, _ in clean if name is None)
    if missing_name:
        print(f"{missing_name} valid row(s) accepted with no name")

    conn = sqlite3.connect(DB_PATH)
    try:
        init_db(conn)
        inserted = save_users(conn, clean)
        total = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        print(f"\n{inserted} inserted, {len(clean) - inserted} skipped as duplicates")
        print(f"{total} total rows now in {DB_PATH}\n")
        display_users(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
