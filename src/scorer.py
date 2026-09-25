"""
scorer.py — Scores each job against your profile's skills.

Pure keyword-overlap scoring, no external API calls needed. Transparent and
fast to run on hundreds of jobs. Anthropic API is reserved for the more
expensive step (drafting cover letters for the top matches only), in main.py.
"""
import re

# Real job postings phrase the same skill in different ways ("Spring" vs
# "Spring Boot", "REST" vs "RESTful APIs", etc). Without aliases, a lot of
# genuinely relevant jobs get scored too low just because of wording. Each
# entry: the skill term (as it appears in config.yaml) -> extra substrings
# that should count as a match for that skill.
ALIASES = {
    "spring boot": ["spring", "springboot", "spring framework", "spring mvc"],
    "rest api": ["rest", "restful", "restful api", "rest apis", "api development"],
    "microservices": ["microservice", "micro-service", "micro services"],
    "ci/cd": ["cicd", "continuous integration", "continuous deployment", "continuous delivery"],
    "sql": ["mysql", "postgresql", "postgres", "oracle db", "t-sql", "pl/sql"],
    "junit": ["unit testing", "unit tests", "test driven", "tdd"],
}


def _normalize(text):
    return re.sub(r"[^a-z0-9+./# ]", " ", (text or "").lower())


def score_job(job, profile):
    """Returns (score 0-100, matched_skills list, missing_gap_skills list)."""
    text = _normalize(job.get("title", "") + " " + job.get("description", ""))

    skills = profile["core_skills"]
    total_weight = sum(s["weight"] for s in skills)
    matched_weight = 0
    matched = []

    for s in skills:
        term_l = s["term"].lower()
        candidates = [term_l] + ALIASES.get(term_l, [])
        if any(c in text for c in candidates):
            matched_weight += s["weight"]
            matched.append(s["term"])

    base_score = (matched_weight / total_weight) * 100 if total_weight else 0

    # Small bonus if the job title itself contains "java" or "spring boot"
    title_l = _normalize(job.get("title", ""))
    if "java" in title_l:
        base_score += 8
    if "spring" in title_l:
        base_score += 5

    score = min(round(base_score), 100)

    gap_hits = [g for g in profile.get("gap_skills", []) if g.lower() in text]

    return score, matched, gap_hits


def score_all(jobs, profile, min_score):
    scored = []
    for job in jobs:
        score, matched, gaps = score_job(job, profile)
        if score < min_score:
            continue
        job["match_score"] = score
        job["matched_skills"] = matched
        job["gap_flags"] = gaps
        scored.append(job)
    scored.sort(key=lambda j: j["match_score"], reverse=True)
    return scored
