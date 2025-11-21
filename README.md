# MyRunStreak.com

A serverless multi-user running analytics platform powered by SmashRun, Supabase, and AWS.

## Overview

MyRunStreak.com automatically tracks and analyzes daily running streaks by connecting to the SmashRun API via OAuth. Run data is stored in Supabase PostgreSQL with multi-user support, providing scalable, serverless analytics.

## Quick Start

```bash
# Install the CLI
uv tool install git+https://github.com/silverbeer/myrunstreak.com

# Login with SmashRun
stk auth login

# Sync your runs
stk sync

# View your stats
stk stats
```

The CLI requires **no configuration** - it connects directly to `api.myrunstreak.run`.

## Architecture

| Component | Technology |
|-----------|------------|
| API | `api.myrunstreak.run` (API Gateway + Lambda) |
| Database | Supabase PostgreSQL |
| Auth | OAuth tokens stored in Supabase |
| Scheduling | AWS EventBridge (daily sync) |
| Secrets | AWS Secrets Manager |
| IaC | Terraform |
| CI/CD | GitHub Actions |

## CLI Commands

```bash
stk auth login      # Authenticate with SmashRun
stk auth status     # Check login status
stk sync            # Sync recent runs
stk sync --full     # Sync all runs
stk stats           # Overall statistics
stk runs            # List recent runs
stk streak          # Current streak
```

## Tech Stack

- **Language**: Python 3.12+
- **Package Manager**: UV
- **Database**: Supabase PostgreSQL
- **Cloud**: AWS (Lambda, API Gateway, Secrets Manager, EventBridge)
- **IaC**: Terraform
- **CLI**: Typer + Rich

## Project Structure

```
myrunstreak.com/
├── src/
│   ├── cli/                    # CLI application (stk)
│   ├── lambdas/
│   │   ├── sync_runs/          # Daily sync Lambda
│   │   └── query_runs/         # Query API Lambda
│   └── shared/
│       ├── supabase_ops/       # Database operations
│       ├── smashrun/           # SmashRun API client
│       └── models/             # Pydantic models
├── terraform/
│   ├── modules/                # Reusable Terraform modules
│   └── environments/           # Environment configs (dev/prod)
├── supabase/
│   └── migrations/             # Database migrations
└── tests/                      # Unit & integration tests
```

## Development

### Prerequisites

- Python 3.12+
- UV package manager
- AWS CLI
- Terraform 1.5+
- Supabase CLI

### Setup

```bash
# Clone and install
git clone https://github.com/silverbeer/myrunstreak.com.git
cd myrunstreak.com
uv sync --all-extras

# Start local Supabase
supabase start

# Run tests
uv run pytest
```

### Code Quality

```bash
uv run ruff check .      # Linting
uv run ruff format .     # Formatting
uv run mypy src/         # Type checking
```

## Deployment

### 1. Bootstrap Terraform State

```bash
cd terraform/bootstrap
terraform init && terraform apply
```

See [docs/TERRAFORM_BOOTSTRAP.md](docs/TERRAFORM_BOOTSTRAP.md)

### 2. Configure Secrets

Store credentials in AWS Secrets Manager:
- `myrunstreak/{env}/supabase/credentials`
- `myrunstreak/{env}/smashrun/oauth`

### 3. Deploy Infrastructure

```bash
cd terraform/environments/dev
terraform init && terraform apply
```

See [docs/PRODUCTION_DEPLOYMENT.md](docs/PRODUCTION_DEPLOYMENT.md)

## Documentation

- [Architecture Overview](docs/ARCHITECTURE.md)
- [Terraform Bootstrap](docs/TERRAFORM_BOOTSTRAP.md)
- [GitHub Actions CI/CD](docs/GITHUB_ACTIONS.md)
- [GitHub OIDC Authentication](docs/GITHUB_OIDC.md) - Secure, token-free AWS authentication
- [Production Deployment](docs/PRODUCTION_DEPLOYMENT.md)
- [Local Testing](docs/LOCAL_TESTING.md)

## Features

**Current:**
- Multi-user support with OAuth authentication
- Automatic daily sync from SmashRun
- Streak tracking and analytics
- CLI tool with zero configuration
- RESTful API at `api.myrunstreak.run`

**Planned:**
- Web dashboard
- Multi-source support (Garmin, Strava)
- Notifications for streak milestones
- Social features

## License

MIT
