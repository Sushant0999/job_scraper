"""
sources.py — Pulls job listings from public, login-free, ToS-compliant APIs.

Deliberately excludes LinkedIn, Naukri, and Indeed: none of them offer a
public application API, and scraping/automating their "Apply" flow violates
their terms of service and risks your account. Everything here is either an
official public API (Adzuna) or an open job-board API meant for this exact
use case (Arbeitnow, RemoteOK, Greenhouse, Lever).
"""
import os
import re
import time
import requests

USER_AGENT = "job-search-agent/1.0 (personal use; respectful rate-limited client)"
TIMEOUT = 15


def _get(url, params=None, headers=None):
    h = {"User-Agent": USER_AGENT}
    if headers:
        h.update(headers)
    try:
        r = requests.get(url, params=params, headers=h, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        print(f"  [warn] request failed for {url}: {e}")
        return None


def fetch_adzuna(title, location, max_results, app_id, app_key):
    """Official Adzuna API. Free tier, needs a free app_id/app_key.
    Docs: https://developer.adzuna.com/docs/search"""
    if not app_id or not app_key:
        return []
    country = "in"  # India index; Adzuna also supports "gb", "us", etc.
    url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "what": title,
        "where": "" if location.lower() == "remote" else location,
        "results_per_page": max_results,
        "content-type": "application/json",
    }
    data = _get(url, params=params)
    if not data:
        return []
    jobs = []
    for item in data.get("results", []):
        jobs.append({
            "source": "Adzuna",
            "company": (item.get("company") or {}).get("display_name", "Unknown"),
            "title": item.get("title", "").strip(),
            "location": (item.get("location") or {}).get("display_name", location),
            "description": item.get("description", ""),
            "url": item.get("redirect_url", ""),
            "salary_min": item.get("salary_min"),
            "salary_max": item.get("salary_max"),
            "posted": item.get("created", ""),
        })
    return jobs


_STOPWORDS = {"developer", "engineer", "software", "java", "se", "sr", "jr",
              "senior", "junior", "lead"}


def _significant_terms(title):
    """Pulls the meaningful words out of a search title for lenient matching.
    e.g. 'Java Backend Developer' -> ['backend'] (java is always implied separately)."""
    words = re.sub(r"[^a-z0-9 ]", " ", title.lower()).split()
    return [w for w in words if w not in _STOPWORDS and len(w) > 2]


def _is_relevant(title, blob, search_title):
    """True if this listing is plausibly a Java backend role matching the search.
    Always requires 'java' OR 'spring' somewhere (title/tags/description) — that's
    the non-negotiable core signal — then optionally checks for other significant
    words from the search title as a soft bonus (not required)."""
    text = (title + " " + blob).lower()
    if "java" not in text and "spring" not in text:
        return False
    return True


def fetch_arbeitnow(title, max_results):
    """Arbeitnow public job board API — free, no key required.
    Docs: https://www.arbeitnow.com/api/job-board-api"""
    data = _get("https://www.arbeitnow.com/api/job-board-api")
    if not data:
        return []
    jobs = []
    for item in data.get("data", []):
        job_title = item.get("title", "")
        tags = " ".join(item.get("tags", []))
        description = item.get("description", "") or ""
        blob = tags + " " + description
        if not _is_relevant(job_title, blob, title):
            continue
        jobs.append({
            "source": "Arbeitnow",
            "company": item.get("company_name", "Unknown"),
            "title": job_title,
            "location": item.get("location", "Remote") or "Remote",
            "description": description,
            "url": item.get("url", ""),
            "salary_min": None,
            "salary_max": None,
            "posted": item.get("created_at", ""),
        })
        if len(jobs) >= max_results:
            break
    return jobs


