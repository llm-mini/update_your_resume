import argparse
import json
import os
import re
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
PRIMARY_MODEL = "google/gemma-4-31b-it:free"
FALLBACK_MODEL = "openai/gpt-oss-120b:free"


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_input_file(filepath: str) -> dict:
    """Parse resume_data.txt into a dict keyed by section name."""
    text = Path(filepath).read_text(encoding="utf-8")
    sections = {}
    current_section = None
    current_lines = []

    for line in text.splitlines():
        stripped = line.strip()
        # Skip comments and blank lines outside sections
        if stripped.startswith("#"):
            continue
        section_match = re.match(r"^\[(\w+)\]$", stripped)
        if section_match:
            if current_section is not None:
                sections[current_section] = "\n".join(current_lines).strip()
            current_section = section_match.group(1).lower()
            current_lines = []
        elif current_section is not None:
            current_lines.append(line)

    if current_section is not None:
        sections[current_section] = "\n".join(current_lines).strip()

    return sections


# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------

def call_llm(prompt: str, model: str) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/resume-maker",
        "X-Title": "Resume Maker",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }
    resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    body = resp.json()
    if "choices" not in body:
        raise RuntimeError(f"No 'choices' in response: {json.dumps(body)}")
    return body["choices"][0]["message"]["content"]


def build_prompt(sections: dict) -> str:
    has_jd = bool(sections.get("jd", "").strip())
    jd_instruction = (
        "A job description is provided in the [jd] section. "
        "Reorder the skill groups so skills that match JD keywords appear first. "
        "Within each group, surface matching skills first."
        if has_jd
        else "No job description provided. Order skill groups by general importance: "
             "AI/ML and LLMs first, then Data Engineering, then Web/API/Backend, "
             "then Infrastructure/DevOps, then Programming Languages/Databases."
    )

    return f"""You are a resume structuring assistant. Parse the raw resume input below and return ONLY valid JSON — no markdown fences, no explanation.

## Task
1. Parse each section into structured data.
2. {jd_instruction}
3. Polish bullet points: fix grammar, ensure each starts with a strong action verb, preserve all numbers and facts exactly.
4. Do NOT invent or add any information not present in the input.

## Required JSON schema
{{
  "personal": {{
    "name": "string",
    "email": "string",
    "phone": "string",
    "linkedin_username": "string",
    "linkedin_url": "string",
    "github_username": "string",
    "github_url": "string",
    "location": "string"
  }},
  "education": {{
    "degree": "string",
    "college": "string",
    "years": "string",
    "cgpa": "string"
  }},
  "honors": ["string"],
  "certifications": ["string"],
  "meta": {{
    "company": "string",
    "resume_name": "string"
  }},
  "skills": [
    {{
      "group": "short group label e.g. AI/ML & LLMs",
      "skills_list": ["skill1", "skill2"]
    }}
  ],
  "experience": [
    {{
      "title": "string",
      "company": "string",
      "period": "string",
      "location": "string",
      "bullets": [
        {{
          "bold": "Project or feature name (or empty string if none)",
          "text": "Rest of the bullet text"
        }}
      ]
    }}
  ],
  "projects": [
    {{
      "name": "string",
      "bullets": ["string"]
    }}
  ]
}}

## Input sections

### [personal]
{sections.get('personal', '')}

### [education]
{sections.get('education', '')}

### [honors]
{sections.get('honors', '')}

### [certifications]
{sections.get('certifications', '')}

### [meta]
{sections.get('meta', '')}

### [skills]
{sections.get('skills', '')}

### [experience]
{sections.get('experience', '')}

### [projects]
{sections.get('projects', '')}

### [jd]
{sections.get('jd', '(none)')}

Return ONLY the JSON object."""


def normalize_data(data: dict) -> dict:
    """Fix common LLM output quirks so templates never crash."""
    # skills: normalize to skills_list key (avoid Jinja2 dict.items() collision)
    for group in data.get("skills", []):
        # LLM may return "items" or "skills_list" — normalize to "skills_list"
        if "items" in group and "skills_list" not in group:
            group["skills_list"] = group.pop("items")
        sl = group.get("skills_list", [])
        if isinstance(sl, str):
            group["skills_list"] = [s.strip() for s in sl.split(",") if s.strip()]
        elif not isinstance(sl, list):
            group["skills_list"] = [str(sl)]

    # experience bullets: ensure each is a dict with bold + text
    for job in data.get("experience", []):
        normalized = []
        for b in job.get("bullets", []):
            if isinstance(b, str):
                normalized.append({"bold": "", "text": b})
            elif isinstance(b, dict):
                b.setdefault("bold", "")
                b.setdefault("text", "")
                normalized.append(b)
        job["bullets"] = normalized

    # projects: ensure bullets is a list of strings
    for proj in data.get("projects", []):
        bullets = proj.get("bullets", [])
        proj["bullets"] = [str(b) for b in bullets]

    # lists: ensure honors and certifications are lists
    for key in ("honors", "certifications"):
        val = data.get(key, [])
        if isinstance(val, str):
            data[key] = [v.strip() for v in val.splitlines() if v.strip()]

    return data


