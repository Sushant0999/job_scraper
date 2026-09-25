#!/usr/bin/env python3
"""
main.py — Job Search Agent entrypoint.

Usage:
    python main.py

What it does:
    1. Loads your profile + search settings from config.yaml
    2. Pulls live job listings from public APIs (Adzuna, Arbeitnow, RemoteOK,
       and any Greenhouse/Lever boards you've added)
    3. Scores each job against your skills
    4. Drafts a tailored cover letter for your best matches using a LOCAL
       LLM via Ollama — no API key, nothing leaves your machine (skipped if
       Ollama isn't running or the model isn't pulled)
    5. Writes everything to an Excel file for you to review

What it deliberately does NOT do:
    - Auto-submit applications anywhere
    - Touch LinkedIn, Naukri, or Indeed (no public application API; automating
      them risks violating their terms of service and getting your account flagged)
    - Call any cloud AI API — cover letter drafting runs 100% locally via Ollama

You stay in control of every "Apply" click.
"""
import os
import sys
import yaml
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from sources import fetch_all          # noqa: E402
from scorer import score_all           # noqa: E402
from excel_writer import write_results  # noqa: E402
import local_llm as llm                # noqa: E402


def main():
    load_dotenv()

    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "config.yaml")) as f:
        config = yaml.safe_load(f)

    profile = config["profile"]
    search_cfg = config["search"]
    out_cfg = config["output"]

    if not os.getenv("ADZUNA_APP_ID"):
        print("Note: ADZUNA_APP_ID/ADZUNA_APP_KEY not set in .env — Adzuna search will be")
        print("skipped, and you'll only get Arbeitnow + RemoteOK (remote-only) results.")
    print("Fetching jobs from all sources...")
    jobs = fetch_all(config)
    print(f"Found {len(jobs)} unique job postings.\n")

    print("Scoring jobs against your profile...")
    scored = score_all(jobs, profile, search_cfg["min_match_score"])
    print(f"{len(scored)} jobs passed the minimum match score "
          f"({search_cfg['min_match_score']}%).\n")

    drafts_dir = os.path.join(here, out_cfg["drafts_dir"])
    os.makedirs(drafts_dir, exist_ok=True)

    model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    available, msg = llm.is_available(model)

    if available:
        threshold = search_cfg["cover_letter_threshold"]
        top_jobs = [j for j in scored if j["match_score"] >= threshold]
        print(f"Drafting cover letters locally (Ollama: {model}) for "
              f"{len(top_jobs)} jobs scoring >= {threshold}%...")
        print("(This runs on your machine — first run may be slow while the model loads.)")
        for job in top_jobs:
            try:
                letter = llm.draft_cover_letter(job, profile, model)
                fname = f"{llm.safe_filename(job['company'])}_{llm.safe_filename(job['title'])}.txt"
                path = os.path.join(drafts_dir, fname)
                with open(path, "w") as f:
                    f.write(letter)
                job["cover_letter_path"] = os.path.join(out_cfg["drafts_dir"], fname)
                print(f"  drafted: {fname}")
            except Exception as e:
                print(f"  [warn] cover letter failed for {job.get('company')}: {e}")
    else:
        print(f"Skipping cover letter drafting: {msg}\n")

    out_path = os.path.join(here, out_cfg["excel_file"])
    write_results(scored, out_path)
    print(f"\nDone. Results written to: {out_path}")
    print("Open the file, review matches top to bottom, and apply manually.")


if __name__ == "__main__":
    main()
