// ============================================================================
// Compliance Pipeline — Demo infrastructure (L0 ingestion)
// ----------------------------------------------------------------------------
// Provisions the MINIMUM real Azure footprint needed to demo L0 -> L2:
//   * A Storage Account that hosts the `tx-events` Queue (L0 publishes here)
//   * Blob containers used by later layers (reports / schemas / audit-logs)
//   * (Optional) an empty L2 Function App shell, only to mirror the architecture
//
// Deliberately NOT provisioned (to protect Azure-for-Students credit):
//   Cosmos DB, Service Bus, Azure OpenAI, AI Search, Document Intelligence.
//   None are required for the L0->L2 demo and they are the main cost drivers.
//
// Deploy:
//   az group create -n rg-compliance-demo -l centralindia
//   az deployment group create -g rg-compliance-demo -f infra/main.bicep
// ============================================================================

@description('Azure region for all resources. Defaults to the resource group region.')
param location string = resourceGroup().location

@description('Short prefix used to name resources (lowercase letters/numbers).')
@minLength(2)
@maxLength(8)
param prefix string = 'comp'

@description('Set true to also create an empty L2 Function App shell (Consumption, ~free).')
param deployFunctionApp bool = false

// Globally-unique, deterministic suffix derived from the resource group id.
var suffix = uniqueString(resourceGroup().id)
var storageName = toLower('${prefix}st${suffix}')
var planName = '${prefix}-l2-plan'
var funcName = toLower('${prefix}-l2-${suffix}')

// ---------------------------------------------------------------------------
// Storage Account  (Standard LRS — cheapest redundancy, fine for a demo)
// ---------------------------------------------------------------------------
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    supportsHttpsTrafficOnly: true
  }
}

// Queue service + the tx-events queue that L0 publishes transactions to.
resource queueService 'Microsoft.Storage/storageAccounts/queueServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource txEventsQueue 'Microsoft.Storage/storageAccounts/queueServices/queues@2023-05-01' = {
  parent: queueService
  name: 'tx-events'
}

// Blob service + the containers referenced in config.py.
resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource reportsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'reports'
}

resource schemasContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'schemas'
}

resource auditLogsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'audit-logs'
}

// ---------------------------------------------------------------------------
// (Optional) L2 Function App shell — Linux Consumption (Y1). Empty by design;
// it exists only so the portal mirrors the "L2 - Monitor: Function Apps" box.
// ---------------------------------------------------------------------------
resource plan 'Microsoft.Web/serverfarms@2023-12-01' = if (deployFunctionApp) {
  name: planName
  location: location
  sku: {
    name: 'Y1'
    tier: 'Dynamic'
  }
  properties: {
    reserved: true // Linux
  }
}

resource func 'Microsoft.Web/sites@2023-12-01' = if (deployFunctionApp) {
  name: funcName
  location: location
  kind: 'functionapp,linux'
  properties: {
    serverFarmId: plan.id
    reserved: true
    siteConfig: {
      linuxFxVersion: 'Python|3.11'
      appSettings: [
        {
          name: 'AzureWebJobsStorage'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storage.name};AccountKey=${storage.listKeys().keys[0].value};EndpointSuffix=${environment().suffixes.storage}'
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
      ]
    }
  }
}

// ---------------------------------------------------------------------------
// Outputs — used to build the .env connection string for the pipeline.
// ---------------------------------------------------------------------------
output storageAccountName string = storage.name
output queueName string = txEventsQueue.name
output functionAppName string = deployFunctionApp ? func.name : 'not-deployed'
