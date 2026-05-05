#!/usr/bin/env python3
"""
Eval runner for the resume-tailor skill.

Usage:
    python scripts/run_evals.py                    # Run all evals
    python scripts/run_evals.py --eval-id 1        # Run a specific eval
    python scripts/run_evals.py --eval-id 1 2      # Run specific evals
    python scripts/run_evals.py --list              # List all eval cases

This script:
1. Reads evals/evals.json
2. For each eval case, runs the skill via `openclaw agent`
3. Checks assertions against the output
4. Produces a grading report in the workspace directory

Assertions are graded by a combination of:
- Deterministic file-system checks (file exists, file not modified, etc.)
- Content checks (searching for expected sections in output)
"""

import argparse
import json
import os
import subprocess
import sys
import time
import shutil
from datetime import datetime
from pathlib import Path


SKILL_DIR = Path(__file__).parent.parent
EVALS_FILE = SKILL_DIR / "evals" / "evals.json"
WORKSPACE_DIR = SKILL_DIR.parent / "resume-tailor-workspace"


def load_evals():
    """Load eval cases from evals.json."""
    with open(EVALS_FILE) as f:
        return json.load(f)


def list_evals(evals_data):
    """Print all eval cases."""
    print(f"\nSkill: {evals_data['skill_name']}")
    print(f"Total evals: {len(evals_data['evals'])}\n")
    for ev in evals_data["evals"]:
        prompt_preview = ev["prompt"][:80] + "..." if len(ev["prompt"]) > 80 else ev["prompt"]
        print(f"  [{ev['id']}] {prompt_preview}")
        print(f"      Files: {ev.get('files', [])}")
        print(f"      Assertions: {len(ev.get('assertions', []))}")
        print()


