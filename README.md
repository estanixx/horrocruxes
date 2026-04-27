# Horrocruxes

Backend API project with FastAPI, deployed to AWS AppRunner.

## Local Development

### Prerequisites

- Docker
- Docker Compose

### Quick Start

```bash
# Start all services locally
docker-compose up --build

# Run in detached mode
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

The backend will be available at `http://localhost:8000`

### API Endpoints

- `GET /` - Root endpoint
- `GET /health` - Health check

### Development

The development container uses hot-reload. Any changes to the code will automatically reload the application.

```bash
# Rebuild after dependency changes
docker-compose build
```

## Infrastructure

### AWS CloudFormation

The `infrastructure/setup.yaml` template creates:

- OIDC Provider for GitHub Actions
- IAM Role with OIDC trust policy
- ECR Repository for backend images
- Optional VPC Connector for AppRunner

```bash
# Deploy infrastructure
aws cloudformation deploy \
  --template-file infrastructure/setup.yaml \
  --stack-name horrocruxes-infra \
  --parameter-overrides \
    GitHubOrg=your-org \
    GitHubRepo=horrocruxes \
    GitHubBranch=prod \
    EcrRepositoryName=horrocruxes-backend \
    Environment=production
```

### GitHub Actions

Push to the `prod` branch triggers:
1. Docker image build
2. Push to ECR
3. Deploy to AWS AppRunner

**Required Secrets:**

| Secret | Description |
|--------|-------------|
| `AWS_ROLE_ARN` | GitHub Actions role ARN (from CloudFormation output `GitHubActionsRoleArn`) |
| `ECR_ACCESS_ROLE_ARN` | AppRunner ECR access role ARN (from CloudFormation output `AppRunnerECRAccessRoleArn`) |