import asyncio
import uuid
from typing import AsyncGenerator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Header
from fastapi.middleware.cors import CORSMiddleware

from app.graph_engine import ChatRequest, ChatResponse, run_graph, stream_graph, build_graph, EnvConfig
from app import memory


app = FastAPI(
    title="Horrocruxes API",
    description="Backend API for Horrocruxes project",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
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
async def chat(
    request: ChatRequest,
    x_session_id: str = Header(default=None, description="Session ID for conversation history"),
) -> ChatResponse:
    # Use provided session_id or generate a new one
    session_id = x_session_id or str(uuid.uuid4())
    
    # Get conversation context from memory
    context = await memory.get_context_string(session_id)
    last_entity = await memory.get_last_entity(session_id)
    
    # Build the enhanced query with context
    enhanced_query = request.query
    if context:
        enhanced_query = f"""Previous conversation:
{context}

Current question: {request.query}"""
    
    # Run the graph with enhanced query
    config = EnvConfig()
    graph = build_graph(config)
    from app.graph_engine import GraphState
    state = GraphState(query=enhanced_query)
    result = await graph.ainvoke(state)
    
    # Extract answer safely
    if isinstance(result, GraphState):
        answer = result.answer or ""
        citations = result.citations if hasattr(result, "citations") else []
        agent_trace = result.agent_trace if hasattr(result, "agent_trace") else []
        timeline = result.timeline if hasattr(result, "timeline") else []
        report_markdown = result.report_markdown if hasattr(result, "report_markdown") else None
        confidence = result.confidence if hasattr(result, "confidence") else None
    else:
        answer = result.get("answer", "") if isinstance(result, dict) else ""
        citations = result.get("citations", []) if isinstance(result, dict) else []
        agent_trace = result.get("agent_trace", []) if isinstance(result, dict) else []
        timeline = result.get("timeline", []) if isinstance(result, dict) else []
        report_markdown = result.get("report_markdown") if isinstance(result, dict) else None
        confidence = result.get("confidence") if isinstance(result, dict) else None
    
    # Store in conversation history
    await memory.add_to_session(session_id, request.query, answer)
    
    return ChatResponse(
        answer=answer,
        citations=citations,
        agent_trace=agent_trace,
        timeline=timeline,
        report_markdown=report_markdown,
        confidence=confidence,
    )


@app.get("/session/{session_id}")
async def get_session(session_id: str):
    """Get conversation history for a session."""
    context = await memory.get_context_string(session_id)
    last_entity = await memory.get_last_entity(session_id)
    return {"session_id": session_id, "context": context, "last_entity": last_entity}


@app.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """Clear conversation history for a session."""
    await memory.clear_session(session_id)
    return {"message": "Session cleared", "session_id": session_id}


@app.post("/session/cleanup")
async def cleanup_sessions():
    """Manually trigger cleanup of old sessions."""
    removed = await memory.cleanup_old_sessions()
    return {"message": f"Removed {removed} old sessions"}


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
    session_id = None
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
                
                # Store in history after successful response
                if session_id:
                    # Extract answer from last event (would need to track this properly)
                    # For now, we'll just track the query
                    await memory.add_to_session(session_id, query, "[streaming response]")
                    
            except asyncio.TimeoutError:
                await websocket.send_text("error:timeout")
            except Exception as e:
                await websocket.send_text(f"error:internal_error:{str(e)}")
    except WebSocketDisconnect:
        return
