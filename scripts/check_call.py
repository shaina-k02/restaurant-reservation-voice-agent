#!/usr/bin/env python3
"""
Check the status and results of a Vapi call.

Usage:
    python3 check_call.py --call-id <CALL_ID>

Requires:
    export VAPI_API_KEY="your-private-key"
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path


VAPI_API_URL = "https://api.vapi.ai/call"
RESERVATIONS_DIR = Path.home() / ".openclaw" / "workspace" / "reservations"


def check_call(call_id):
    api_key = os.environ.get("VAPI_API_KEY")
    if not api_key:
        print("ERROR: VAPI_API_KEY environment variable not set.")
        sys.exit(1)

    url = f"{VAPI_API_URL}/{call_id}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    req = urllib.request.Request(url, headers=headers, method="GET")

    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"ERROR: Vapi API returned {e.code}")
        print(f"Response: {error_body}")
        sys.exit(1)


def save_reservation_note(call_data):
    """Save a reservation note based on call results."""
    RESERVATIONS_DIR.mkdir(parents=True, exist_ok=True)

    analysis = call_data.get("analysis", {})
    summary = analysis.get("summary", "No summary available")
    success = analysis.get("successEvaluation", "unknown")
    structured = analysis.get("structuredData", {})

    customer = call_data.get("customer", {})
    phone = customer.get("number", "Unknown")

    status = call_data.get("status", "unknown")
    ended_reason = call_data.get("endedReason", "unknown")
    duration = call_data.get("costs", [{}])

    # Extract transcript
    messages = call_data.get("messages", [])
    transcript_lines = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", msg.get("message", ""))
        if content:
            transcript_lines.append(f"**{role.title()}**: {content}")

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"reservation_{timestamp}.md"

    # Determine reservation status from analysis
    res_status = "Unknown"
    if isinstance(structured, dict):
        res_status = structured.get("reservation_status", "Unknown")
    elif "confirmed" in summary.lower():
        res_status = "Confirmed"
    elif "unavailable" in summary.lower() or "not available" in summary.lower():
        res_status = "Not Available"
    elif "voicemail" in summary.lower():
        res_status = "Voicemail"

    note = f"""# Reservation Note

- **Restaurant Phone**: {phone}
- **Status**: {res_status}
- **Call Status**: {status}
- **Ended Reason**: {ended_reason}
- **Success**: {success}
- **Call ID**: {call_data.get('id', 'unknown')}
- **Timestamp**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Summary

{summary}

## Transcript

{chr(10).join(transcript_lines) if transcript_lines else "No transcript available."}
"""

    filepath = RESERVATIONS_DIR / filename
    with open(filepath, "w") as f:
        f.write(note)

    print(f"\nReservation note saved to: {filepath}")
    return filepath


def display_result(call_data):
    """Display call results in a readable format."""
    status = call_data.get("status", "unknown")
    ended_reason = call_data.get("endedReason", "unknown")
    analysis = call_data.get("analysis", {})

    print(f"\n{'='*60}")
    print(f"CALL RESULT")
    print(f"{'='*60}")
    print(f"  Call ID: {call_data.get('id', 'unknown')}")
    print(f"  Status: {status}")
    print(f"  Ended Reason: {ended_reason}")

    if status == "ended":
        summary = analysis.get("summary", "No summary available")
        success = analysis.get("successEvaluation", "Not evaluated")

        print(f"\n  Summary: {summary}")
        print(f"  Success: {success}")

        structured = analysis.get("structuredData", {})
        if structured:
            print(f"\n  Structured Data:")
            for key, value in structured.items():
                print(f"    {key}: {value}")

        # Save the note
        save_reservation_note(call_data)

        # Feed back to OpenClaw
        print(f"\n{'='*60}")
        print("OPENCLAW ACTION")
        print(f"{'='*60}")
        if "confirmed" in summary.lower() or (isinstance(structured, dict) and structured.get("reservation_status") == "confirmed"):
            print("  ✅ Reservation CONFIRMED — note saved to reservations folder.")
            print("  The reservation details have been logged for your records.")
        else:
            print("  ❌ Reservation NOT confirmed — see summary above for details.")
            print("  Note saved with call transcript for reference.")

    elif status in ("queued", "ringing", "in-progress"):
        print(f"\n  Call is still {status}. Try again in a moment:")
        print(f"  python3 check_call.py --call-id {call_data.get('id')}")

    else:
        print(f"\n  Unexpected status. Full response:")
        print(json.dumps(call_data, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Check Vapi call status and results")
    parser.add_argument("--call-id", required=True, help="The Vapi call ID to check")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument("--save", action="store_true", help="Save reservation note even if call not ended")

    args = parser.parse_args()

    print(f"Checking call {args.call_id}...")
    call_data = check_call(args.call_id)

    if args.json:
        print(json.dumps(call_data, indent=2))
    else:
        display_result(call_data)


if __name__ == "__main__":
    main()
