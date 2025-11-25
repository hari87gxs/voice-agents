# Newton Deployment Guide

## How to Create and Deploy a New Version for Different Use Cases

This guide explains how to create a new persona/use case (like Newton for science teaching) from the base voice agent platform.

---

## Quick Start: Deploy a New Persona in 5 Steps

### 1. **Create a New Directory**
```bash
# Copy the entire Newton folder as a template
cp -r /Users/hari/Documents/haricode/Newton /Users/hari/Documents/haricode/YourNewApp

cd /Users/hari/Documents/haricode/YourNewApp
```

### 2. **Update config.json - Define Your Persona**

Edit `config.json` to define your new persona's behavior:

```json
{
  "voice": "shimmer",  // Options: shimmer, alloy, echo, fable, onyx, cedar, ash, ballad, coral, sage, verse
  "intro_message": "[Call started - Your custom greeting instruction]",
  "system_prompt": {
    "role": "Your Persona Name - Title",
    "goal": "What this persona should accomplish",
    "tone_and_style": {
      "description": "How the persona should speak and behave",
      "interjections": ["Hey", "Wow", "Sure"],
      "phrasing_guide": "Guidelines for how to phrase responses",
      "example": "Example of the persona's speaking style",
      "caricature_warning": "Warnings about what to avoid"
    },
    "core_rules": [
      "Rule 1: What the persona must always do",
      "Rule 2: Another important behavior",
      "Rule 3: Key constraint or guideline"
    ],
    "conversation_script": {
      "phase_1_greeting": {
        "title": "Initial Interaction",
        "opening": "First thing the persona says",
        "wait_instruction": "What to wait for",
        "if_name_given": "Response if user gives name",
        "if_no_name": "Response if user doesn't give name"
      },
      "phase_2_main": {
        "title": "Main Conversation Flow",
        "step_1": "First step in conversation",
        "step_2": "Second step",
        "step_3": "Third step"
      },
      "edge_cases": {
        "title": "Special Situations",
        "scenario_1": "How to handle edge case 1",
        "scenario_2": "How to handle edge case 2"
      }
    },
    "language_enforcement": "Language rules (default English, allow switching, etc.)",
    "intelligence_rules": "How the persona should listen and respond intelligently"
  }
}
```

**Example Use Cases:**
- **Fitness Coach**: Motivational, energetic, tracks workout goals
- **Mental Health Counselor**: Empathetic, calm, active listening
- **Language Tutor**: Patient, corrective, encouraging
- **Job Interview Coach**: Professional, constructive feedback
- **Customer Service Rep**: Polite, solution-oriented, brand-specific

### 3. **Update Frontend Branding**

Edit `index.html` to match your new persona:

```html
<!-- Update the title -->
<title>YourApp 🎯 - Tagline</title>

<!-- Update the header -->
<h1>🎯 YourApp - Your Friendly Helper</h1>
<p>Your custom subtitle here</p>
```

**Customize Colors/Theme:**
```css
/* Change background gradient */
background: linear-gradient(135deg, #YourColor1 0%, #YourColor2 100%);

/* Change header colors */
.header {
    background: linear-gradient(135deg, #YourColor3 0%, #YourColor4 100%);
}

/* Change button colors */
.btn-start {
    background: linear-gradient(135deg, #YourColor5 0%, #YourColor6 100%);
}
```

**Update Branding in client.js:**
```javascript
// Line ~448: Change transcript download header
let content = 'YourApp - Conversation Transcript\n';

// Line ~450: Change role label
const role = item.role === 'user' ? 'YOU' : 'YOUR_PERSONA_NAME';

// Line ~462: Change download filename
a.download = `yourapp-transcript-${Date.now()}.txt`;

// Line ~450: Change display name
const roleLabel = item.role === 'user' ? 'You' : 'YourPersona';
```

### 4. **Update Environment Variables**

Edit `.env` to set a unique port:

```bash
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key-here
AZURE_OPENAI_DEPLOYMENT=gpt-realtime
PORT=8002  # Use a different port for each app
```

### 5. **Build, Push, and Deploy**

