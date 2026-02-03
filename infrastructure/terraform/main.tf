# ============================================
# IMRAG Infrastructure - All-in-One
# ============================================

terraform {
  required_version = ">= 1.0.0"
  
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.80"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }
}

provider "azurerm" {
  features {
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
    key_vault {
      purge_soft_delete_on_destroy = true
    }
  }
  subscription_id = var.subscription_id
}

# ============================================
# VARIABLES
# ============================================

variable "subscription_id" {
  type = string
}

variable "location" {
  type    = string
  default = "australiaeast"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "monthly_budget" {
  type    = number
  default = 35
}

variable "alert_email" {
  type = string
}

# ============================================
# RANDOM SUFFIX
# ============================================

resource "random_string" "suffix" {
  length  = 6
  special = false
  upper   = false
}

locals {
  suffix = random_string.suffix.result
  common_tags = {
    project     = "imrag"
    environment = var.environment
    managed_by  = "terraform"
  }
}

# ============================================
# RESOURCE GROUP
# ============================================

resource "azurerm_resource_group" "main" {
  name     = "rg-imrag-${var.environment}"
  location = var.location
  tags     = local.common_tags
}

# ============================================
# RELEASE TEAM - Storage Account
# ============================================

resource "azurerm_storage_account" "release" {
  name                     = "strelease${local.suffix}"
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  access_tier              = "Cool"
  
  tags = merge(local.common_tags, { team = "release", lead = "Alex Johnson" })
}

# ============================================
# CI TEAM - Storage Account + Container
# ============================================

resource "azurerm_storage_account" "ci" {
  name                     = "stci${local.suffix}"
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  access_tier              = "Cool"
  
  tags = merge(local.common_tags, { team = "ci", lead = "James Wilson" })
}

resource "azurerm_container_group" "ci" {
  name                = "aci-ci-${local.suffix}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  os_type             = "Linux"
  restart_policy      = "OnFailure"
  ip_address_type     = "None"

  container {
    name   = "ci-runner"
    image  = "mcr.microsoft.com/azure-cli:latest"
    cpu    = 0.25
    memory = 0.5
    commands = ["/bin/sh", "-c", "echo 'CI Runner' && sleep 3600"]
  }
  
  tags = merge(local.common_tags, { team = "ci", lead = "James Wilson" })
}

# ============================================
# CLOUDOPS TEAM - Key Vault + Function App
# ============================================

data "azurerm_client_config" "current" {}

resource "azurerm_key_vault" "cloudops" {
  name                       = "kv-ops-${local.suffix}"
  resource_group_name        = azurerm_resource_group.main.name
  location                   = azurerm_resource_group.main.location
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  soft_delete_retention_days = 7
  purge_protection_enabled   = false
  
  access_policy {
    tenant_id          = data.azurerm_client_config.current.tenant_id
    object_id          = data.azurerm_client_config.current.object_id
    secret_permissions = ["Get", "List", "Set", "Delete", "Purge"]
    key_permissions    = ["Get", "List", "Create", "Delete"]
  }
  
  tags = merge(local.common_tags, { team = "cloudops", lead = "David Brown" })
}

resource "azurerm_storage_account" "cloudops" {
  name                     = "stfunc${local.suffix}"
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  
  tags = merge(local.common_tags, { team = "cloudops", lead = "David Brown" })
}

resource "azurerm_service_plan" "cloudops" {
  name                = "asp-ops-${local.suffix}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  os_type             = "Linux"
  sku_name            = "Y1"
  
  tags = merge(local.common_tags, { team = "cloudops" })
}

resource "azurerm_linux_function_app" "cloudops" {
  name                       = "func-ops-${local.suffix}"
  resource_group_name        = azurerm_resource_group.main.name
  location                   = azurerm_resource_group.main.location
  service_plan_id            = azurerm_service_plan.cloudops.id
  storage_account_name       = azurerm_storage_account.cloudops.name
  storage_account_access_key = azurerm_storage_account.cloudops.primary_access_key
  
  site_config {
    application_stack {
      python_version = "3.11"
    }
  }
  
  tags = merge(local.common_tags, { team = "cloudops", lead = "David Brown" })
}

# ============================================
# MONITORING
# ============================================

resource "azurerm_log_analytics_workspace" "main" {
  name                = "log-imrag-${local.suffix}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "PerGB2018"
  retention_in_days   = 30
  daily_quota_gb      = 0.5
  
  tags = local.common_tags
}

resource "azurerm_application_insights" "main" {
  name                = "appi-imrag-${local.suffix}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  workspace_id        = azurerm_log_analytics_workspace.main.id
  application_type    = "web"
  
  tags = local.common_tags
}

# ============================================
# BUDGET ALERT
# ============================================

resource "azurerm_consumption_budget_resource_group" "main" {
  name              = "budget-imrag"
  resource_group_id = azurerm_resource_group.main.id
  amount            = var.monthly_budget
  time_grain        = "Monthly"
  
  time_period {
    start_date = "2026-02-01T00:00:00Z"
    end_date   = "2026-12-31T00:00:00Z"
  }
  
  notification {
    enabled        = true
    threshold      = 80
    operator       = "GreaterThan"
    contact_emails = [var.alert_email]
  }
}

# ============================================
# OUTPUTS
# ============================================

output "resource_group" {
  value = azurerm_resource_group.main.name
}

output "storage_accounts" {
  value = {
    release  = azurerm_storage_account.release.name
    ci       = azurerm_storage_account.ci.name
    cloudops = azurerm_storage_account.cloudops.name
  }
}

output "key_vault" {
  value = azurerm_key_vault.cloudops.name
}

output "function_app" {
  value = azurerm_linux_function_app.cloudops.default_hostname
}
