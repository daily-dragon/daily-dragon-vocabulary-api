#!/bin/bash
# Run once locally with admin credentials to grant CDK permissions to the CI IAM user.
# Usage: ./scripts/setup_cdk_permissions.sh <iam-username>
set -e

if [ -z "$1" ]; then
  echo "Usage: $0 <iam-username>"
  echo "The IAM user whose credentials are stored in GitHub secrets."
  exit 1
fi

IAM_USER="$1"
POLICY_NAME="DailyDragonCDKPolicy"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
POLICY_ARN="arn:aws:iam::${ACCOUNT}:policy/${POLICY_NAME}"

echo "Creating policy $POLICY_NAME..."
if output=$(aws iam create-policy \
  --policy-name "$POLICY_NAME" \
  --policy-document "$(cat "$SCRIPT_DIR/cdk_permissions_policy.json")" 2>&1); then
  echo "Policy created."
elif echo "$output" | grep -q "EntityAlreadyExists"; then
  echo "Policy already exists, skipping."
else
  echo "Error creating policy: $output" >&2
  exit 1
fi

echo "Attaching policy to $IAM_USER..."
aws iam attach-user-policy \
  --user-name "$IAM_USER" \
  --policy-arn "$POLICY_ARN"

echo "Done. $IAM_USER can now run cdk bootstrap and cdk deploy."