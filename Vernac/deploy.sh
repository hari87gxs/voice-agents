#!/bin/bash

# GCP Deployment Script for Vernac Voice Agent
# This script deploys the application to Google Cloud Platform

set -e  # Exit on error

echo "🚀 Vernac Voice Agent - GCP Deployment Script"
echo "=============================================="

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ gcloud CLI not found. Please install it first:${NC}"
    echo "   https://cloud.google.com/sdk/docs/install"
    exit 1
fi

echo -e "${GREEN}✓ gcloud CLI found${NC}"

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${RED}❌ .env file not found!${NC}"
    echo "Please create .env with your Azure OpenAI credentials:"
    echo "  AZURE_OPENAI_ENDPOINT=your_endpoint"
    echo "  AZURE_OPENAI_API_KEY=your_api_key"
    echo "  AZURE_OPENAI_DEPLOYMENT=your_deployment"
    exit 1
fi

echo -e "${GREEN}✓ .env file found${NC}"

# Prompt for GCP project ID
read -p "Enter your GCP Project ID: " PROJECT_ID

if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}❌ Project ID cannot be empty${NC}"
    exit 1
fi

# Set the project
echo -e "${YELLOW}Setting GCP project to: ${PROJECT_ID}${NC}"
gcloud config set project $PROJECT_ID

# Choose deployment method
echo ""
echo "Choose deployment method:"
echo "1) Cloud Run (Recommended - Serverless, auto-scaling)"
echo "2) App Engine (Standard environment)"
read -p "Enter choice [1-2]: " DEPLOY_METHOD

if [ "$DEPLOY_METHOD" = "1" ]; then
    # Cloud Run Deployment
    echo -e "${YELLOW}📦 Deploying to Cloud Run...${NC}"
    
    SERVICE_NAME="vernac-voice-agent"
    REGION="us-central1"
    
    read -p "Enter service name (default: vernac-voice-agent): " INPUT_SERVICE_NAME
    SERVICE_NAME=${INPUT_SERVICE_NAME:-$SERVICE_NAME}
    
    read -p "Enter region (default: us-central1): " INPUT_REGION
    REGION=${INPUT_REGION:-$REGION}
    
    # Load environment variables from .env
    source .env
    
    # Build and deploy
    echo -e "${YELLOW}Building container image...${NC}"
    gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME
    
    echo -e "${YELLOW}Deploying to Cloud Run...${NC}"
    gcloud run deploy $SERVICE_NAME \
        --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
        --platform managed \
        --region $REGION \
        --allow-unauthenticated \
        --set-env-vars AZURE_OPENAI_ENDPOINT=$AZURE_OPENAI_ENDPOINT,AZURE_OPENAI_API_KEY=$AZURE_OPENAI_API_KEY,AZURE_OPENAI_DEPLOYMENT=$AZURE_OPENAI_DEPLOYMENT \
        --port 8000 \
        --memory 512Mi \
        --cpu 1 \
        --timeout 300
    
    # Get the service URL
    SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)')
    
    echo ""
    echo -e "${GREEN}✅ Deployment successful!${NC}"
    echo -e "${GREEN}🌐 Your app is live at: ${SERVICE_URL}${NC}"
    
elif [ "$DEPLOY_METHOD" = "2" ]; then
    # App Engine Deployment
    echo -e "${YELLOW}📦 Deploying to App Engine...${NC}"
    
    # Load environment variables and create app.yaml with secrets
    source .env
    
    # Create temporary app.yaml with environment variables
    cat > app.yaml.tmp << EOF
runtime: python311
env: standard
instance_class: F2
entrypoint: python server.py

env_variables:
  HOST: "0.0.0.0"
  PORT: "8080"
  AZURE_OPENAI_ENDPOINT: "$AZURE_OPENAI_ENDPOINT"
  AZURE_OPENAI_API_KEY: "$AZURE_OPENAI_API_KEY"
  AZURE_OPENAI_DEPLOYMENT: "$AZURE_OPENAI_DEPLOYMENT"

automatic_scaling:
  min_instances: 1
  max_instances: 10
  target_cpu_utilization: 0.65
EOF
    
    echo -e "${YELLOW}Deploying to App Engine...${NC}"
    gcloud app deploy app.yaml.tmp --quiet
    
    # Clean up temporary file
    rm app.yaml.tmp
    
    # Get the service URL
    SERVICE_URL=$(gcloud app describe --format 'value(defaultHostname)')
    SERVICE_URL="https://$SERVICE_URL"
    
    echo ""
    echo -e "${GREEN}✅ Deployment successful!${NC}"
    echo -e "${GREEN}🌐 Your app is live at: ${SERVICE_URL}${NC}"
    
else
    echo -e "${RED}❌ Invalid choice${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}📋 Next Steps:${NC}"
echo "1. Test your deployment by visiting the URL above"
echo "2. Click 'Start Call' and test the voice agent"
echo "3. Share the URL with your team for testing"
echo ""
echo -e "${YELLOW}💡 Tips:${NC}"
echo "- Update CORS origins in .env to include your deployed URL"
echo "- Monitor logs: gcloud logging read"
echo "- Update config.json and redeploy to change agent behavior"
echo ""
echo -e "${GREEN}Happy testing! 🎉${NC}"
