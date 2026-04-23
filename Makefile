.PHONY: help install test lint format type-check bootstrap-tf init-tf plan-tf apply-tf destroy-tf restore-prod

# Default target
help:
	@echo "MyRunStreak.com - Available Commands"
	@echo ""
	@echo "Python Development:"
	@echo "  make install       - Install dependencies with UV"
	@echo "  make test          - Run pytest tests"
	@echo "  make lint          - Run ruff linting"
	@echo "  make format        - Format code with ruff"
	@echo "  make type-check    - Run mypy type checking"
	@echo ""
	@echo "Terraform Operations:"
	@echo "  make bootstrap-tf  - Bootstrap Terraform remote state (run once)"
	@echo "  make init-tf       - Initialize Terraform (dev environment)"
	@echo "  make plan-tf       - Plan Terraform changes (dev environment)"
	@echo "  make apply-tf      - Apply Terraform changes (dev environment)"
	@echo "  make destroy-tf    - Destroy Terraform infrastructure (dev)"
	@echo ""
	@echo "Database:"
	@echo "  make restore-prod  - Restore prod Supabase data to local (destroys local data)"
	@echo ""
	@echo "All-in-One:"
	@echo "  make setup         - Complete setup (install + bootstrap)"

# Python Development
install:
	uv sync --all-extras

test:
	uv run pytest

lint:
	uv run ruff check .

format:
	uv run ruff format .

type-check:
	uv run mypy src/

# Terraform Bootstrap (run once)
bootstrap-tf:
	@echo "Bootstrapping Terraform remote state backend..."
	@echo "Make sure you've created terraform/bootstrap/terraform.tfvars with your AWS account ID"
	@cd terraform/bootstrap && terraform init && terraform plan && terraform apply

# Terraform Dev Environment
init-tf:
	@echo "Initializing Terraform dev environment..."
	@cd terraform/environments/dev && terraform init

plan-tf:
	@cd terraform/environments/dev && terraform plan

apply-tf:
	@cd terraform/environments/dev && terraform apply

destroy-tf:
	@echo "WARNING: This will destroy all infrastructure in dev environment"
	@cd terraform/environments/dev && terraform destroy

# Database
restore-prod:
	@scripts/restore_prod_to_local.sh

# Complete setup
setup: install
	@echo "Project setup complete!"
	@echo "Next steps:"
	@echo "1. Configure terraform/bootstrap/terraform.tfvars with your AWS account ID"
	@echo "2. Run 'make bootstrap-tf' to create remote state backend"
	@echo "3. Configure terraform/environments/dev/terraform.tfvars with your SmashRun credentials"
	@echo "4. Uncomment the backend block in terraform/environments/dev/main.tf"
	@echo "5. Run 'make init-tf' to initialize the dev environment"
