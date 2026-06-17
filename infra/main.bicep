@description('The name of the storage account. Must be globally unique and under 24 chars.')
param storageAccountName string = 'stcomp${uniqueString(resourceGroup().id)}'

@description('The location for all resources.')
param location string = resourceGroup().location

// Create the Storage Account
resource storageAccount 'Microsoft.Storage/storageAccounts@2022-09-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
  }
}

// Create the Queue Service
resource queueService 'Microsoft.Storage/storageAccounts/queueServices@2022-09-01' = {
  parent: storageAccount
  name: 'default'
}

// Create the tx-events Queue
resource txEventQueue 'Microsoft.Storage/storageAccounts/queueServices/queues@2022-09-01' = {
  parent: queueService
  name: 'tx-events'
}

// Create the Blob Service
resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2022-09-01' = {
  parent: storageAccount
  name: 'default'
}

// Create the 3 Blob Containers
resource container1 'Microsoft.Storage/storageAccounts/blobServices/containers@2022-09-01' = {
  parent: blobService
  name: 'tx-payloads'
}

resource container2 'Microsoft.Storage/storageAccounts/blobServices/containers@2022-09-01' = {
  parent: blobService
  name: 'tx-processed'
}

resource container3 'Microsoft.Storage/storageAccounts/blobServices/containers@2022-09-01' = {
  parent: blobService
  name: 'tx-flagged'
}

// Output the Storage Account Name so the bash script can retrieve the connection string easily
output storageAccountName string = storageAccount.name