```bash
# Set your GCP project
gcloud config set project YOUR_PROJECT_ID

# Build Docker image
docker build --platform=linux/amd64 -t gcr.io/YOUR_PROJECT_ID/your-app-name .

# Push to Google Container Registry
docker push gcr.io/YOUR_PROJECT_ID/your-app-name

# Deploy to Cloud Run
source .env && gcloud run deploy your-app-name \
  --image gcr.io/YOUR_PROJECT_ID/your-app-name \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars AZURE_OPENAI_ENDPOINT=$AZURE_OPENAI_ENDPOINT,AZURE_OPENAI_API_KEY=$AZURE_OPENAI_API_KEY,AZURE_OPENAI_DEPLOYMENT=$AZURE_OPENAI_DEPLOYMENT \
  --port 8000 \
  --memory 512Mi \
  --cpu 1 \
  --timeout 300 \
  --quiet
```

**Your app is now live!** The deployment will output a public URL like:
```
Service URL: https://your-app-name-XXXXXXXXXX.us-central1.run.app
```

---

## Testing Locally Before Deployment

Always test locally first:

```bash
# Start the server
cd /Users/hari/Documents/haricode/YourNewApp
python3 server.py

# Open in browser
# Navigate to http://localhost:8002 (or your chosen port)
```

**Test Checklist:**
- ✅ Voice greeting plays immediately in correct language
- ✅ Persona follows the conversation script
- ✅ Tone and style match expectations
- ✅ Language switching works (if enabled)
- ✅ Transcript displays correctly with persona name
- ✅ Download generates proper filename
- ✅ Branding/colors match your design

---

## Updating an Existing Deployment

If you need to update a deployed app:

```bash
# 1. Make changes to config.json, index.html, or client.js
# 2. Rebuild the Docker image (same tag)
docker build --platform=linux/amd64 -t gcr.io/YOUR_PROJECT_ID/your-app-name .

# 3. Push updated image
docker push gcr.io/YOUR_PROJECT_ID/your-app-name

# 4. Redeploy (Cloud Run will automatically use the new image)
source .env && gcloud run deploy your-app-name \
  --image gcr.io/YOUR_PROJECT_ID/your-app-name \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars AZURE_OPENAI_ENDPOINT=$AZURE_OPENAI_ENDPOINT,AZURE_OPENAI_API_KEY=$AZURE_OPENAI_API_KEY,AZURE_OPENAI_DEPLOYMENT=$AZURE_OPENAI_DEPLOYMENT \
  --port 8000 \
  --memory 512Mi \
  --cpu 1 \
  --timeout 300 \
  --quiet
```

**Note:** Cloud Run creates a new revision and routes 100% of traffic to it automatically.

---

## Architecture Overview

**Files You'll Modify:**
- `config.json` - Persona behavior, conversation flow, rules
- `index.html` - UI branding, colors, title, subtitle
- `client.js` - Transcript labels, download filename, display name
- `.env` - Port number for local testing

**Files You Won't Need to Touch:**
- `server.py` - WebSocket relay (works for all personas)
- `audio-processor.js` - Audio DSP (universal)
- `Dockerfile` - Container setup (universal)
- `requirements.txt` - Python dependencies (universal)

---

## Common Customizations

### 1. **Change Voice Personality**
Available voices (choose in `config.json`):
- `shimmer` - Cheerful, energetic (Newton default)
- `alloy` - Neutral, professional
- `echo` - Calm, soothing
- `fable` - Storytelling, narrative
- `onyx` - Deep, authoritative
- `cedar` - Warm, friendly (ABC Bank default)
- `ash`, `ballad`, `coral`, `sage`, `verse` - Other variations

### 2. **Multi-Language Support**
```json
"language_enforcement": "ALWAYS start in ENGLISH. Speak ONLY in English unless the user explicitly asks you to switch to a different language. If they request a language change, confirm the switch and then use that language."
```

To force English-only:
```json
"language_enforcement": "You MUST speak ONLY in English. Never use any other language under any circumstances."
```

### 3. **Conversation Memory**
```json
"core_rules": [
  "REMEMBER USER NAME: If the user tells you their name, use it throughout the conversation",
  "TRACK CONTEXT: Remember what you discussed earlier and reference it naturally",
  "PERSONALIZE: Adapt your responses based on what you've learned about the user"
]
```

