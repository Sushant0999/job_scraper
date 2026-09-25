# Job Search Agent (Semi-Automated, Fully Local AI)

Finds jobs, scores them against your profile, drafts cover letters for your
best matches using a **local LLM** — no API key, no account, no cost, and
nothing leaves your machine. Then it stops there: you review the Excel
output and click "Apply" yourself on each platform.

## Why it doesn't auto-apply on LinkedIn / Naukri / Indeed

None of them offer a public application API. The only way to "auto-apply"
there is a browser bot that clicks through their UI — which violates their
terms of service and can get your account flagged or banned. This agent
only talks to sources that are *meant* to be queried programmatically:

| Source | What it is | Auth needed |
|---|---|---|
| [Adzuna](https://developer.adzuna.com/) | Job aggregator with strong India + global coverage | Free `app_id` + `app_key` |
| [Arbeitnow](https://www.arbeitnow.com/api/job-board-api) | Free public job board API (mostly remote/global) | None |
| [RemoteOK](https://remoteok.com/api) | Free public API for remote tech jobs | None |
| Greenhouse / Lever | Public job-board APIs for specific companies | None (you add company tokens) |

## Why a local LLM instead of a cloud API

Cover letter drafting uses [Ollama](https://ollama.com) — a free tool that
runs open models (Llama, Mistral, Gemma, etc.) directly on your machine.
No signup, no API key, no per-request cost, no data leaving your laptop.
The trade-off: it needs ~5-8GB free RAM/VRAM for a decent small model, and
drafting is slower than a cloud API (especially on CPU-only machines).

## Setup

```bash
cd job_agent
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

1. Get a **free** Adzuna app_id/app_key at https://developer.adzuna.com/ and
   put them in `.env`. (Skip this and you'll still get Arbeitnow + RemoteOK
   remote results — just less India-specific coverage.)
2. Install Ollama from https://ollama.com (Mac/Windows/Linux installers, or
   `curl -fsSL https://ollama.com/install.sh | sh` on Linux).
3. Pull a model and leave Ollama running in the background:
   ```bash
   ollama pull llama3.2:3b   # ~2GB, fits fully on a 4GB-VRAM GPU (e.g. GTX 1650), fast
   ollama serve              # if it isn't already running as a background service
   ```
   This is the project's default model — chosen to run well on modest GPUs
   (4GB VRAM / quad-core mobile CPU class hardware). If you have a beefier
   GPU and want noticeably better letters at the cost of speed, try:
   ```bash
   ollama pull llama3.1:8b   # ~4.7GB, needs ~8GB+ combined VRAM/RAM, much slower on 4GB cards
   ```
   and set `OLLAMA_MODEL=llama3.1:8b` in `.env`.
4. Edit `config.yaml`:
   - Your skills are pre-filled from your resume — add/remove as your stack changes.
   - `search.titles` / `search.locations` — what to search for.
   - `search.min_match_score` — filters out weak matches before they hit the spreadsheet.
   - `search.cover_letter_threshold` — only jobs scoring at/above this get a drafted letter (keeps local generation time down).
   - `company_boards` — add specific companies' Greenhouse/Lever board tokens if you want to track them directly (find the token in their careers page URL).

## Run it

```bash
python main.py
```

The script checks whether Ollama is running and the model is pulled before
attempting any drafting — if either is missing, it tells you exactly what
to fix and still completes the job search + scoring + Excel export without
cover letters.

Output:
- `job_agent_results.xlsx` — every job that passed your minimum score, ranked, with matched skills, gaps flagged, and a link to apply.
- `drafts/` — a `.txt` cover letter per top-scoring job, named `Company_Title.txt`. Read each one before sending — local models are good but make mistakes, just like cloud ones.

## Suggested workflow

1. Run it once a week (`python main.py`).
2. Open `job_agent_results.xlsx`, sort by Match Score.
3. For each job you like: open the `Application Link`, skim the drafted cover letter in `drafts/` if there is one, tweak it, and apply manually.
4. Update the `Status` column yourself as you go (this file doesn't auto-track applications — for that, use the separate Applications Log tracker from your resume review).

## Extending it

- Add more Greenhouse/Lever company tokens to `config.yaml` as you discover companies you like — no code changes needed.
- The scoring in `src/scorer.py` is plain keyword-weight matching, intentionally simple and free to run on hundreds of jobs.
- Want a different model? Any Ollama model works — just `ollama pull <name>` and set `OLLAMA_MODEL=<name>` in `.env`. Larger models (e.g. `llama3.1:70b`) draft better letters but need much more RAM/VRAM and time.
- Naukri/LinkedIn do offer **email job alerts** you can subscribe to manually — those are a ToS-safe complement to this agent, just not something this script can act on automatically.
