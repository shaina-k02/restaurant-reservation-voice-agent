# Restaurant Reservation Voice Agent — OpenClaw Skill

An OpenClaw skill that places outbound phone calls to restaurants via [Vapi](https://vapi.ai) to make reservations. After the call, receives a webhook with the conversation summary and feeds it to OpenClaw to send a confirmation email.

## Architecture

```
User → OpenClaw → Vapi API → Outbound Call → Restaurant
                                    ↓
                             (call ends)
                                    ↓
                          Vapi end-of-call webhook
                                    ↓
                          ngrok → localhost:5111
                                    ↓
                   webhook_listener.py → OpenClaw → email
```

## Setup

### Vapi

1. Create an account at [dashboard.vapi.ai](https://dashboard.vapi.ai)
2. Create a free US phone number
3. Create an assistant using the prompt in `vapi_assistant_config.json`
4. Set First Message to: `Hi there! I'd like to make a dinner reservation, please.`
5. Set Organization Settings → Server URL to your webhook endpoint

### Environment

```bash
export VAPI_API_KEY="your-vapi-private-key"
export VAPI_PHONE_NUMBER_ID="your-phone-number-id"
```

### Webhook (ngrok)

```bash
# Terminal 1: start the local listener
python3 scripts/webhook_listener.py

# Terminal 2: expose it publicly
ngrok http 5111
```

Update your Vapi assistant's server URL to the ngrok public URL.

## Usage

### Make a call

```bash
curl -X POST https://api.vapi.ai/call \
  -H "Authorization: Bearer $VAPI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"phoneNumberId":"YOUR_ID","customer":{"number":"+1RESTAURANT"},"assistantId":"YOUR_ID"}'
```

### Check result

```bash
python3 scripts/check_call.py --call-id CALL_ID
```

### Connect to OpenClaw

```bash
openclaw agent --agent main --local -m \
  "A reservation was confirmed for Friday March 28 at 7 PM, party of 4, under Shaina Khan. Send a confirmation email to my email."
```

## Project Structure

```
.
├── SKILL.md                      # Skill definition
├── README.md
├── vapi_assistant_config.json    # Vapi assistant prompt/config
└── scripts/
    ├── make_call.py              # Trigger outbound call
    ├── check_call.py             # Poll for call results
    └── webhook_listener.py       # Local webhook receiver
```

## Prerequisites

- Node.js 22+ and [OpenClaw](https://openclaw.ai) with Anthropic API key
- Python 3.9+
- [Vapi](https://dashboard.vapi.ai) account with free credits
- [ngrok](https://ngrok.com) for webhook tunneling
