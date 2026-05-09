"""
fetch_repos.py — Data ingestion script for the AMRIT (PSMRI) context indexer.

Fetches all public repositories from the PSMRI GitHub organization, along with
their README content, and writes the result to data/repos.json.
"""

import base64
import json
import os
import time

import requests
from dotenv import load_dotenv

ORG = "PSMRI"
BASE_URL = "https://api.github.com"
OUTPUT_PATH = os.path.join("data", "repos.json")


def build_headers(token: str) -> dict:
    """Return the HTTP headers required for all GitHub API requests."""
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }


def fetch_all_repos(headers: dict) -> list[dict]:
    """
    Fetch every public repository in the PSMRI org, handling pagination.

    Returns a list of raw repo objects from the GitHub API.
    """
    repos = []
    page = 1

    while True:
        print(f"Fetching repos page {page}...")
        response = requests.get(
            f"{BASE_URL}/orgs/{ORG}/repos",
            headers=headers,
            params={"per_page": 100, "page": page, "type": "public"},
        )
        response.raise_for_status()

        batch = response.json()
        if not batch:
            break

        repos.extend(batch)
        page += 1

    return repos


def fetch_readme(repo_name: str, headers: dict) -> str | None:
    """
    Fetch and decode the README for a given repo.

    Returns the decoded UTF-8 text, or None if the repo has no README.
    """
    response = requests.get(
        f"{BASE_URL}/repos/{ORG}/{repo_name}/readme",
        headers=headers,
    )

    if response.status_code == 404:
        return None

    response.raise_for_status()

    # GitHub returns README content as base64-encoded bytes
    encoded = response.json().get("content", "")
    return base64.b64decode(encoded).decode("utf-8")


def extract_repo_fields(repo: dict, readme: str | None) -> dict:
    """Pick the relevant fields from a raw GitHub repo object."""
    return {
        "name": repo["name"],
        "full_name": repo["full_name"],
        "description": repo.get("description"),
        "language": repo.get("language"),
        "html_url": repo["html_url"],
        "default_branch": repo.get("default_branch"),
        "updated_at": repo.get("updated_at"),
        "readme": readme,
    }


def main():
    """Orchestrate repo fetching and write results to data/repos.json."""
    load_dotenv()

    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise EnvironmentError("GITHUB_TOKEN not found in environment or .env file")

    headers = build_headers(token)
    raw_repos = fetch_all_repos(headers)
    print(f"Found {len(raw_repos)} repos. Fetching READMEs...\n")

    results = []
    for repo in raw_repos:
        name = repo["name"]
        readme = fetch_readme(name, headers)

        if readme is not None:
            print(f"  Got README for {name}")
        else:
            print(f"  Skipped README for {name} (not found)")

        results.append(extract_repo_fields(repo, readme))

        # Be polite to avoid GitHub's secondary rate limits
        time.sleep(0.1)

    os.makedirs("data", exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nDone. Saved {len(results)} repos to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
