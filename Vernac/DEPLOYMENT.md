# Deploying Vernac to Google Cloud Platform (GCP)

## Prerequisites

1. **Google Cloud Account**: Sign up at https://cloud.google.com
2. **gcloud CLI**: Install from https://cloud.google.com/sdk/docs/install
3. **GCP Project**: Create a project in the Google Cloud Console

## Quick Deploy (Recommended)

### Option 1: Cloud Run (Serverless)

```bash
# Run the deployment script
./deploy.sh
```

The script will:
1. Prompt for your GCP Project ID
2. Ask you to choose Cloud Run (option 1)
3. Build and deploy automatically
4. Give you a live URL

**Advantages:**
- Auto-scaling (0 to N instances)
- Pay only for actual usage
- HTTPS included
- Easy rollbacks

### Option 2: Manual Cloud Run Deployment

```bash
# Set your project
gcloud config set project YOUR_PROJECT_ID

# Build the container
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/vernac-voice-agent

# Deploy to Cloud Run
gcloud run deploy vernac-voice-agent \
  --image gcr.io/YOUR_PROJECT_ID/vernac-voice-agent \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars AZURE_OPENAI_ENDPOINT=your_endpoint,AZURE_OPENAI_API_KEY=your_key,AZURE_OPENAI_DEPLOYMENT=your_deployment \
  --port 8000 \
  --memory 512Mi \
  --timeout 300
```

### Option 3: App Engine

```bash
# Run the deployment script and choose option 2
./deploy.sh

# OR manually:
gcloud app deploy
```

## Environment Variables

Your `.env` file needs these values:

```
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key-here
AZURE_OPENAI_DEPLOYMENT=gpt-realtime
HOST=0.0.0.0
PORT=8000
```

**IMPORTANT**: Update `ALLOWED_ORIGINS` in `.env` after deployment:
```
ALLOWED_ORIGINS=https://your-deployed-url.run.app,http://localhost:8000
```

## Testing Your Deployment

1. Visit the URL provided after deployment
2. Click "Start Call"
3. Grant microphone permissions
4. Test the conversation flow

## Updating Configuration

To change the agent's behavior without redeploying:

1. Edit `config.json` locally
2. Redeploy: `./deploy.sh`

The deployment script preserves your environment variables.

## Monitoring & Logs

### Cloud Run
```bash
# View logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=vernac-voice-agent" --limit 50 --format json

# View metrics
gcloud run services describe vernac-voice-agent --region us-central1
```

### App Engine
```bash
# View logs
gcloud app logs tail -s default

# View metrics
gcloud app browse
```

## Troubleshooting

### Issue: "Permission Denied"
```bash
# Enable required APIs
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
```

### Issue: "CORS Error"
Update `.env`:
```
ALLOWED_ORIGINS=https://your-app.run.app,https://your-domain.com
```
Redeploy.

### Issue: "WebSocket Connection Failed"
Cloud Run has a 60-minute timeout. This is sufficient for typical calls.

### Issue: "Out of Memory"
Increase memory in deploy command:
```bash
--memory 1Gi
```

## Cost Estimation

### Cloud Run (Pay-per-use)
- Free tier: 2 million requests/month
- After free tier: ~$0.40 per million requests
- Memory: $0.0000025 per GB-second
- CPU: $0.00002400 per vCPU-second

**Estimated cost for 1000 calls/month (avg 3 min each):**
- ~$2-5/month

### App Engine
- F2 instance: ~$0.10/hour
- Min 1 instance = ~$73/month

**Recommendation**: Use Cloud Run for cost efficiency.

## Security Best Practices

1. **Never commit `.env` to git**
2. **Use Secret Manager** (for production):
```bash
# Store secret
gcloud secrets create azure-api-key --data-file=<(echo -n "your-key")

# Reference in Cloud Run
gcloud run deploy --update-secrets AZURE_OPENAI_API_KEY=azure-api-key:latest
```

3. **Enable authentication** (for internal use):
```bash
gcloud run deploy --no-allow-unauthenticated
```

## CI/CD (Optional)

For automated deployments, create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Cloud Run

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: google-github-actions/setup-gcloud@v1
        with:
          project_id: ${{ secrets.GCP_PROJECT_ID }}
          service_account_key: ${{ secrets.GCP_SA_KEY }}
      - run: gcloud builds submit --tag gcr.io/${{ secrets.GCP_PROJECT_ID }}/vernac-voice-agent
      - run: gcloud run deploy vernac-voice-agent --image gcr.io/${{ secrets.GCP_PROJECT_ID }}/vernac-voice-agent --region us-central1
```

## Sharing with Team

Once deployed, share:
1. **URL**: https://your-app.run.app
2. **Test Instructions**: "Click Start Call and speak naturally"
3. **Expected Behavior**: Reference the conversation script in `config.json`

## Rollback

If something goes wrong:

```bash
# Cloud Run - rollback to previous revision
gcloud run services update-traffic vernac-voice-agent --to-revisions PREVIOUS_REVISION=100

# App Engine - rollback
gcloud app versions list
gcloud app services set-traffic default --splits VERSION=1
```
