# Copilot Instructions for Horrocruxes

## Purpose
This file provides repository-specific guidance for GitHub Copilot and other AI coding agents when working in this project.

## Key points
- The backend is a FastAPI service in `backend/app/main.py` with chat endpoints at `POST /chat` and `WS /ws/chat`.
- Business logic lives in `backend/app/graph_engine.py` and `backend/app/memory.py`.
- Frontend is a React + Vite app in `Frontend/`.
- Use `docker-compose up --build` to run both services locally.
- The backend uses the new Pinecone SDK package `pinecone`; do not switch to `pinecone-client`.
- Preserve existing API contracts when changing endpoints or request/response shapes.

## When modifying code
- Keep environment variable semantics aligned with `README.md`.
- Prefer minimal, safe changes in backend chat flow since frontend and ingestion scripts depend on stable routes and model behavior.
- Do not assume a test suite is present; validate changes through manual local execution or by inspecting the app logic.

## Links
- [Project README](./README.md)
- [Frontend README](./Frontend/README.md)

## Notes for AI agents
- This repository uses `AGENTS.md` for architecture and workflow reference.
- `copilot-instructions.md` is the authoritative repo-specific instruction file used by Copilot and related tools.
