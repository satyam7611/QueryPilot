from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.routes import health, datasets, query

app = FastAPI(
    title="QueryPilot API",
    description="Production-ready API wrapper around the stateful, cyclic QueryPilot Text-to-SQL agent.",
    version="1.0.0"
)

# Configure CORS Middleware using dynamic Settings list
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers with clear prefixes
app.include_router(health.router, tags=["Health"])
app.include_router(datasets.router, prefix="/api", tags=["Datasets"])
app.include_router(query.router, prefix="/api", tags=["Query Engine"])

if __name__ == "__main__":
    import uvicorn
    # Start the server locally on port 8000
    uvicorn.run("web_main:app", host="0.0.0.0", port=8000, reload=True)
