#!/usr/bin/env bash
# Guardian Angel — Cloud Run Deployment Script
#
# Usage:
#   ./deploy/cloud_run_deploy.sh [PROJECT_ID] [REGION]
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - Docker installed
#   - Artifact Registry repository created
#
# Environment variables (set in Cloud Run):
#   - OPENROUTER_API_KEY
#   - JWT_SECRET
#   - DATABASE_URL

set -euo pipefail

PROJECT_ID="${1:-guardian-angel-prod}"
REGION="${2:-us-central1}"
SERVICE_NAME="guardian-angel"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "============================================"
echo "🛡️  Guardian Angel — Cloud Run Deployment"
echo "============================================"
echo "  Project:  ${PROJECT_ID}"
echo "  Region:   ${REGION}"
echo "  Service:  ${SERVICE_NAME}"
echo "  Image:    ${IMAGE_NAME}"
echo "============================================"
echo ""

# Step 1: Build the Docker image
echo "📦 Building Docker image..."
docker build -t "${IMAGE_NAME}:latest" .

# Step 2: Push to Container Registry
echo "⬆️  Pushing to Container Registry..."
docker push "${IMAGE_NAME}:latest"

# Step 3: Deploy to Cloud Run
echo "🚀 Deploying to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --image="${IMAGE_NAME}:latest" \
  --platform=managed \
  --allow-unauthenticated \
  --port=8000 \
  --memory=512Mi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=3 \
  --timeout=300 \
  --set-env-vars="ENVIRONMENT=production"

# Step 4: Get the service URL
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --format="value(status.url)")

echo ""
echo "============================================"
echo "✅ Deployment complete!"
echo "============================================"
echo "  Service URL: ${SERVICE_URL}"
echo ""
echo "⚠️  Remember to set secrets:"
echo "  gcloud run services update ${SERVICE_NAME} \\"
echo "    --set-env-vars=OPENROUTER_API_KEY=<key>,JWT_SECRET=<secret>"
echo "============================================"
