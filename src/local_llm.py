"""
local_llm.py — Drafts cover letters using a LOCAL LLM via Ollama.

No API key, no account, no internet call at inference time, nothing leaves
your machine. Requires Ollama (https://ollama.com) installed and running,
with at least one model pulled (e.g. `ollama pull llama3.2:3b`).

If Ollama isn't running or no model is available, this degrades gracefully:
the rest of the agent (job search + scoring + Excel output) still works,
it just skips the cover-letter drafting step.
"""
import os
import re
import requests

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
TIMEOUT = 90  # local generation can be slow on CPU-only machines

PROMPT_TEMPLATE = """You are helping draft a short, specific, honest cover letter for a real job application.

Candidate profile:
- Name: {name}
- ~{years} years experience as a Java Backend Developer
- Core stack: Java, Spring Boot, Spring Cloud, Microservices, REST APIs, MySQL, PostgreSQL, Redis, RabbitMQ, Docker, Jenkins
- Notable project: CareerForcePro, an AI hiring automation platform - Spring Cloud/RabbitMQ/Redis, 10,000+ candidate profiles, 99.9% uptime
- Current role: Software Engineer at Netsmartz IT Solutions - cut API response time 20% via SQL optimization, cut deployment time 30% via Jenkins/Docker CI/CD

Job posting:
- Company: {company}
- Title: {title}
- Location: {location}
- Description (may be partial/HTML-stripped): {description}

Write a 4-paragraph cover letter (under 220 words total):
1. Opening: state the role and one strong, specific hook tying the candidate to THIS job.
2. Relevant experience: 2-3 concrete, quantified points from the candidate's background that map to what this JD actually asks for. Do not invent metrics or skills not listed above.
3. Briefly and honestly address any real gap (e.g. if the JD wants AWS/Kafka and the candidate doesn't have it) by framing it as active upskilling - only if relevant, otherwise skip this paragraph.
4. Closing: brief, confident, no cliches like "I am passionate about technology."

Output ONLY the letter text. Plain text, no markdown, no headers, no placeholders,
no explanation of what you're doing. Start directly with "Dear Hiring Manager,"
and end with "Sincerely,\n{name}".
"""


def _strip_html(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:2000]


def is_available(model=None):
    """Checks whether Ollama is running and the requested model is pulled."""
    model = model or DEFAULT_MODEL
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        r.raise_for_status()
    except requests.RequestException:
        return False, "Ollama doesn't seem to be running (couldn't reach " \
                       f"{OLLAMA_HOST}). Start it with `ollama serve` or open the Ollama app."
    names = [m.get("name", "") for m in r.json().get("models", [])]
    # Ollama model names sometimes include a ":tag" suffix, e.g. "llama3.1:latest"
    if not any(n == model or n.startswith(model + ":") for n in names):
        available = ", ".join(names) if names else "(none pulled yet)"
        return False, (f"Model '{model}' isn't pulled. Run `ollama pull {model}` "
                        f"first. Models currently available: {available}")
    return True, ""


def draft_cover_letter(job, profile, model=None):
    model = model or DEFAULT_MODEL
    description = _strip_html(job.get("description", ""))
    prompt = PROMPT_TEMPLATE.format(
        name=profile["name"],
        years=profile["years_experience"],
        company=job.get("company", "the company"),
        title=job.get("title", "the role"),
        location=job.get("location", ""),
        description=description,
    )
    resp = requests.post(
        f"{OLLAMA_HOST}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False,
              "options": {"temperature": 0.4}},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json().get("response", "").strip()


def safe_filename(s):
    s = re.sub(r"[^a-zA-Z0-9_-]+", "_", s)
    return s.strip("_")[:60]
