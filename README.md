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

The backend will be available at `http://localhost:8080`

### Environment Configuration

The backend uses these environment variables (defaults shown where applicable):

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_API_KEY` | — | Google GenAI API key for LLM (required when using Gemini embeddings) |
| `PINECONE_API_KEY` | — | Pinecone API key |
| `PINECONE_INDEX` | `horrocruxes-index` | Pinecone index name |
| `PINECONE_ENV` | — | Pinecone environment (kept for compatibility) |
| `LANGSMITH_API_KEY` | — | Enable LangSmith tracing when set |
| `LANGSMITH_PROJECT` | `horrocruxes` | LangSmith project name |
| `GOOGLE_LLM_MODEL` | `models/gemini-1.5-pro` | Gemini chat model for answers |
| `AWS_REGION` | `us-east-1` | AWS region for S3 |
| `S3_BUCKET` | `horrocruxes-data` | S3 bucket with PDFs/CSVs |
| `S3_PDF_PREFIX` | `data/books` | S3 prefix for PDF docs |
| `S3_CSV_PREFIX` | `data/structured` | S3 prefix for CSV data |
| `S3_REPORTS_PREFIX` | `reports` | S3 prefix for saved reports |
| `EMBEDDING_PROVIDER` | `sentence-transformers` | Embedding provider: `sentence-transformers` or `gemini` |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model for the selected provider |

LangSmith tracing is only enabled when `LANGSMITH_API_KEY` is present.

### API Endpoints

- `GET /` - Root endpoint
- `GET /health` - Health check
- `POST /chat` - Returns `ChatResponse` with citations list
- `WS /ws/chat` - Streams agent state updates

### Pinecone SDK Note

This project uses the **new** Pinecone SDK package name: `pinecone`.
The deprecated `pinecone-client` package is not supported here.

### Development

The development container uses hot-reload. Any changes to the code will automatically reload the application.

```bash
# Rebuild after dependency changes
docker-compose build
```

### Development Dependencies

Production dependencies live in `backend/requirements.txt`.
Heavy, local-only dependencies (embeddings ingestion) live in `backend/dev-requirements.txt`.

```bash
pip install -r backend/requirements.txt
pip install -r backend/dev-requirements.txt
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

## One-time Pinecone Ingestion

Index PDFs and CSVs from S3 into Pinecone once (or when data changes):

```bash
cd backend
export PINECONE_API_KEY=...
export PINECONE_INDEX=horrocruxes-index
export AWS_REGION=us-east-1
export S3_BUCKET=horrocruxes-data
export S3_PDF_PREFIX=data/books
export S3_CSV_PREFIX=data/structured
export EMBEDDING_PROVIDER=sentence-transformers
export EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

python scripts/ingest_pinecone.py
```

## Kaggle Dataset (7 CSVs) → S3 (one-time)

Download the Kaggle dataset locally, then upload to S3 for ingestion:

```bash
cd backend
pip install -r dev-requirements.txt

# Download dataset (requires Kaggle credentials)
export KAGGLE_DATASET=gulsahdemiryurek/harry-potter-dataset
export KAGGLE_DOWNLOAD_DIR=./data/kaggle
python scripts/kaggle_download.py

# Upload to S3 under S3_CSV_PREFIX
export S3_BUCKET=horrocruxes-data
export S3_CSV_PREFIX=data/structured
python scripts/kaggle_upload_s3.py

# Re-run ingestion to include CSVs
python scripts/ingest_pinecone.py
```

Optional ingestion tuning:

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBEDDING_PROVIDER` | `sentence-transformers` | Embedding provider (`sentence-transformers` or `gemini`) |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Override embedding model |
| `EMBEDDING_DEVICE` | `cpu` | Embedding device (`cpu` or `cuda`) - default is CPU |
| `INGEST_BATCH_SIZE` | `25` | Number of documents per upsert batch |
| `INGEST_RETRY_MAX` | `5` | Max retries when rate limited |
| `INGEST_RETRY_BASE_SECONDS` | `5` | Base backoff seconds for retries |

When using `EMBEDDING_PROVIDER=gemini`, set `GOOGLE_API_KEY` and optionally
`GOOGLE_EMBEDDING_MODEL` for the Gemini embedding model.

**Required Secrets:**

| Secret | Description |
|--------|-------------|
| `AWS_ROLE_ARN` | GitHub Actions role ARN (from CloudFormation output `GitHubActionsRoleArn`) |
| `ECR_ACCESS_ROLE_ARN` | AppRunner ECR access role ARN (from CloudFormation output `AppRunnerECRAccessRoleArn`) |
