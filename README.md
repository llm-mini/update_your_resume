# Resume Maker

Edit one text file. Trigger a workflow. Get a polished, ATS-friendly resume PDF — committed back to your repo.

## The Problem

Tailoring a resume for each job application is tedious:
- Copy-paste between versions loses formatting
- Manually reordering skills to match a job description takes time
- Keeping a PDF in sync with edits is error-prone
- No version history of what you sent to which company

This project solves all of that with a single text file as the source of truth and a GitHub Actions workflow that does the rest.

---

## How It Works

```
Edit resume_data.txt
        ↓
Commit from GitHub browser
        ↓
Trigger workflow manually (Actions tab)
        ↓
LLM parses free-form text → structured JSON
LLM reorders skills to match JD (if provided)
        ↓
Generates resume.md  (ATS-safe Markdown)
Generates resume.pdf (two-column, styled)
        ↓
Both files committed to export/<company_name>/
```

---

## Architecture

```
resume-maker/
├── resume_data.txt          # Your resume data (edit this)
├── test_data.txt            # Baseline test — exact reference resume content
├── generate.py              # Core generator: parser + LLM + Markdown + PDF
├── template.html            # Jinja2 HTML template (two-column layout)
├── style.css                # A4 print CSS for WeasyPrint
├── requirements.txt
├── .env                     # OPENROUTER_API_KEY (local only, gitignored)
├── .github/
│   └── workflows/
│       └── generate_resume.yml
└── export/
    └── <resume_name>/
        ├── resume.md        # ATS-friendly single-column Markdown
        └── resume.pdf       # Two-column styled PDF with clickable links
```

### Key components

| Component | Role |
|-----------|------|
| `resume_data.txt` | Single source of truth. Sections for personal info, skills, experience, projects, optional JD |
| `generate.py` | Parses the text file, calls OpenRouter LLM, renders Markdown + PDF |
| `template.html` + `style.css` | Two-column resume layout (WeasyPrint-compatible) |
| GitHub Actions workflow | Manual dispatch — installs deps, generates files, commits output |

### LLM usage (OpenRouter — free tier)
- **Model**: `google/gemma-4-31b-it:free` (fallback: `openai/gpt-oss-120b:free`)
- Parses free-form text into structured resume data
- Reorders skills to match job description keywords (if `[jd]` section filled)
- Polishes bullet grammar without changing facts or adding information

---

## Setup

### 1. Fork / clone this repo

```bash
git clone https://github.com/<your-username>/resume-maker.git
cd resume-maker
```

### 2. Get an OpenRouter API key

1. Sign up at [openrouter.ai](https://openrouter.ai)
2. Go to **Keys** → create a new key
3. Copy the key

### 3. Add the key as a GitHub secret

In your repo: **Settings → Secrets and variables → Actions → New repository secret**

- Name: `OPENROUTER_API_KEY`
- Value: your key

### 4. Fill in your resume data

Edit `resume_data.txt`:

- **Static sections** (`[personal]`, `[education]`, `[honors]`, `[certifications]`) — fill once, rarely change
- **Dynamic sections** — update per application:
  - `[meta]` — set `resume_name` (becomes the export folder name, e.g. `google_sde`)
  - `[skills]` — list your skills (write freely, LLM will structure and group them)
  - `[experience]` — describe each role (write naturally, LLM will format into resume bullets)
  - `[projects]` — describe projects
  - `[jd]` — paste the job description here to get JD-matched skill ordering (optional)

### 5. Commit and trigger the workflow

1. Edit `resume_data.txt` directly in the GitHub browser
2. Commit the change
3. Go to **Actions → Generate Resume → Run workflow**
4. Wait ~60 seconds
5. Find your resume at `export/<resume_name>/resume.md` and `resume.pdf`

---

## Local Testing

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate        # Linux/Mac
# or
.\venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Copy and fill in your API key
cp .env.example .env            # or just edit .env directly
# Add: OPENROUTER_API_KEY=sk-or-...

# Run baseline test (uses reference resume content)
python generate.py --input test_data.txt --skip-pdf

# Run with your data
python generate.py --skip-pdf
```

> **Note:** `--skip-pdf` is needed on Windows because WeasyPrint requires GTK system libraries not available by default. PDF generation works correctly on Linux (including GitHub Actions).

Output is written to `export/<resume_name>/resume.md`.

---

## Workflow Options

The GitHub Actions workflow accepts one optional input:

| Input | Default | Description |
|-------|---------|-------------|
| `input_file` | `resume_data.txt` | Which input file to use. Set to `test_data.txt` to run a baseline test. |

---

## Output

### `resume.md`
ATS-safe single-column Markdown. Clean heading hierarchy, no HTML, plain bullet lists. Paste into any ATS scanner or share as a readable file.

### `resume.pdf`
Two-column styled PDF matching a professional resume format:
- **Left**: Professional Experience
- **Right**: Skills, Awards, Projects, Certifications, Education
- Clickable links for email, LinkedIn, GitHub

---

## Tips

- Set `resume_name` in `[meta]` to something like `amazon_sde2` or `stripe_backend` — this creates a versioned folder per application in `export/`
- Paste the full JD under `[jd]` for best skill reordering — the more text, the better the keyword matching
- The `[skills]` section can be written loosely: `Python, SQL, Docker, LangChain` on one line or spread across lines — LLM groups them intelligently
- Keep `test_data.txt` untouched as a regression baseline to verify layout after any template changes
