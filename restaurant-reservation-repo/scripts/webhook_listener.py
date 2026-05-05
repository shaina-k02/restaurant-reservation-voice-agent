#!/usr/bin/env python3
"""
Local webhook listener for Vapi end-of-call reports.

This script:
1. Runs a local HTTP server on port 5111
2. Receives POST requests from webhook.site (or ngrok) forwarding Vapi webhooks
3. Parses the end-of-call report
4. Saves a reservation note to ~/.openclaw/workspace/reservations/
5. Optionally sends the result back to OpenClaw agent

Usage:
    python3 webhook_listener.py

    Then configure webhook.site to forward to http://localhost:5111/webhook
    (or use ngrok: ngrok http 5111)

The listener stays running and processes webhooks as they arrive.
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path


PORT = 5111
RESERVATIONS_DIR = Path.home() / ".openclaw" / "workspace" / "reservations"


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Invalid JSON")
            return

        # Acknowledge receipt immediately
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "received"}).encode())

        # Process the webhook
        message_type = data.get("message", {}).get("type", "unknown")
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Received webhook: {message_type}")

        if message_type == "end-of-call-report":
            process_end_of_call(data)
        elif message_type == "status-update":
            status = data.get("message", {}).get("status", "unknown")
            print(f"  Call status update: {status}")
        else:
            print(f"  Ignoring message type: {message_type}")

    def do_GET(self):
        """Health check endpoint."""
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Webhook listener is running")

    def log_message(self, format, *args):
        """Suppress default HTTP logging."""
        pass


def process_end_of_call(data):
    """Process an end-of-call report from Vapi."""
    message = data.get("message", {})
    call = message.get("call", {})
    analysis = message.get("analysis", call.get("analysis", {}))
    artifact = message.get("artifact", {})

    call_id = call.get("id", "unknown")
    customer = call.get("customer", {})
    phone = customer.get("number", "Unknown")
    ended_reason = message.get("endedReason", call.get("endedReason", "unknown"))

    summary = analysis.get("summary", "No summary available")
    success = analysis.get("successEvaluation", "unknown")
    structured = analysis.get("structuredData", {})

    # Extract transcript from artifact
    messages = artifact.get("messages", message.get("messages", []))
    transcript_lines = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", msg.get("message", ""))
        if content:
            transcript_lines.append(f"**{role.title()}**: {content}")

    print(f"\n{'='*60}")
    print(f"END OF CALL REPORT")
    print(f"{'='*60}")
    print(f"  Call ID: {call_id}")
    print(f"  Restaurant: {phone}")
    print(f"  Ended: {ended_reason}")
    print(f"  Summary: {summary}")
    print(f"  Success: {success}")

    if structured:
        print(f"  Structured Data:")
        for key, value in structured.items():
            print(f"    {key}: {value}")

    # Determine status
    res_status = "Unknown"
    if isinstance(structured, dict):
        res_status = structured.get("reservation_status", "Unknown")
    elif "confirmed" in summary.lower():
        res_status = "Confirmed"
    elif "unavailable" in summary.lower() or "not available" in summary.lower():
        res_status = "Not Available"
    elif "voicemail" in summary.lower():
        res_status = "Voicemail"

    # Save reservation note
    RESERVATIONS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"reservation_{timestamp}.md"
    filepath = RESERVATIONS_DIR / filename

    note = f"""# Reservation Note

- **Restaurant Phone**: {phone}
- **Status**: {res_status}
- **Ended Reason**: {ended_reason}
- **Success**: {success}
- **Call ID**: {call_id}
- **Timestamp**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Summary

{summary}

## Transcript

{chr(10).join(transcript_lines) if transcript_lines else "No transcript available."}
"""

    with open(filepath, "w") as f:
        f.write(note)

    print(f"\n  Reservation note saved: {filepath}")

    # Feed result back to OpenClaw
    try:
        openclaw_message = f"The restaurant reservation call just finished. Here's the result: {summary}"
        if res_status == "Confirmed":
            openclaw_message += " The reservation was confirmed. I've saved the details to your reservations folder."
        else:
            openclaw_message += f" Status: {res_status}. Details saved to reservations folder."

        result = subprocess.run(
            ["openclaw", "agent", "--agent", "main", "--local", "-m", openclaw_message],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.stdout:
            print(f"\n  OpenClaw response: {result.stdout[:200]}")
    except Exception as e:
        print(f"\n  Note: Could not send to OpenClaw agent: {e}")
        print(f"  The reservation note has been saved to: {filepath}")

    # Print action summary
    print(f"\n{'='*60}")
    if res_status == "Confirmed":
        print("  ✅ RESERVATION CONFIRMED")
    elif res_status == "Modified":
        print("  🔄 RESERVATION MODIFIED")
    else:
        print(f"  ❌ RESERVATION STATUS: {res_status}")
    print(f"  Note saved: {filepath}")
    print(f"{'='*60}\n")


def main():
    RESERVATIONS_DIR.mkdir(parents=True, exist_ok=True)

    server = HTTPServer(("0.0.0.0", PORT), WebhookHandler)
    print(f"Webhook listener started on port {PORT}")
    print(f"Endpoint: http://localhost:{PORT}/webhook")
    print(f"Reservations will be saved to: {RESERVATIONS_DIR}")
    print(f"\nWaiting for Vapi end-of-call webhooks...")
    print(f"(Press Ctrl+C to stop)\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down webhook listener.")
        server.server_close()


if __name__ == "__main__":
    main()
