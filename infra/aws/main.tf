provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

locals {
  azs    = ["${var.region}a", "${var.region}b"]
  prefix = "${var.project}-${var.environment}"
}
