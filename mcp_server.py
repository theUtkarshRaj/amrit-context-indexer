"""
mcp_server.py — FastMCP stdio server wrapping the AMRIT FTS5 index.

Exposes four tools and one resource family to MCP clients (Claude Desktop,
Claude Code, etc.). All logging goes to stderr; stdout is reserved for the
MCP protocol wire format.
"""

import json
import os
import sqlite3
import sys

from mcp.server.fastmcp import FastMCP

_HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_HERE, "data", "index.db")
REPOS_PATH = os.path.join(_HERE, "data", "repos.json")

mcp = FastMCP("amrit-context-indexer")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _db() -> sqlite3.Connection:
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Index not found at {DB_PATH}. Run indexer.py first.")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _repos() -> list[dict]:
    with open(REPOS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _snippet(text: str, max_len: int = 300) -> str:
    if not text:
        return ""
    text = text.strip().replace("\n", " ")
    return text[:max_len] + "..." if len(text) > max_len else text


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def search_repos(query: str, top_k: int = 5, include_archived: bool = False) -> list[dict]:
    """BM25-ranked FTS5 search over repo names, descriptions, and READMEs."""
    archive_filter = "" if include_archived else "AND archived = 0"
    with _db() as conn:
        rows = conn.execute(
            f"""
            SELECT name, language, html_url, description, readme, archived
            FROM repos_fts
            WHERE repos_fts MATCH ?
            {archive_filter}
            ORDER BY bm25(repos_fts)
            LIMIT ?
            """,
            (query, top_k),
        ).fetchall()

    results = []
    for row in rows:
        results.append({
            "name": row["name"],
            "language": row["language"] or "unknown",
            "html_url": row["html_url"],
            "description": row["description"] or "",
            "readme_snippet": _snippet(row["readme"]),
            "archived": bool(row["archived"]),
        })

    return results


@mcp.tool()
def list_repos(language: str | None = None) -> list[dict]:
    """List all repos, optionally filtered by language, with archived flag."""
    repos = _repos()
    result = []
    for repo in repos:
        lang = repo.get("language") or "Other"
        if language and lang.lower() != language.lower():
            continue
        result.append({
            "name": repo["name"],
            "language": lang,
            "html_url": repo["html_url"],
            "description": repo.get("description") or "",
            "archived": repo.get("archived", False),
            "updated_at": repo.get("updated_at") or "",
        })
    result.sort(key=lambda r: r["name"])
    return result


@mcp.tool()
def repo_details(name: str) -> dict:
    """Return full metadata for a single repo by exact name."""
    repos = _repos()
    for repo in repos:
        if repo["name"].lower() == name.lower():
            return {
                "name": repo["name"],
                "full_name": repo.get("full_name") or "",
                "description": repo.get("description") or "",
                "language": repo.get("language") or "unknown",
                "html_url": repo["html_url"],
                "default_branch": repo.get("default_branch") or "",
                "updated_at": repo.get("updated_at") or "",
                "archived": repo.get("archived", False),
            }
    return {"error": f"Repo '{name}' not found."}


@mcp.tool()
def get_readme(name: str) -> str:
    """Return the full README text for a repo by exact name."""
    with _db() as conn:
        row = conn.execute(
            "SELECT readme FROM repos_fts WHERE name = ?", (name,)
        ).fetchone()
    if row is None:
        return f"Repo '{name}' not found in index."
    return row["readme"] or "(no README)"


# ---------------------------------------------------------------------------
# Resources  —  amrit://repo/{name}/readme
# ---------------------------------------------------------------------------

@mcp.resource("amrit://repo/{name}/readme")
def readme_resource(name: str) -> str:
    """Expose each repo's README as an MCP resource URI."""
    return get_readme(name)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("amrit-context-indexer MCP server starting", file=sys.stderr)
    mcp.run()  # defaults to stdio transport
