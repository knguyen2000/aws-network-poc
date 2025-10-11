variable "aws_region" {
  description = "AWS region"
  default     = "us-east-1"
}

variable "aws_az" {
  description = "Primary AZ"
  default     = "us-east-1a"
}

variable "aws_az_b" {
  description = "Secondary AZ"
  default     = "us-east-1b"
}

variable "instance_type" {
  description = "EC2 instance type"
  default     = "t3.micro"
}

# Only prefix is a var in this pattern (bucket is created by Terraform)
variable "results_prefix" {
  description = "Key prefix inside the results bucket (include trailing slash)"
  default     = "net-results/"
}
