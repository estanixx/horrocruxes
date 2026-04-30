import asyncio
from typing import AsyncGenerator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.graph_engine import ChatRequest, ChatResponse, run_graph, stream_graph


app = FastAPI(
    title="Horrocruxes API",
    description="Backend API for Horrocruxes project",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Horrocruxes API", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    state = await run_graph(request.query)
    answer = state.answer or ""
    return ChatResponse(answer=answer, citations=state.citations)


async def _stream_state_events(query: str) -> AsyncGenerator[str, None]:
    async for update in stream_graph(query):
        for payload in update.values():
            if hasattr(payload, "route") and payload.route:
                yield f"route:{payload.route}"
            if hasattr(payload, "errors") and payload.errors:
                yield "errors:" + "; ".join(payload.errors)
            if hasattr(payload, "citations") and payload.citations:
                yield "citations:" + str([
                    c.model_dump() if hasattr(c, "model_dump") else c
                    for c in payload.citations
                ])
            if hasattr(payload, "answer") and payload.answer:
                yield "answer:" + payload.answer


@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            payload = await websocket.receive_json()
            query = payload.get("query")
            if not query:
                await websocket.send_text("error:missing query")
                continue
            try:
                async for event in _stream_state_events(query):
                    await websocket.send_text(event)
            except asyncio.TimeoutError:
                await websocket.send_text("error:timeout")
            except Exception:
                await websocket.send_text("error:internal_error")
    except WebSocketDisconnect:
        return