def run_single_eval(eval_case, iteration_dir, skill_path):
    """Run a single eval case and return results."""
    eval_id = eval_case["id"]
    eval_name = f"eval-{eval_id}"
    eval_dir = iteration_dir / eval_name / "with_skill"
    output_dir = eval_dir / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Running eval {eval_id}: {eval_case['prompt'][:60]}...")
    print(f"{'='*60}")

    # Copy input files to a temp working directory
    work_dir = iteration_dir / eval_name / "workdir"
    work_dir.mkdir(parents=True, exist_ok=True)

    input_files = eval_case.get("files", [])
    for f in input_files:
        src = SKILL_DIR / f
        if src.exists():
            shutil.copy2(src, work_dir / src.name)
            print(f"  Copied input file: {src.name}")

    # Record files before the run (to detect new files)
    files_before = set(work_dir.iterdir()) if work_dir.exists() else set()

    # --- Preconditions for specific evals ---
    # Eval 7 tests versioning: create a fake v1 so the agent should generate v2
    if eval_id == 7:
        tailored_dir = Path.home() / "Desktop" / "tailored_resumes"
        tailored_dir.mkdir(parents=True, exist_ok=True)
        fake_v1 = tailored_dir / "tailored_resume_stripe_data_engineer_v1.pdf"
        if not fake_v1.exists():
            fake_v1.write_text("placeholder v1")
            print(f"  Created precondition: {fake_v1}")

    # Build the prompt that includes skill context
    prompt = eval_case["prompt"]
    if input_files:
        file_names = [Path(f).name for f in input_files]
        prompt += f"\n\nThe files are located in {work_dir}. Files present: {', '.join(file_names)}"
    prompt += f"\n\nSave any output files to {output_dir}"

    # Run via openclaw agent
    start_time = time.time()
    try:
        result = subprocess.run(
            [
                "openclaw", "agent",
                "--agent", "main",
                "--local",
                "-m", prompt,
            ],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(work_dir),
        )
        duration_ms = int((time.time() - start_time) * 1000)
        agent_output = result.stdout + result.stderr
        success = result.returncode == 0
    except subprocess.TimeoutExpired:
        duration_ms = 300000
        agent_output = "ERROR: Agent timed out after 300 seconds"
        success = False
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        agent_output = f"ERROR: {str(e)}"
        success = False

    # Save agent output
    with open(eval_dir / "agent_output.txt", "w") as f:
        f.write(agent_output)

    # Save timing
    timing = {"duration_ms": duration_ms, "timestamp": datetime.now().isoformat()}
    with open(eval_dir / "timing.json", "w") as f:
        json.dump(timing, f, indent=2)

    # Detect new files created
    files_after = set(work_dir.iterdir()) if work_dir.exists() else set()
    new_files = files_after - files_before
    output_files_created = list(output_dir.iterdir()) if output_dir.exists() else []

    # Also check workdir for new files and copy them to outputs
    for nf in new_files:
        if nf.is_file():
            shutil.copy2(nf, output_dir / nf.name)
            output_files_created.append(output_dir / nf.name)

    # Grade assertions
    assertions = eval_case.get("assertions", [])
    grading_results = grade_assertions(
        assertions, agent_output, output_files_created,
        input_files, eval_case, output_dir, work_dir
    )

    # Save grading
    passed = sum(1 for r in grading_results if r["passed"])
    total = len(grading_results)
    grading = {
        "assertion_results": grading_results,
        "summary": {
            "passed": passed,
            "failed": total - passed,
            "total": total,
            "pass_rate": round(passed / total, 2) if total > 0 else 0,
        },
    }
    with open(eval_dir / "grading.json", "w") as f:
        json.dump(grading, f, indent=2)

    # Save eval metadata
    metadata = {
        "eval_id": eval_id,
        "eval_name": eval_name,
        "prompt": eval_case["prompt"],
        "assertions": assertions,
        "success": success,
    }
    with open(eval_dir.parent / "eval_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    return grading


def grade_assertions(assertions, agent_output, output_files, input_files, eval_case, output_dir, work_dir):
    """Grade each assertion against the actual outputs."""
    results = []
    output_lower = agent_output.lower()
    output_file_names = [f.name.lower() for f in output_files if isinstance(f, Path)]
    input_file_names = [Path(f).name.lower() for f in input_files]

    for assertion in assertions:
        a_lower = assertion.lower()
        passed = False
        evidence = ""

        # --- File creation checks ---
        if "new file was created" in a_lower or "new file" in a_lower and "created" in a_lower:
            new_files = [f for f in output_file_names if f not in input_file_names]
            passed = len(new_files) > 0
            evidence = f"New files found: {new_files}" if passed else "No new files detected in output directory"

        elif "output filename contains" in a_lower and ("company" in a_lower or "job title" in a_lower):
            new_files = [f for f in output_file_names if f not in input_file_names]
            # Check if any new file has a descriptive name (not just generic)
            passed = any("tailored" in f or "resume" in f for f in new_files)
            evidence = f"Output files: {new_files}" if new_files else "No output files found"

        elif "original" in a_lower and "not modified" in a_lower:
            # Check that input files still exist unmodified in workdir
            passed = True  # Default true unless we detect modification
            for inp in input_files:
                orig = SKILL_DIR / inp
                work_copy = work_dir / Path(inp).name
                if orig.exists() and work_copy.exists():
                    if orig.stat().st_size != work_copy.stat().st_size:
                        passed = False
                        evidence = f"File {Path(inp).name} was modified (size changed)"
                        break
            if passed:
                evidence = "Original input files remain unmodified"

        elif "docx" in a_lower and "created" in a_lower:
            passed = any(f.endswith(".docx") for f in output_file_names if f not in input_file_names)
            evidence = f"DOCX files in output: {[f for f in output_file_names if f.endswith('.docx')]}"

        elif ".tex" in a_lower and "created" in a_lower:
            passed = any(f.endswith(".tex") for f in output_file_names if f not in input_file_names)
            evidence = f"TEX files in output: {[f for f in output_file_names if f.endswith('.tex')]}"

        # --- Content NOT in chat checks ---
        elif "resume content" in a_lower and "not" in a_lower and ("chat" in a_lower or "returned" in a_lower or "dumped" in a_lower):
            # Detect if the agent dumped the full resume into chat.
            # We look for resume-specific formatting patterns, not just keywords
            # like "experience" or "skills" which naturally appear in analysis.
            import re
            dump_signals = 0
            # Signal 1: Multiple job entries with company names and date ranges
            date_range_pattern = r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|january|february|march|april|june|july|august|september|october|november|december)\s+\d{4}\s*[-–—]\s*(present|\d{4})'
            date_matches = re.findall(date_range_pattern, output_lower)
            if len(date_matches) >= 2:
                dump_signals += 1
            # Signal 2: Contact info patterns (email + phone together)
            has_email = bool(re.search(r'[\w.-]+@[\w.-]+\.\w+', agent_output))
            has_phone = bool(re.search(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', agent_output))
            if has_email and has_phone:
                dump_signals += 1
            # Signal 3: Long comma-separated skill lists (8+ items)
            skill_list_match = re.findall(r'(?:[\w\+\#\.]+(?:\s*,\s*)){7,}[\w\+\#\.]+', agent_output)
            if skill_list_match:
                dump_signals += 1
            # Signal 4: GPA mention with degree info
            has_gpa = bool(re.search(r'gpa[:\s]*\d+\.\d+', output_lower))
            has_degree = bool(re.search(r'\b(b\.?s\.?|m\.?s\.?|bachelor|master)\b', output_lower))
            if has_gpa and has_degree:
                dump_signals += 1
            # Need 3+ signals to conclude the resume was dumped
            passed = dump_signals < 3
            evidence = f"Resume dump signals: {dump_signals}/4 (date ranges: {len(date_matches)}, contact info: {has_email and has_phone}, skill lists: {bool(skill_list_match)}, edu details: {has_gpa and has_degree})"

        # --- Analysis section checks ---
        elif "strengths section" in a_lower or "strengths" in a_lower and "section" in a_lower:
            passed = "strength" in output_lower
            evidence = "Found 'Strengths' in output" if passed else "No 'Strengths' section found"

        elif "gaps section" in a_lower or "gaps" in a_lower and "section" in a_lower:
            passed = "gap" in output_lower
            evidence = "Found 'Gaps' in output" if passed else "No 'Gaps' section found"

        elif "suggested improvements" in a_lower or "improvements section" in a_lower:
            passed = "improvement" in output_lower or "suggest" in output_lower
            evidence = "Found improvements section in output" if passed else "No improvements section found"

        elif "at least" in a_lower and "bullet" in a_lower:
            # Count bullet-like items (lines starting with - or *)
            import re
            bullet_count = len(re.findall(r"^[\s]*[-*•]", agent_output, re.MULTILINE))
            min_bullets = 1
            for word in a_lower.split():
                if word.isdigit():
                    min_bullets = int(word)
                    break
            passed = bullet_count >= min_bullets
            evidence = f"Found {bullet_count} bullet points (needed {min_bullets})"

        # --- Missing input checks ---
        elif "asks for" in a_lower and ("job description" in a_lower or "job url" in a_lower or "job" in a_lower):
            passed = any(kw in output_lower for kw in ["job description", "job posting", "job link", "job url", "which job", "what role", "what position"])
            evidence = "Agent asked for job info" if passed else "Agent did not ask for job details"

        elif "asks for" in a_lower and "resume" in a_lower:
            passed = any(kw in output_lower for kw in ["resume", "upload", "attach", "provide your", "share your"])
            evidence = "Agent asked for resume" if passed else "Agent did not ask for resume"

        elif "not proceed" in a_lower or "does not proceed" in a_lower:
            passed = not any(f for f in output_file_names if f not in input_file_names)
            evidence = "No premature output files created" if passed else "Files were created prematurely"

        elif "no output file" in a_lower and "prematurely" in a_lower:
            new_files = [f for f in output_file_names if f not in input_file_names]
            passed = len(new_files) == 0
            evidence = f"New files: {new_files}" if new_files else "No premature files created"

        # --- Quality checks ---
        elif "fabricated" in a_lower or "not in the original" in a_lower:
            passed = True
            evidence = "MANUAL_REVIEW: Requires human verification that no skills were fabricated"

        elif "keywords from the job description" in a_lower:
            passed = True
            evidence = "MANUAL_REVIEW: Requires comparison of tailored resume against job keywords"

        elif "specific" in a_lower and ("skills" in a_lower or "job requirements" in a_lower):
            passed = True
            evidence = "MANUAL_REVIEW: Requires human check for specificity"

        # --- Forbidden section checks ---
        elif "not contain" in a_lower and "key changes" in a_lower:
            has_key_changes = any(kw in output_lower for kw in [
                "key changes", "changes made", "changes summary",
                "what changed", "resume changes", "key changes from"
            ])
            passed = not has_key_changes
            evidence = "No forbidden 'Key Changes' section found" if passed else "Found a 'Key Changes' section in output"

        # --- Version number checks ---
        elif "version number" in a_lower and ("filename" in a_lower or "output" in a_lower):
            import re
            # Check both output_dir and ~/Desktop/tailored_resumes/
            all_output_files = list(output_file_names)
            desktop_dir = Path.home() / "Desktop" / "tailored_resumes"
            if desktop_dir.exists():
                all_output_files.extend([f.name.lower() for f in desktop_dir.iterdir() if f.is_file()])
            new_files = [f for f in all_output_files if f not in input_file_names]
            version_pattern = re.compile(r'_v\d+')
            passed = any(version_pattern.search(f) for f in new_files)
            versioned = [f for f in new_files if version_pattern.search(f)]
            evidence = f"Files with version numbers: {versioned}" if passed else f"No version numbers found in: {new_files}"

        elif "version number higher than v1" in a_lower:
            import re
            # Check both output_dir and ~/Desktop/tailored_resumes/
            all_output_files = list(output_file_names)
            desktop_dir = Path.home() / "Desktop" / "tailored_resumes"
            if desktop_dir.exists():
                all_output_files.extend([f.name.lower() for f in desktop_dir.iterdir() if f.is_file()])
            new_files = [f for f in all_output_files if f not in input_file_names]
            v2_plus = [f for f in new_files if re.search(r'_v([2-9]|\d{2,})', f)]
            passed = len(v2_plus) > 0
            evidence = f"Files with v2+: {v2_plus}" if passed else f"No v2+ files found in: {new_files}"

        # --- Refuse / skip checks ---
        elif "did not refuse" in a_lower or "not refuse" in a_lower:
            refuse_signals = ["i can't", "i cannot", "need more details", "please provide more",
                              "could you provide", "need a more detailed", "already tailored",
                              "nothing new to do", "same request"]
            refused = any(sig in output_lower for sig in refuse_signals)
            passed = not refused
            evidence = "Agent did not refuse" if passed else "Agent appeared to refuse or skip the task"

        elif "not skip" in a_lower or "not say the resume was already" in a_lower:
            skip_signals = ["already exists", "already tailored", "already generated",
                            "nothing new", "same request", "no changes"]
            skipped = any(sig in output_lower for sig in skip_signals)
            passed = not skipped
            evidence = "Agent did not skip" if passed else "Agent skipped because previous version exists"

        # --- Specific gap checks ---
        elif "mentions" in a_lower and ("c#" in a_lower or ".net" in a_lower or "azure" in a_lower):
            passed = any(kw in output_lower for kw in ["c#", ".net", "azure", "csharp"])
            evidence = "Found C#/.NET/Azure mentioned as gap" if passed else "C#/.NET/Azure not mentioned in analysis"

        elif "valid latex" in a_lower or ("\\begin{document}" in a_lower and "\\end{document}" in a_lower):
            for f in output_files:
                if str(f).endswith(".tex") and Path(f).exists():
                    content = Path(f).read_text()
                    passed = "\\begin{document}" in content and "\\end{document}" in content
                    evidence = "LaTeX file has document structure" if passed else "Missing basic LaTeX structure"
                    break
            else:
                passed = False
                evidence = "No .tex file found to validate"

        elif "preserves" in a_lower and "latex" in a_lower:
            passed = True
            evidence = "MANUAL_REVIEW: Requires human verification of LaTeX structure preservation"

        elif "generic" in a_lower and "advice" in a_lower:
            passed = True
            evidence = "MANUAL_REVIEW: Requires human check that advice is role-specific"

        else:
            # Unrecognized assertion — flag for manual review
            passed = True
            evidence = f"MANUAL_REVIEW: Assertion not auto-gradeable: {assertion}"

        results.append({
            "text": assertion,
            "passed": passed,
            "evidence": evidence,
        })

    return results


def print_summary(all_results):
    """Print a summary of all eval results."""
    print(f"\n{'='*60}")
    print("EVAL SUMMARY")
    print(f"{'='*60}\n")

    total_passed = 0
    total_assertions = 0
    manual_review_count = 0

    for eval_id, grading in all_results.items():
        summary = grading["summary"]
        total_passed += summary["passed"]
        total_assertions += summary["total"]

        status = "PASS" if summary["pass_rate"] == 1.0 else "PARTIAL" if summary["pass_rate"] > 0 else "FAIL"
        icon = "✅" if status == "PASS" else "⚠️" if status == "PARTIAL" else "❌"
        print(f"{icon} Eval {eval_id}: {summary['passed']}/{summary['total']} assertions passed ({summary['pass_rate']*100:.0f}%)")

        for r in grading["assertion_results"]:
            if not r["passed"]:
                print(f"     ❌ {r['text']}")
                print(f"        Evidence: {r['evidence']}")
            elif "MANUAL_REVIEW" in r["evidence"]:
                manual_review_count += 1
                print(f"     👁️ {r['text']} (needs manual review)")

    overall_rate = round(total_passed / total_assertions * 100, 1) if total_assertions > 0 else 0
    print(f"\nOverall: {total_passed}/{total_assertions} ({overall_rate}%)")
    if manual_review_count > 0:
        print(f"Manual review needed: {manual_review_count} assertions")
    print()


def main():
    parser = argparse.ArgumentParser(description="Run evals for resume-tailor skill")
    parser.add_argument("--eval-id", type=int, nargs="*", help="Specific eval IDs to run")
    parser.add_argument("--list", action="store_true", help="List all eval cases")
    parser.add_argument("--iteration", type=int, default=None, help="Iteration number (auto-increments by default)")
    args = parser.parse_args()

    evals_data = load_evals()

    if args.list:
        list_evals(evals_data)
        return

    # Determine iteration number
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    if args.iteration:
        iteration_num = args.iteration
    else:
        existing = [d for d in WORKSPACE_DIR.iterdir() if d.is_dir() and d.name.startswith("iteration-")]
        iteration_num = len(existing) + 1

    iteration_dir = WORKSPACE_DIR / f"iteration-{iteration_num}"
    iteration_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nRunning evals — iteration {iteration_num}")
    print(f"Results will be saved to: {iteration_dir}\n")

    # Filter evals if specific IDs requested
    evals_to_run = evals_data["evals"]
    if args.eval_id:
        evals_to_run = [e for e in evals_to_run if e["id"] in args.eval_id]
        if not evals_to_run:
            print(f"No evals found with IDs: {args.eval_id}")
            return

    # Run evals
    all_results = {}
    for eval_case in evals_to_run:
        grading = run_single_eval(eval_case, iteration_dir, SKILL_DIR)
        all_results[eval_case["id"]] = grading

    # Print summary
    print_summary(all_results)

    # Save aggregate benchmark
    benchmark = {
        "iteration": iteration_num,
        "timestamp": datetime.now().isoformat(),
        "skill_name": evals_data["skill_name"],
        "results": {str(k): v for k, v in all_results.items()},
    }
    with open(iteration_dir / "benchmark.json", "w") as f:
        json.dump(benchmark, f, indent=2)

    print(f"Benchmark saved to: {iteration_dir / 'benchmark.json'}")


if __name__ == "__main__":
    main()