### 4. **Domain-Specific Knowledge**
Add specific instructions in `conversation_script`:
```json
"phase_2_domain_expertise": {
  "title": "Domain Knowledge Application",
  "medical_advice": "Never provide medical advice. Always say 'Please consult a healthcare professional.'",
  "legal_advice": "Never provide legal advice. Direct users to licensed attorneys.",
  "financial_planning": "Provide general information only. Recommend consulting a financial advisor for specific decisions."
}
```

---

## Troubleshooting

**Issue: Voice not playing**
- Check browser console for errors
- Verify Azure credentials in `.env`
- Check network tab for WebSocket connection

**Issue: Wrong language on startup**
- Update `intro_message` in `config.json` to explicitly state language
- Add language enforcement at the top of `system_prompt`

**Issue: Persona not following script**
- Make instructions more explicit in `core_rules`
- Add examples in `conversation_script`
- Use CAPS for critical instructions (e.g., "ALWAYS", "NEVER")

**Issue: Deployment fails**
- Verify GCP project has billing enabled
- Check Docker image built successfully: `docker images | grep your-app-name`
- Ensure all files are copied in Dockerfile

**Issue: Static/crackling audio**
- This is inherent to Azure TTS (not fixable client-side)
- Try different voices (cedar, shimmer are cleaner)
- Consider audio crossfading already implemented

---

## Example: Creating a "FitCoach" App

```bash
# 1. Copy template
cp -r Newton FitCoach
cd FitCoach

# 2. Update config.json
{
  "voice": "onyx",
  "intro_message": "[Call started - Greet energetically and ask about fitness goals]",
  "system_prompt": {
    "role": "FitCoach - Personal Fitness Trainer",
    "goal": "Motivate users to achieve their fitness goals through encouragement and actionable advice",
    "tone_and_style": {
      "description": "Energetic, motivational, like a supportive gym trainer",
      "interjections": ["Let's go!", "You got this!", "Awesome!"],
      ...
    },
    "core_rules": [
      "BE MOTIVATIONAL: Always encourage and celebrate progress",
      "ASK ABOUT GOALS: First conversation should establish fitness goals",
      "TRACK PROGRESS: Remember what exercises they mentioned and follow up"
    ],
    ...
  }
}

# 3. Update branding in index.html
<title>FitCoach 💪 - Your AI Fitness Trainer</title>
<h1>💪 FitCoach - Your Personal Trainer</h1>

# 4. Update client.js labels
const roleLabel = item.role === 'user' ? 'You' : 'FitCoach';

# 5. Set port in .env
PORT=8003

# 6. Deploy
docker build --platform=linux/amd64 -t gcr.io/vernac-479217/fitcoach .
docker push gcr.io/vernac-479217/fitcoach
gcloud run deploy fitcoach --image gcr.io/vernac-479217/fitcoach ...
```

---

## Best Practices

1. **Test Locally First**: Always run `python3 server.py` and test at localhost before deploying
2. **Version Control**: Keep each app in its own directory (Vernac, Newton, FitCoach, etc.)
3. **Explicit Instructions**: Make config.json rules very explicit - GPT-4o follows clear instructions better
4. **Unique Ports**: Use different ports for each app when running locally (8000, 8001, 8002, etc.)
5. **Consistent Naming**: Use the same name throughout (folder name, Docker image, Cloud Run service)
6. **Environment Variables**: Never commit `.env` to git - keep credentials secure

---

## Resources

- **Azure OpenAI Realtime API Docs**: https://learn.microsoft.com/en-us/azure/ai-services/openai/realtime-audio
- **Cloud Run Docs**: https://cloud.google.com/run/docs
- **Voice Options**: Test different voices at https://platform.openai.com/docs/guides/text-to-speech

---

## Need Help?

**Common Issues:**
1. Config not loading → Check JSON syntax with `python3 -m json.tool config.json`
2. Deployment fails → Check `gcloud builds list` for build logs
3. Voice issues → Try different voice options in config.json
4. Language problems → Strengthen `language_enforcement` rules

**Current Deployments:**
- Vernac (ABC Bank): https://vernac-voice-agent-708533464468.us-central1.run.app
- Newton (Science Teacher): https://newton-science-teacher-708533464468.us-central1.run.app
