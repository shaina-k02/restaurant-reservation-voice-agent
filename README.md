# Resume Tailor — OpenClaw Skill

An OpenClaw skill that tailors a resume (PDF, DOCX, or LaTeX) to a specific job posting. Creates a new versioned resume file and prints an analysis of strengths, gaps, and suggested improvements.

## Setup

```bash
cp -r . ~/.openclaw/workspace/skills/resume-tailor
pip install pdfplumber python-docx reportlab --break-system-packages
openclaw gateway restart
```

## Usage

```bash
openclaw agent --agent main --local -m \
  "Tailor my resume at ~/resume.pdf for this job: [paste job description or URL]"
```

**Output:**
- New file at `~/Desktop/tailored_resumes/tailored_resume_<company>_<role>_v1.pdf`
- Terminal summary with STRENGTHS, GAPS, and SUGGESTED IMPROVEMENTS

## Evals

Seven test cases covering PDF/DOCX/LaTeX inputs, missing input detection, sparse job descriptions, and version incrementing.

```bash
python3 scripts/generate_sample_resumes.py   # first time only
python3 scripts/run_evals.py                  # run all 7
python3 scripts/run_evals.py --eval-id 1 4 5  # run specific evals
```

| ID | Scenario | Tests |
|----|----------|-------|
| 1 | PDF + Stripe Data Engineer | Full flow, versioning, output format |
| 2 | DOCX + ML startup | DOCX handling, ML-specific analysis |
| 3 | LaTeX + Microsoft SWE II | LaTeX preservation, C#/.NET gap detection |
| 4 | Resume only, no job | Asks for missing input |
| 5 | Job only, no resume | Asks for missing input |
| 6 | Sparse job description | Doesn't refuse |
| 7 | Repeat request | Creates v2, doesn't skip |

## Project Structure

```
.
├── SKILL.md                          # Skill definition
├── README.md
├── evals/
│   ├── evals.json                    # 7 test cases with assertions
│   └── files/
│       └── sample_resume.tex         # Sample LaTeX resume
└── scripts/
    ├── generate_sample_resumes.py    # Generates PDF/DOCX samples
    └── run_evals.py                  # Eval runner with grading
```

## Prerequisites

- Node.js 22+ and [OpenClaw](https://openclaw.ai) with Anthropic API key
- Python 3.9+
