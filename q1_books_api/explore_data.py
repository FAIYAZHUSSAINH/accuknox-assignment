"""
Exploration script, not part of the pipeline.

Run before designing the SQLite schema, to answer: which fields can actually
be missing, how often, and can title alone be a unique key? Results from
this script are what justified:
  - title TEXT NOT NULL (never missing in any sample below)
  - author / first_publish_year nullable (both missing at meaningful rates)
  - a dedup key wider than just title (duplicate titles are common)
"""

import requests

API_URL = "https://openlibrary.org/search.json"

# Deliberately mixes a popular topic with obscure ones. A single popular
# query (e.g. "python") undersells the real missing-field rate - see README
# for the numbers this produced.
QUERIES = [
    "python",
    "tamil literature",
    "embedded systems design",
    "victorian botany",
    "obscure regional poetry",  # kept to demonstrate the zero-results case
]


def probe(query, limit=100):
    response = requests.get(
        API_URL,
        params={"q": query, "fields": "title,author_name,first_publish_year", "limit": limit},
        timeout=10,
    )
    response.raise_for_status()
    docs = response.json().get("docs", [])

    print(f"\nquery: {query!r}")
    print(f"total: {len(docs)}")

    if not docs:
        # A successful response with zero matches - not an error, just empty.
        print("No results.")
        return

    missing_author = sum(1 for d in docs if "author_name" not in d)
    missing_year = sum(1 for d in docs if "first_publish_year" not in d)
    missing_title = sum(1 for d in docs if "title" not in d)
    print(f"missing author_name:        {missing_author}")
    print(f"missing first_publish_year: {missing_year}")
    print(f"missing title:              {missing_title}")

    # author_name is a list - how many co-authors does a book typically have?
    author_counts = [len(d.get("author_name", [])) for d in docs]
    print(f"max authors on one book: {max(author_counts)}")

    # Do titles repeat? Decides whether UNIQUE(title) alone would be safe.
    titles = [d.get("title") for d in docs]
    print(f"duplicate titles: {len(titles) - len(set(titles))} / {len(titles)}")


if __name__ == "__main__":
    for q in QUERIES:
        probe(q)
