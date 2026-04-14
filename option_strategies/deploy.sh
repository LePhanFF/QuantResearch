#!/usr/bin/env bash
#
# Deploy the Wheel Strategy Dashboard to Google Cloud Run.
#
# Usage:
#   ./deploy.sh                         # uses current gcloud project
#   ./deploy.sh my-project us-central1  # override project and region
#
set -euo pipefail

PROJECT="${1:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${2:-us-central1}"
SERVICE="wheel-dashboard"
REPO="wheel-repo"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/${SERVICE}"

echo "=== Wheel Strategy Dashboard Deploy ==="
echo "Project: ${PROJECT}  Region: ${REGION}  Image: ${IMAGE}"

# Enable APIs
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
    cloudbuild.googleapis.com --project="${PROJECT}" --quiet

# Create Artifact Registry (idempotent)
gcloud artifacts repositories describe "${REPO}" \
    --location="${REGION}" --project="${PROJECT}" 2>/dev/null || \
gcloud artifacts repositories create "${REPO}" \
    --repository-format=docker --location="${REGION}" \
    --project="${PROJECT}" --quiet

# Build and push
gcloud builds submit --tag="${IMAGE}" --project="${PROJECT}" --quiet

# Deploy to Cloud Run
gcloud run deploy "${SERVICE}" \
    --image="${IMAGE}" --region="${REGION}" --project="${PROJECT}" \
    --platform=managed --allow-unauthenticated \
    --memory=1Gi --cpu=1 --timeout=300 \
    --min-instances=0 --max-instances=3 --quiet

URL=$(gcloud run services describe "${SERVICE}" \
    --region="${REGION}" --project="${PROJECT}" --format="value(status.url)")

echo ""
echo "=== Deployed ==="
echo "Dashboard: ${URL}"
echo "Run scan:  curl ${URL}/api/scan"
