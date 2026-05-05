#!/usr/bin/env python3
"""
Make an outbound restaurant reservation call via Vapi.

Usage:
    python3 make_call.py \
        --phone "+12125551234" \
        --date "Friday March 28 at 7pm" \
        --party-size 4 \
        --name "Shaina Khan" \
        --special "outdoor seating if possible"

Requires:
    export VAPI_API_KEY="your-private-key"
    export VAPI_PHONE_NUMBER_ID="3411e9ad-426f-4bac-8c9b-65812c2ffc76"
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error


VAPI_API_URL = "https://api.vapi.ai/call"


def make_reservation_call(phone, date, party_size, name, special_requests=""):
    api_key = os.environ.get("VAPI_API_KEY")
    phone_number_id = os.environ.get("VAPI_PHONE_NUMBER_ID", "3411e9ad-426f-4bac-8c9b-65812c2ffc76")

    if not api_key:
        print("ERROR: VAPI_API_KEY environment variable not set.")
        print("Run: export VAPI_API_KEY='your-private-key'")
        sys.exit(1)

    # Build the system prompt with reservation details
    system_prompt = f"""You are a polite and professional reservation assistant calling a restaurant on behalf of a customer. Your goal is to make a restaurant reservation with these details:

- Date and time: {date}
- Party size: {party_size}
- Name for the reservation: {name}
{f'- Special requests: {special_requests}' if special_requests else ''}

Guidelines:
- Be courteous and natural — you are calling a real restaurant, speak like a friendly human.
- Start by saying: "Hi, I'd like to make a reservation please."
- Provide the details when asked: date/time, party size, and name.
- If the requested time is not available, ask what times ARE available and try to find the closest alternative. Accept the closest available time if it's within 1 hour of the original request.
- If the restaurant does not take reservations, politely thank them and end the call.
- Confirm all details before ending the call: date, time, party size, and name.
- End with: "Thank you so much, we appreciate it. Goodbye."
- Keep the conversation focused — do not go off topic.
- If you reach a voicemail or automated system, say "I'll try calling back later" and end the call."""

    # Build the API payload with a transient assistant
    payload = {
        "phoneNumberId": phone_number_id,
        "customer": {
            "number": phone
        },
        "assistant": {
            "name": "Restaurant Reservation Agent",
            "firstMessage": "Hi, I'd like to make a reservation please.",
            "model": {
                "provider": "openai",
                "model": "gpt-4o",
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt
                    }
                ]
            },
            "voice": {
                "provider": "11labs",
                "voiceId": "21m00Tcm4TlvDq8ikWAM"
            },
            "endCallMessage": "Thank you, goodbye!",
            "maxDurationSeconds": 120,
            "serverMessages": [
                "end-of-call-report",
                "status-update",
                "conversation-update"
            ],
            "analysisPlan": {
                "summaryPrompt": "Summarize this restaurant reservation call. Include: whether the reservation was confirmed, the final date/time, party size, name, and any special notes. If the reservation was not made, explain why.",
                "structuredDataPrompt": "Extract: reservation_status (confirmed/modified/unavailable/voicemail), confirmed_date, confirmed_time, party_size, name, restaurant_notes",
                "successEvaluationPrompt": "Was the reservation successfully made? Answer yes or no with a brief reason."
            }
        }
    }

    # Make the API call
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    req = urllib.request.Request(
        VAPI_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))
            call_id = result.get("id", "unknown")
            status = result.get("status", "unknown")

            print(f"Call initiated successfully!")
            print(f"  Call ID: {call_id}")
            print(f"  Status: {status}")
            print(f"  Calling: {phone}")
            print(f"  Reservation: {date}, party of {party_size}, under {name}")
            print(f"\nThe AI agent is now calling the restaurant.")
            print(f"Check your webhook.site dashboard for the end-of-call report.")
            print(f"\nTo check call status later:")
            print(f"  python3 check_call.py --call-id {call_id}")

            return result

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"ERROR: Vapi API returned {e.code}")
        print(f"Response: {error_body}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"ERROR: Could not reach Vapi API: {e.reason}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Make a restaurant reservation call via Vapi")
    parser.add_argument("--phone", required=True, help="Restaurant phone number (E.164 format, e.g., +12125551234)")
    parser.add_argument("--date", required=True, help="Desired date and time (e.g., 'Friday March 28 at 7pm')")
    parser.add_argument("--party-size", type=int, required=True, help="Number of people")
    parser.add_argument("--name", required=True, help="Name for the reservation")
    parser.add_argument("--special", default="", help="Special requests (optional)")

    args = parser.parse_args()

    # Ensure phone number is in E.164 format
    phone = args.phone
    if not phone.startswith("+"):
        phone = "+1" + phone.replace("-", "").replace("(", "").replace(")", "").replace(" ", "")

    print(f"Placing reservation call...")
    print(f"  Restaurant: {phone}")
    print(f"  Date/Time: {args.date}")
    print(f"  Party Size: {args.party_size}")
    print(f"  Name: {args.name}")
    if args.special:
        print(f"  Special: {args.special}")
    print()

    make_reservation_call(phone, args.date, args.party_size, args.name, args.special)


if __name__ == "__main__":
    main()
