output "resource_group" {
  value = azurerm_resource_group.rg.name
}

output "job_name" {
  value = azurerm_container_app_job.decoder.name
}

output "start_command" {
  description = "Paste this to run the job once"
  value       = "az containerapp job start --name ${azurerm_container_app_job.decoder.name} --resource-group ${azurerm_resource_group.rg.name}"
}