def fetch_remoteok(title, max_results):
    """RemoteOK public API — free, no key required.
    Docs: https://remoteok.com/api"""
    data = _get("https://remoteok.com/api")
    if not data:
        return []
    jobs = []
    for item in data:
        if not isinstance(item, dict) or "position" not in item:
            continue
        position = item.get("position", "")
        tags = " ".join(item.get("tags", []))
        description = item.get("description", "") or ""
        blob = tags + " " + description
        if not _is_relevant(position, blob, title):
            continue
        jobs.append({
            "source": "RemoteOK",
            "company": item.get("company", "Unknown"),
            "title": position,
            "location": "Remote",
            "description": description,
            "url": item.get("url", "") or f"https://remoteok.com/remote-jobs/{item.get('id','')}",
            "salary_min": item.get("salary_min"),
            "salary_max": item.get("salary_max"),
            "posted": item.get("date", ""),
        })
        if len(jobs) >= max_results:
            break
    return jobs


def fetch_greenhouse(board_token, max_results):
    """Public Greenhouse job board API for a specific company.
    Docs: https://developers.greenhouse.io/job-board.html"""
    url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"
    data = _get(url, params={"content": "true"})
    if not data:
        return []
    jobs = []
    for item in data.get("jobs", [])[:max_results]:
        jobs.append({
            "source": f"Greenhouse:{board_token}",
            "company": board_token,
            "title": item.get("title", ""),
            "location": (item.get("location") or {}).get("name", ""),
            "description": item.get("content", "") or "",
            "url": item.get("absolute_url", ""),
            "salary_min": None,
            "salary_max": None,
            "posted": item.get("updated_at", ""),
        })
    return jobs


def fetch_lever(board_token, max_results):
    """Public Lever job board API for a specific company.
    Docs: https://github.com/lever/postings-api"""
    url = f"https://api.lever.co/v0/postings/{board_token}"
    data = _get(url, params={"mode": "json"})
    if not data:
        return []
    jobs = []
    for item in data[:max_results]:
        jobs.append({
            "source": f"Lever:{board_token}",
            "company": board_token,
            "title": item.get("text", ""),
            "location": (item.get("categories") or {}).get("location", ""),
            "description": item.get("descriptionPlain", "") or "",
            "url": item.get("hostedUrl", ""),
            "salary_min": None,
            "salary_max": None,
            "posted": "",
        })
    return jobs


def fetch_all(config):
    """Run every configured source across every title/location combo."""
    app_id = os.getenv("ADZUNA_APP_ID")
    app_key = os.getenv("ADZUNA_APP_KEY")
    max_r = config["search"]["max_results_per_query"]
    titles = config["search"]["titles"]
    locations = config["search"]["locations"]

    if not app_id or not app_key:
        print("  [info] ADZUNA_APP_ID/ADZUNA_APP_KEY not set — Adzuna will return 0 "
              "results. This is your main India-specific source; see README to add a free key.")

    all_jobs = []
    counts = {}

    for title in titles:
        for loc in locations:
            found = fetch_adzuna(title, loc, max_r, app_id, app_key)
            counts["Adzuna"] = counts.get("Adzuna", 0) + len(found)
            all_jobs.extend(found)
            time.sleep(0.5)  # be polite to the API

    for title in titles:
        found_a = fetch_arbeitnow(title, max_r)
        counts["Arbeitnow"] = counts.get("Arbeitnow", 0) + len(found_a)
        all_jobs.extend(found_a)

        found_r = fetch_remoteok(title, max_r)
        counts["RemoteOK"] = counts.get("RemoteOK", 0) + len(found_r)
        all_jobs.extend(found_r)
        time.sleep(0.5)

    for token in config.get("company_boards", {}).get("greenhouse", []):
        found = fetch_greenhouse(token, max_r)
        counts["Greenhouse"] = counts.get("Greenhouse", 0) + len(found)
        all_jobs.extend(found)
        time.sleep(0.3)

    for token in config.get("company_boards", {}).get("lever", []):
        found = fetch_lever(token, max_r)
        counts["Lever"] = counts.get("Lever", 0) + len(found)
        all_jobs.extend(found)
        time.sleep(0.3)

    print(f"  Raw results before dedup: {dict(counts)}")

    # Dedupe by (company, title, url)
    seen = set()
    deduped = []
    for j in all_jobs:
        key = (j["company"].lower(), j["title"].lower(), j["url"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(j)

    return deduped
