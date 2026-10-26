variable "subscription_id" {
  description = "Your Azure subscription ID (az account show --query id -o tsv)"
  type        = string
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "canadacentral"
}

variable "environment" {
  description = "Short name added to every resource, e.g. demo or dev"
  type        = string
  default     = "demo"
}

variable "image" {
  description = "The container image to run"
  type        = string
  default     = "ghcr.io/5hayam0hebbi/hireops:latest"
}
