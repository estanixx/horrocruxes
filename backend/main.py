from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Horrocruxes API",
    description="Backend API for Horrocruxes project",
    version="1.0.0"
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