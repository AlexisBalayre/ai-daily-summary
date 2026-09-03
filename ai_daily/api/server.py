"""FastAPI server configuration."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ai_daily.api.chat import router as chat_router
from ai_daily.api.routes import router

app = FastAPI(
    title="AI Daily Summary API",
    description="API for the AI news aggregation platform",
    version="0.2.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "healthy"}


# Static files serving for frontend
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    # Serve static assets
    app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

    # SPA fallback - serve index.html for all non-API routes
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        index_path = static_dir / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return {"error": "Frontend not built"}
