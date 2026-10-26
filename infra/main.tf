# Deploys the HireOps image to Azure Container Apps as a job you start on demand.
# Costs: Container Apps jobs bill only while running and include a monthly free grant;
# Log Analytics bills per GB ingested (cents here). Run `terraform destroy` when done.

terraform {
  required_version = ">= 1.6"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

locals {
  tags = {
    project = "hireops"
    owner   = "shaya"
    managed = "terraform"
  }
}

resource "azurerm_resource_group" "rg" {
  name     = "rg-hireops-${var.environment}"
  location = var.location
  tags     = local.tags
}

resource "azurerm_log_analytics_workspace" "logs" {
  name                = "log-hireops-${var.environment}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = local.tags
}

resource "azurerm_container_app_environment" "env" {
  name                       = "cae-hireops-${var.environment}"
  location                   = azurerm_resource_group.rg.location
  resource_group_name        = azurerm_resource_group.rg.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.logs.id
  tags                       = local.tags
}

resource "azurerm_container_app_job" "decoder" {
  name                         = "hireops-decoder-${var.environment}"
  location                     = azurerm_resource_group.rg.location
  resource_group_name          = azurerm_resource_group.rg.name
  container_app_environment_id = azurerm_container_app_environment.env.id
  replica_timeout_in_seconds   = 300
  replica_retry_limit          = 0
  tags                         = local.tags

  manual_trigger_config {
    parallelism              = 1
    replica_completion_count = 1
  }

  template {
    container {
      name   = "hireops"
      image  = var.image
      cpu    = 0.25
      memory = "0.5Gi"
      # Rules-only mode: no AI model in the cloud, so the demo stays cheap and fast.
      # --one-line prints the report as one JSON line, so each run is one log entry.
      args = ["samples/job.txt", "--resume", "samples/resume.md", "--no-ai", "--one-line"]
    }
  }
}
