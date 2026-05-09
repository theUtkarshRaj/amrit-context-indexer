"""
search.py — CLI for querying the AMRIT context index.

Supports full-text search against the FTS5 SQLite index (search mode),
grouped repo browsing (list mode), and corpus statistics (stats mode).
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime

DB_PATH = os.path.join("data", "index.db")
REPOS_PATH = os.path.join("data", "repos.json")


def load_repos() -> list[dict]:
    with open(REPOS_PATH, encoding="utf-8") as f:
        return json.load(f)


def snippet(text: str, max_len: int = 200) -> str:
    """Return a truncated preview of README text."""
    if not text:
        return "(no README)"
    text = text.strip().replace("\n", " ")
    return text[:max_len] + "..." if len(text) > max_len else text


# --- Search mode ---

def cmd_search(query: str) -> None:
    """Run a BM25-ranked FTS5 query and print the top 5 results."""
    if not os.path.exists(DB_PATH):
        sys.exit(f"Index not found at {DB_PATH}. Run indexer.py first.")

    with sqlite3.connect(DB_PATH) as conn:
        # bm25() returns negative scores; ORDER BY ASC puts best match first
        rows = conn.execute(
            """
            SELECT name, language, html_url, description, readme
            FROM repos_fts
            WHERE repos_fts MATCH ?
            ORDER BY bm25(repos_fts)
            LIMIT 5
            """,
            (query,),
        ).fetchall()

    if not rows:
        print(f'No results for "{query}".')
        return

    for name, language, url, description, readme in rows:
        lang_str = language or "unknown"
        desc_str = description or "No description"
        print(f"  > {name}")
        print(f"    [{lang_str}]  {url}")
        print(f"    {desc_str}")
        print(f"    {snippet(readme)}")
        print()


# --- List mode ---

def cmd_list() -> None:
    """Group repos by language and print them as a categorised list."""
    repos = load_repos()

    groups: dict[str, list[str]] = {}
    for repo in repos:
        lang = repo.get("language") or "Other"
        groups.setdefault(lang, []).append(repo["name"])

    # Most-populated languages first; "Other" always last
    sorted_langs = sorted(
        groups, key=lambda l: (-len(groups[l]), l == "Other", l)
    )

    for lang in sorted_langs:
        names = groups[lang]
        print(f"\n  {lang} ({len(names)})")
        for name in sorted(names):
            print(f"    - {name}")


# --- Stats mode ---

def cmd_stats() -> None:
    """Print corpus statistics: totals, language breakdown, recent updates."""
    repos = load_repos()
    total = len(repos)

    lang_counts: dict[str, int] = {}
    for repo in repos:
        lang = repo.get("language") or "Other"
        lang_counts[lang] = lang_counts.get(lang, 0) + 1

    print(f"\n  Total repos: {total}")
    print("\n  By language:")
    for lang, count in sorted(lang_counts.items(), key=lambda x: -x[1]):
        pct = count / total * 100
        print(f"    {lang:<20} {count:>3}  ({pct:.1f}%)")

    # Top 5 most recently updated
    dated = [r for r in repos if r.get("updated_at")]
    dated.sort(key=lambda r: r["updated_at"], reverse=True)
    print("\n  Most recently updated:")
    for repo in dated[:5]:
        # updated_at is ISO 8601; strip time component for readability
        date = repo["updated_at"][:10]
        print(f"    {date}  {repo['name']}")
    print()


# --- Entry point ---

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search and browse the AMRIT context index.",
        epilog="Examples:\n"
               "  python search.py \"beneficiary registration\"\n"
               "  python search.py --list\n"
               "  python search.py --stats",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("query", nargs="?", help="Full-text search query")
    parser.add_argument("--list", action="store_true", help="List repos grouped by language")
    parser.add_argument("--stats", action="store_true", help="Show corpus statistics")

    args = parser.parse_args()

    if args.list:
        cmd_list()
    elif args.stats:
        cmd_stats()
    elif args.query:
        cmd_search(args.query)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
