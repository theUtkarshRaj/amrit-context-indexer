"""
indexer.py — Builds a SQLite FTS5 full-text search index from data/repos.json.

FTS5 is chosen over embeddings because it ships with Python's sqlite3 stdlib,
requires no GPU or external model, and keyword search is sufficient for matching
developer queries against repo names, descriptions, and README text.
"""

import json
import os
import sqlite3

INPUT_PATH = os.path.join("data", "repos.json")
OUTPUT_PATH = os.path.join("data", "index.db")


def load_repos(path: str) -> list[dict]:
    """Load the repo list from a JSON file produced by fetch_repos.py."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def create_fts_table(conn: sqlite3.Connection) -> None:
    """Create the FTS5 virtual table, dropping any prior version first."""
    conn.execute("DROP TABLE IF EXISTS repos_fts")
    conn.execute("""
        CREATE VIRTUAL TABLE repos_fts USING fts5(
            name,
            full_name,
            description,
            language,
            html_url,
            readme
        )
    """)


def index_repos(conn: sqlite3.Connection, repos: list[dict]) -> None:
    """Insert every repo into the FTS5 table, printing progress as it goes."""
    total = len(repos)
    for i, repo in enumerate(repos, start=1):
        print(f"Indexing {i} of {total}: {repo['name']}")
        conn.execute(
            "INSERT INTO repos_fts VALUES (?, ?, ?, ?, ?, ?)",
            (
                repo.get("name") or "",
                repo.get("full_name") or "",
                repo.get("description") or "",
                repo.get("language") or "",
                repo.get("html_url") or "",
                repo.get("readme") or "",   # null readme → empty string
            ),
        )


def main():
    """Load repos.json, build the FTS5 index, and write data/index.db."""
    repos = load_repos(INPUT_PATH)

    # Always start fresh so repeated runs don't accumulate stale rows
    if os.path.exists(OUTPUT_PATH):
        os.remove(OUTPUT_PATH)

    with sqlite3.connect(OUTPUT_PATH) as conn:
        create_fts_table(conn)
        index_repos(conn, repos)
        conn.commit()

    print(f"\nIndexed {len(repos)} repos to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
