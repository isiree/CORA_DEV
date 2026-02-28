# ============================================
# IMRAG Terraform Variables
# Used by CI/CD pipeline for scaling operations
# ============================================

variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
  default     = "rg-imrag-dev"
}

#variable "location" {
  #description = "Azure region for resources"
  #type        = string
  #default     = "UK South"
#}

#variable "environment" {
# description = "Environment name"
# type        = string
# default     = "dev"
#}

# ============================================
# SCALING VARIABLES - Used by CI/CD pipeline
# ============================================
variable "container_cpu" {
  description = "CPU cores for container instance (used by scale_up/scale_down jobs)"
  type        = string
  default     = "0.5"
}

variable "container_memory" {
  description = "Memory in GB for container instance (used by scale_up/scale_down jobs)"
  type        = string
  default     = "0.5"
}

# ============================================
# COMMON TAGS
# ============================================
variable "common_tags" {
  description = "Common tags for all resources"
  type        = map(string)
  default = {
    project     = "imrag"
    environment = "dev"
    managed_by  = "terraform"
  }
}