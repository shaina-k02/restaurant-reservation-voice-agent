---
name: resume-tailor
description: >
  Tailor a resume to a specific job posting. Use this skill whenever the user wants to customize,
  adapt, or tailor their resume for a job application. Triggers include: uploading a resume file
  (PDF, DOC, DOCX, or LaTeX) alongside a job description or job posting URL, asking to "tailor
  my resume", "customize my resume for this role", "match my resume to this job", or any request
  to align resume content with a specific position. Also use when the user asks for a gap analysis,
  strength assessment, or improvement suggestions relative to a job posting — even if they don't
  explicitly say "tailor". Do NOT use for writing a resume from scratch or for general resume
  formatting without a target job.
---

# Resume Tailor

Tailor an existing resume to a specific job posting. Produce a new resume file and a brief
analysis of strengths, gaps, and suggested improvements.

## Inputs

Two inputs are required:

1. **A resume** — a file path to a PDF, DOC/DOCX, or LaTeX (.tex) file.
2. **A job target** — either a URL to a job posting, or a pasted job description.

If either input is missing, ask for it before doing anything else.

## Workflow

Follow these steps in order. Do not skip steps.

### Step 1: Extract resume content

First, ensure parsing tools are available:
```bash
pip install pdfplumber python-docx --break-system-packages -q 2>/dev/null
```

Then extract text based on file type:
- **PDF**: Use `pdfplumber` in a Python script. If extraction returns mostly empty text (scanned document), note this to the user.
- **DOCX**: Use `python-docx` to read paragraphs and tables. Preserve section headers.
- **DOC**: Convert to DOCX with `libreoffice --headless --convert-to docx`, then read as DOCX.
- **LaTeX (.tex)**: Read the raw file. The LaTeX source is human-readable — extract content by reading the text between `\begin{document}` and `\end{document}`.

You now have the full resume text in memory. Do not save it to a temp file — just use it directly.

### Step 2: Extract job requirements

- **URL**: Fetch the page with `web_fetch` or `curl`. Extract the relevant job content.
- **Pasted text**: Use it directly.

From the job content, identify:
- Job title and company
- Required qualifications and skills
- Preferred/nice-to-have qualifications
- Key responsibilities
- Technologies and tools mentioned

If the job posting is sparse (just a title and a few bullets), work with what's available — do not refuse.

### Step 3: Analyze and tailor

With both the resume content and job requirements in hand, do the following analysis:

**Strengths**: Which resume experiences, skills, or qualifications directly match job requirements? Be specific — name the skill and the requirement it matches.

**Gaps**: Which job requirements are missing from the resume entirely, or present but understated? Distinguish between hard gaps (not mentioned at all) and soft gaps (mentioned but could be stronger).

**Suggested improvements**: What concrete actions could the candidate take beyond what's in the tailored resume? These are things the candidate should do themselves — add a project, get a certification, quantify a vague achievement with real numbers only they know.

Then generate the tailored resume:
- Rewrite the professional summary to align with the target role.
- Reorder sections and bullet points so the most relevant content comes first.
- Weave in keywords from the job description where they authentically apply to existing experience.
- Strengthen vague bullets by making them more specific (e.g., "worked on backend" → "built RESTful APIs serving 50K+ DAU").
- Keep the tailoring proportional — this is a targeted edit, not a rewrite. Preserve the candidate's voice and structure.
- **One-pager**: The tailored resume MUST fit on a single page. To achieve this, trim less relevant bullet points, combine related points, shorten verbose descriptions, and remove sections that don't contribute to the target role. Keep the most impactful content — quality over quantity.
- **No random bolding**: Do not bold random words or phrases in the resume body. Only bold the candidate's name, section headings (Experience, Education, Skills, etc.), and job titles/company names. Everything else should be regular weight text.

**Critical rule**: Never invent experiences, skills, certifications, or metrics that aren't in the original resume. Rewording existing content is fine. Adding fabricated content is not.

### Step 4: Save the tailored resume as a new file

Always generate a new tailored resume, even if a previous version exists for the same job. Never skip generation because a previous version was already created. Every run produces a new file.

Generate the tailored resume in the **same format as the input**:
- PDF input → generate a DOCX first using `python-docx` with proper formatting (name as a heading, contact info on a separate line below, clear section headers, bullet points for experience). Then convert to PDF using `libreoffice --headless --convert-to pdf`. If libreoffice is not available, save as DOCX instead and note this to the user. Do NOT use reportlab — it produces poorly formatted PDFs with overlapping text.
- DOCX input → new DOCX (use `python-docx` with proper paragraph styles, headings, and bullet points)
- LaTeX input → new `.tex` file

File naming: `tailored_resume_<company>_<jobtitle>_v<N>.<ext>` (lowercase, underscores for spaces).
- Check `~/Desktop/tailored_resumes/` for existing versions and increment the number.
- First run: `tailored_resume_stripe_data_engineer_v1.pdf`
- Second run: `tailored_resume_stripe_data_engineer_v2.pdf`
- Third run: `tailored_resume_stripe_data_engineer_v3.pdf`

Save to: `~/Desktop/tailored_resumes/` (create the directory if it doesn't exist).
If the user specifies a different path, use that instead.

Do not modify the original resume file.

### Step 5: Print the analysis

After saving the file, print this analysis to the terminal. This is the primary output the user sees — do not skip it or truncate it.

Print exactly three sections: STRENGTHS, GAPS, and SUGGESTED IMPROVEMENTS. No other sections. Do not add "Key Changes Made", "Changes Summary", or any other heading.

```
============================================================
RESUME TAILORING COMPLETE
============================================================

Target: [Job Title] at [Company]

STRENGTHS:
  • [2-5 bullets: what in the resume matches the job]

GAPS:
  • [2-5 bullets: what the job requires that's missing or weak]

SUGGESTED IMPROVEMENTS:
  • [2-5 bullets: actionable next steps for the candidate]

Tailored resume saved to: ~/Desktop/tailored_resumes/[filename]
============================================================
```

Guidelines for the bullets:
- Reference specific skills, tools, and requirements by name.
- Strengths should cite both the resume evidence and the matching requirement.
- Gaps should name the missing requirement and note whether it's a hard or soft gap.
- Improvements should be things the candidate can actually act on — not generic advice.
  Good: "Add Snowflake to your skills if you have any hands-on exposure."
  Bad: "Consider gaining more experience in data warehousing."

## What NOT to do

- Do not print the tailored resume content in the chat. It goes in the file only.
- The summary must contain ONLY three headings: STRENGTHS, GAPS, and SUGGESTED IMPROVEMENTS. Do not add ANY other heading or section including but not limited to: "Key Changes", "Key Changes from Previous Version", "Changes Made", "Changes Summary", "What Changed", "Resume Changes", or anything similar. If you feel the urge to describe what you changed, put it inside the SUGGESTED IMPROVEMENTS bullets — not in a separate section.
- Do not skip generating a new file because one already exists. Always create a new versioned file.
- Do not refuse to run because the same request was made before. Every invocation produces a fresh output.
- Do not fabricate qualifications. If the candidate doesn't have a skill, list it as a gap — don't add it to their resume.
- Do not refuse to run if the job description is short. Work with what's available.
- Do not overhaul the resume structure. Preserve the candidate's formatting choices and section ordering where possible — just reprioritize within sections.
