# Resume Maker — Claude Reference

## Project Purpose
GitHub-based ATS resume generator. User edits one text file, triggers GitHub Actions manually, LLM parses + structures data, outputs Markdown + two-column PDF committed back to repo.

## Repo Structure
```
resume-maker/
├── resume_data.txt          # INPUT: edit this per job application
├── test_data.txt            # BASELINE: Anil's exact resume content for regression testing
├── generate.py              # Core script: parse → LLM → MD + PDF
├── template.html            # Jinja2 two-column HTML (WeasyPrint renders this to PDF)
├── style.css                # A4 print CSS for WeasyPrint
├── requirements.txt         # weasyprint, jinja2, requests, python-dotenv
├── .env                     # OPENROUTER_API_KEY (gitignored)
├── .gitignore
├── .github/workflows/
│   └── generate_resume.yml  # Manual dispatch workflow
├── export/
│   └── <resume_name>/       # Generated output folder
│       ├── resume.md
│       └── resume.pdf
└── Sample/
    └── Anil_Resume_with_Qcom.pdf  # Reference PDF (original resume)
```

## Input File Format (`resume_data.txt`)
Sections delimited by `[section_name]`. Lines starting with `#` are comments.

**Static sections** (pre-filled, rarely change):
- `[personal]` — name, email, phone, linkedin_username, linkedin_url, github_username, github_url, location
- `[education]` — degree, college, years, cgpa
- `[honors]` — bullet list
- `[certifications]` — bullet list

**Dynamic sections** (edit per job application):
- `[meta]` — `company:` and `resume_name:` (resume_name becomes the export folder name)
- `[skills]` — write freely, LLM structures and reorders
- `[experience]` — write freely, LLM parses into structured bullets
- `[projects]` — write freely, LLM structures
- `[jd]` — optional job description; if present, LLM reorders skills to match JD keywords first

## LLM Integration
- **Provider**: OpenRouter (free tier)
- **Primary model**: `google/gemma-4-31b-it:free`
- **Fallback model**: `openai/gpt-oss-120b:free`
- **API key**: `OPENROUTER_API_KEY` in `.env` locally, GitHub secret in CI
- Single LLM call per run — all sections sent in one prompt, returns structured JSON
- `normalize_data()` in `generate.py` fixes common LLM output quirks (type coercion, key normalization)

## Critical Implementation Notes

### Jinja2 `items` key collision
Skill groups use key `skills_list` (NOT `items`). `group.items` in Jinja2 calls Python's `dict.items()` method — causes `TypeError: 'builtin_function_or_method' object is not iterable`. Never rename back to `items`.

### WeasyPrint on Windows
WeasyPrint requires GTK/Pango native DLLs — not available on Windows without manual GTK install. Use `--skip-pdf` flag for local testing. PDF generation works correctly on Ubuntu (GitHub Actions).

### Rate limits
OpenRouter free tier has per-minute rate limits. Space out test runs — hitting 429 is common during rapid development iteration.

## CLI Usage
```bash
# Install deps
pip install -r requirements.txt

# Generate from main input file
python generate.py

# Run baseline test (Anil's exact resume content)
python generate.py --input test_data.txt

# Skip PDF on Windows
python generate.py --input test_data.txt --skip-pdf

# Custom input file
python generate.py --input my_custom_input.txt
```

Output always goes to `export/<resume_name>/resume.md` + `resume.pdf`.

## GitHub Actions Workflow
- **Trigger**: Manual dispatch only (`workflow_dispatch`)
- **Optional input**: `input_file` param (defaults to `resume_data.txt`)
- **Steps**: checkout → setup Python 3.11 → install WeasyPrint system libs → pip install → generate → commit export/ back to same branch → upload artifact
- **Required secret**: `OPENROUTER_API_KEY`
- Generated files committed with `[skip ci]` to avoid re-triggering

## PDF Layout (Two-Column)
- **Header**: Name large, contact row with email/phone/LinkedIn/GitHub/location links
- **Left (~60%)**: Professional Experience — bold project names, metric-rich bullets
- **Right (~40%)**: Technical Skills, Honors & Awards, Projects, Certifications, Education
- CSS uses table layout (not flexbox) for WeasyPrint compatibility

## Skill Ordering Logic
- **With JD**: LLM surfaces skills matching JD keywords first within and across groups
- **Without JD**: General importance order — AI/ML → Data Engineering → Web/API → Infrastructure → Languages/Databases
