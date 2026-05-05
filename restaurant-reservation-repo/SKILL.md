---
name: restaurant-reservation
description: >
  Make a restaurant reservation via an AI voice agent phone call. Use this skill whenever the user
  wants to book, reserve, or make a reservation at a restaurant by phone. Triggers include: "make a
  reservation at", "book a table at", "call the restaurant", "reserve a table", or any request to
  have an AI agent call a restaurant to book a table. The user provides a restaurant phone number,
  desired date/time, party size, and name. The skill uses Vapi to place an outbound call, and after
  the call completes, processes the result and saves a reservation confirmation or failure note.
---

# Restaurant Reservation Voice Agent

Place an outbound phone call to a restaurant using a Vapi voice agent to make a reservation
on behalf of the user. After the call, process the webhook summary and take action.

## When this skill activates

The user wants to make a restaurant reservation by phone. They should provide:

1. **Restaurant phone number** (required)
2. **Date and time** for the reservation (required)
3. **Party size** (required)
4. **Name** for the reservation (required)
5. **Special requests** (optional — e.g., outdoor seating, high chair, allergies)

If any required info is missing, ask for it before placing the call.

## Prerequisites

The following environment variables must be set:

- `VAPI_API_KEY` — your Vapi private API key (from dashboard.vapi.ai)
- `VAPI_PHONE_NUMBER_ID` — the ID of your Vapi phone number (from Phone Numbers in dashboard)

The webhook handler script must be running locally to receive the end-of-call report.

## Workflow

### Step 1: Collect reservation details

Gather all required information from the user:
- Restaurant phone number (US format, e.g., +1XXXXXXXXXX)
- Date and time
- Party size
- Name for the reservation
- Any special requests

Confirm the details with the user before placing the call.

### Step 2: Place the outbound call

Run the outbound call script:

```bash
python3 ~/.openclaw/workspace/skills/restaurant-reservation/scripts/make_call.py \
  --phone "+1XXXXXXXXXX" \
  --date "Friday March 28 at 7pm" \
  --party-size 4 \
  --name "Shaina Khan" \
  --special "outdoor seating"
```

This script:
1. Builds a transient Vapi assistant with the reservation details baked into the system prompt
2. Calls the Vapi `/call` API to initiate an outbound call from your Vapi number
3. Returns the call ID

Tell the user: "I've placed the call to the restaurant. The AI agent is speaking with them now.
I'll let you know the outcome once the call finishes."

### Step 3: Wait for the webhook and process the result

The webhook handler (`scripts/webhook_listener.py`) runs as a local server and receives
the end-of-call report from Vapi (relayed via webhook.site or ngrok).

Alternatively, you can poll for the call result:

```bash
python3 ~/.openclaw/workspace/skills/restaurant-reservation/scripts/check_call.py --call-id <CALL_ID>
```

This fetches the call details from Vapi's API including the transcript and summary.

### Step 4: Process the outcome and take action

Once the call result is available, the skill:

1. **Parses the conversation summary** — was the reservation confirmed, modified, or denied?
2. **Saves a reservation note** to `~/.openclaw/workspace/reservations/` as a markdown file:

```markdown
# Reservation Confirmation

- **Restaurant**: <name or number>
- **Date/Time**: <confirmed date and time>
- **Party Size**: <number>
- **Name**: <reservation name>
- **Status**: Confirmed / Modified / Not Available
- **Notes**: <any details from the call>
- **Call ID**: <vapi call id>
- **Timestamp**: <when the call was made>
```

3. **Adds a calendar reminder** (if OpenClaw has calendar access) for the reservation time
4. **Reports back to the user** with the outcome

### Step 5: Report to the user

Summarize the call result:

- If confirmed: "Your reservation is confirmed at [restaurant] for [date/time], party of [N], under [name]."
- If modified: "The restaurant couldn't do [original time], but they booked you for [new time] instead."
- If unavailable: "Unfortunately, the restaurant [doesn't take reservations / is fully booked]. [Suggest alternatives if mentioned]."

## Important constraints

- Only place calls to US phone numbers (Vapi free numbers are US-only).
- Always confirm details with the user before placing the call.
- The Vapi agent speaks naturally and politely — it's calling a real restaurant.
- Do not call the same number more than once for the same reservation attempt.
