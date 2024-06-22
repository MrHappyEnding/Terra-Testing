variable "access_key" {
  description = "Access key for Alibaba Cloud."
  type        = string
}

variable "secret_key" {
  description = "Secret key for Alibaba Cloud."
  type        = string
}

variable "region" {
  description = "The region to deploy resources in."
  type        = string
  default     = "cn-hangzhou"
}

variable "zone_id" {
  description = "The availability zone to deploy resources in."
  type        = string
  default     = "cn-hangzhou-b"
}

variable "ecs_password" {
  description = "Password for the ECS instance."
  type        = string
}
