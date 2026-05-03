# Horrocruxes AI Agent Instructions

## Purpose
This file helps AI coding agents understand the repository structure, main responsibilities, and where to find authoritative docs.

## Project overview
- `backend/`: FastAPI backend with an LLM-driven chat pipeline and session memory support.
- `Frontend/`: React + Vite web client.
- `docker-compose.yaml`: local development orchestrator for backend + frontend.
- `infrastructure/setup.yaml`: AWS CloudFormation infrastructure template for GitHub Actions / AppRunner deployment.

## Key conventions
- Backend entrypoint: `backend/app/main.py`
- Chat routing and business logic live in `backend/app/graph_engine.py` and `backend/app/memory.py`
- Backend production dependencies: `backend/requirements.txt`
- Backend developer-only dependencies: `backend/dev-requirements.txt`
- Frontend scripts are defined in `Frontend/package.json`

## Local development commands
- Start both services: `docker-compose up --build`
- Start detached: `docker-compose up -d`
- Stop services: `docker-compose down`
- Rebuild after dependency changes: `docker-compose build`
- Frontend only: `docker-compose up --build frontend`
- Backend only: use Docker Compose service `backend` or run Python from `backend/`

## Important environment details
- Backend environment variables are documented in `README.md`.
- Notable backend behavior:
  - Uses Pinecone with the new `pinecone` SDK package.
  - Supports `sentence-transformers` and `gemini` embedding providers.
  - Uses `LANGSMITH_API_KEY` optionally for tracing.
- Frontend base API URL is configured via `VITE_API_URL`.

## Guidance for AI agents
- Prefer linking to `README.md` for environment setup and deployment details.
- Preserve backend API behavior when modifying chat flow; the frontend expects `POST /chat` and WebSocket `/ws/chat`.
- Backend CORS is configured for local React dev servers on `5173`/`5174`.
- The repository does not appear to include a dedicated test suite; focus changes on runtime behavior and README-driven instructions.

## Use this file as a quick reference when:
- Adding or changing API endpoints
- Updating deployment or local development flows
- Working on backend/frontend integration
- Modifying environment variable handling
