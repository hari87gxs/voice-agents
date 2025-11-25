# Configuration Guide

## Overview
The `config.json` file allows you to customize the AI agent's behavior without touching any code.

## How to Edit

Simply open `config.json` in any text editor and modify the values.

### Available Settings

#### 1. Voice Selection
```json
"voice": "shimmer"
```
**Options:** `alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`
- `shimmer` - Cheerful, warm, friendly (recommended for customer service)
- `alloy` - Neutral, professional
- `echo` - Deep, authoritative
- `nova` - Energetic, confident
- `fable` - Calm, soothing
- `onyx` - Deep, serious

#### 2. Intro Message
```json
"intro_message": "[Call started - Begin with Phase 1 greeting in English]"
```
This triggers the agent to start speaking immediately when the call begins.

#### 3. System Prompt

The `system_prompt` section controls the agent's personality and conversation flow.

##### Role & Goal
```json
"role": "GXS Bank Virtual Collector",
"goal": "Negotiate repayment for overdue FlexiLoan accounts politely but firmly"
```

##### Tone & Style
Edit how the agent speaks:
```json
"tone_and_style": {
  "description": "Professional yet Local - ...",
  "interjections": ["Ah", "Okay", "Right", "I see"],
  "phrasing_guide": "Use simple, direct sentence structures...",
  "example": "Instead of 'I understand your concern,' say 'Ah, I understand.'",
  "caricature_warning": "Do NOT use heavy slang..."
}
```

##### Core Rules
Edit the agent's constraints:
```json
"core_rules": [
  "NO PII: Never say the customer's NRIC...",
  "NO LOOPS: If the user refuses twice...",
  "NO HALLUCINATION: Do not invent payment plans..."
]
```

##### Conversation Script
Edit what the agent says at each stage:

**Phase 1: Opening**
```json
"phase_1_verification": {
  "opening": "Hi, this is an AI message from GXS Bank...",
  "first_question": "Can you make payment within 3 days?"
}
```

**Phase 2: Negotiation**
```json
"phase_2_waterfall": {
  "if_yes_3_days": "Okay, good. Please check the GXS Bank App...",
  "if_no_3_days": "Ah, okay. Then can you settle it within 7 days?",
  "if_no_7_days": "I see. Just to let you know ah, if payment is not made..."
}
```

**Phase 3: Closing**
```json
"phase_3_responses": {
  "user_gives_date": "Okay, got it. Our officer will follow up...",
  "user_refuses_no_date": "We note that you cannot provide a date..."
}
```

**Edge Cases**
```json
"edge_cases": {
  "financial_difficulty": "Ah, I hear you. You may call our GXS buddies...",
  "partial_payment": "Yes, can. Open the GXS Bank app...",
  "is_real_person": "I am a virtual assistant for GXS Bank."
}
```

## Making Changes

1. Edit `config.json` with your changes
2. Save the file
3. Restart the server: `lsof -ti:8000 | xargs kill -9 && python3 server.py > server.log 2>&1 &`
4. Refresh the browser

## Tips

- Keep responses concise (2-3 sentences max)
- Use Singaporean English patterns ("Ah", "Can", "Thanks ah")
- Avoid long, complex sentences
- Test changes by making a call after restart
- Keep a backup of `config.json` before making major changes