def structure_with_llm(sections: dict) -> dict:
    if not OPENROUTER_API_KEY:
        print("ERROR: OPENROUTER_API_KEY not set in .env or environment.", file=sys.stderr)
        sys.exit(1)

    prompt = build_prompt(sections)
    for model in [PRIMARY_MODEL, FALLBACK_MODEL]:
        print(f"Calling LLM ({model})...")
        try:
            raw = call_llm(prompt, model)
            # Strip markdown fences if model disobeys
            raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
            raw = re.sub(r"\s*```$", "", raw.strip())
            data = json.loads(raw)
            data = normalize_data(data)
            print("LLM structured data successfully.")
            return data
        except (requests.HTTPError, RuntimeError) as e:
            print(f"Model {model} failed: {e}. Trying fallback...", file=sys.stderr)
        except json.JSONDecodeError as e:
            print(f"Model {model} returned invalid JSON: {e}. Trying fallback...", file=sys.stderr)

    print("ERROR: All LLM models failed.", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Markdown generation
# ---------------------------------------------------------------------------

MARKDOWN_TEMPLATE = """\
# {{ data.personal.name }}

{{ data.personal.email }} | {{ data.personal.phone }} | [LinkedIn]({{ data.personal.linkedin_url }}) | [GitHub]({{ data.personal.github_url }}) | {{ data.personal.location }}

---

## Professional Experience
{% for job in data.experience %}

### {{ job.title }}
**{{ job.company }}** | {{ job.period }} | {{ job.location }}
{% for b in job.bullets %}
- {% if b.bold %}**{{ b.bold }}**{% if b.text %} {{ b.text }}{% endif %}{% else %}{{ b.text }}{% endif %}
{% endfor %}
{% endfor %}

---

## Technical Skills
{% for group in data.skills %}
- **{{ group.group }}**: {{ group.skills_list | join(', ') }}
{% endfor %}

---

## Projects
{% for proj in data.projects %}

### {{ proj.name }}
{% for b in proj.bullets %}
- {{ b }}
{% endfor %}
{% endfor %}

---

## Honors & Awards
{% for h in data.honors %}
- {{ h }}
{% endfor %}

---

## Certifications
{% for c in data.certifications %}
- {{ c }}
{% endfor %}

---

## Education

**{{ data.education.degree }}**
{{ data.education.college }}
{{ data.education.years }} | CGPA: {{ data.education.cgpa }}
"""


def render_markdown(data: dict) -> str:
    env = Environment()
    tmpl = env.from_string(MARKDOWN_TEMPLATE)
    return tmpl.render(data=data)


# ---------------------------------------------------------------------------
# PDF generation
# ---------------------------------------------------------------------------

def render_pdf(data: dict, output_path: str, script_dir: Path):
    from weasyprint import HTML, CSS

    template_path = script_dir / "template.html"
    css_path = script_dir / "style.css"

    jinja_env = Environment(loader=FileSystemLoader(str(script_dir)))
    tmpl = jinja_env.get_template("template.html")
    html_content = tmpl.render(data=data)

    css = CSS(filename=str(css_path))
    HTML(string=html_content, base_url=str(script_dir)).write_pdf(
        output_path, stylesheets=[css]
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate ATS resume from text file")
    parser.add_argument(
        "--input", default="resume_data.txt",
        help="Input data file (default: resume_data.txt)"
    )
    parser.add_argument(
        "--skip-pdf", action="store_true",
        help="Skip PDF generation (useful on Windows where WeasyPrint needs GTK)"
    )
    args = parser.parse_args()

    script_dir = Path(__file__).parent

    input_path = script_dir / args.input
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Parsing {input_path}...")
    sections = parse_input_file(str(input_path))

    data = structure_with_llm(sections)

    resume_name = data.get("meta", {}).get("resume_name", "output").strip()
    if not resume_name:
        resume_name = "output"
    # Sanitize folder name
    resume_name = re.sub(r"[^\w\-]", "_", resume_name)

    export_dir = script_dir / "export" / resume_name
    export_dir.mkdir(parents=True, exist_ok=True)

    md_path = export_dir / "resume.md"
    pdf_path = export_dir / "resume.pdf"

    print("Rendering Markdown...")
    md_content = render_markdown(data)
    md_path.write_text(md_content, encoding="utf-8")
    print(f"Markdown saved: {md_path}")

    if args.skip_pdf:
        print("Skipping PDF generation (--skip-pdf)")
    else:
        print("Rendering PDF...")
        render_pdf(data, str(pdf_path), script_dir)
        print(f"PDF saved: {pdf_path}")

    print(f"\nDone! Output in: export/{resume_name}/")


if __name__ == "__main__":
    main()
