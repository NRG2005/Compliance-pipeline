#!/usr/bin/env bash
# This script grabs the Azure Storage Connection String and appends it to .env
# Usage: ./infra/setup-env.sh <ResourceGroupName>

if [ -z "$1" ]; then
  echo "Usage: ./infra/setup-env.sh <ResourceGroupName>"
  exit 1
fi

RESOURCE_GROUP=$1

echo "Fetching Storage Account from Resource Group: $RESOURCE_GROUP..."

# Get the first storage account in the resource group
STORAGE_ACCOUNT=$(az storage account list -g $RESOURCE_GROUP --query "[0].name" -o tsv)

if [ -z "$STORAGE_ACCOUNT" ]; then
  echo "No storage account found in $RESOURCE_GROUP."
  exit 1
fi

echo "Found Storage Account: $STORAGE_ACCOUNT"
echo "Fetching connection string..."

# Fetch the connection string
CONN_STR=$(az storage account show-connection-string -g $RESOURCE_GROUP -n $STORAGE_ACCOUNT --query "connectionString" -o tsv)

if [ -z "$CONN_STR" ]; then
  echo "Failed to get connection string."
  exit 1
fi

echo "Success! Writing connection string to .env file..."

# Append to .env (creating it if it doesn't exist)
# Check if BLOB_STORAGE_CONNECTION_STRING already exists in .env
if grep -q "BLOB_STORAGE_CONNECTION_STRING" .env 2>/dev/null; then
  # Replace the line on Mac using sed
  sed -i '' "s|BLOB_STORAGE_CONNECTION_STRING=.*|BLOB_STORAGE_CONNECTION_STRING=\"$CONN_STR\"|g" .env
else
  echo "" >> .env
  echo "BLOB_STORAGE_CONNECTION_STRING=\"$CONN_STR\"" >> .env
fi

# Add AZURE_STORAGE_QUEUE_NAME to .env if not present
if ! grep -q "AZURE_STORAGE_QUEUE_NAME" .env 2>/dev/null; then
  echo "AZURE_STORAGE_QUEUE_NAME=\"tx-events\"" >> .env
fi

echo "Environment configured successfully!"
