"""FastAPI server configuration."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ai_daily.api.routes import router

app = FastAPI(
    title="AI Daily Summary API",
    description="API for the AI news aggregation platform",
    version="0.2.0",
)

# CORS middleware
# TODO: In production, configure allow_origins via environment variable (e.g., CORS_ORIGINS)
# instead of allowing all origins with "*"
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(router, prefix="/api/v1")


@app.get("/")
def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "ai-daily-summary"}


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "healthy"}
