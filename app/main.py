"""
BRIDA AI System - Main Application (FIXED)
✅ FIXED: Exception handlers now return JSONResponse instead of dict
✅ FIXED: Added dashboard router
✅ FIXED: Visitor counter import corrected
Enhanced with Vector Search functionality and proper router configuration
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ===============================
# IMPORT ROUTERS
# ===============================
from app.routers.chatbot_router import router as chatbot_router
from app.routers.recommendations import router as recommendations_router
from app.routers.ai_insight import router as insight_router
from app.routers.ai_collaboration import router as collaboration_router
from app.routers.dashboard import router as dashboard_router 
from app.routers.auth import router as auth
from app.routers.visitor_counter import router as visitor_counter_router 
from app.routers import peta_inovasi

# ===============================
# IMPORT STARTUP HANDLER
# ===============================
from app.startup_handler import lifespan, router as admin_router


# ===============================
# CREATE FASTAPI APP
# ===============================
app = FastAPI(
    title="BRIDA AI System",
    description="AI-powered Innovation Management System for Jawa Timur",
    version="2.0.1",
    lifespan=lifespan,  # ✅ This handles database connection now
)


# ===============================
# CORS MIDDLEWARE
# ===============================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  
        "http://localhost:5173",   
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ❌ REMOVED: Duplicate @app.on_event("startup") and @app.on_event("shutdown")
# Database connection is now handled in lifespan context manager


# ===============================
# ROUTES
# ===============================


# Health check
@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "BRIDA AI System",
        "version": "2.0.1",
        "features": {
            "chatbot": "enabled",
            "vector_search": "enabled",
            "clustering": "enabled",
            "recommendations": "enabled",
            "ai_insights": "enabled",
            "dashboard": "enabled",
            "visitor_counter": "enabled",  # ✅ ADDED
        },
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    try:
        from app.database import database
        from app.services.vector_search_service import (
            _cache_loaded as vector_loaded,
            _inovasi_data_cache,
        )
        from app.services.clustering_service import get_cluster_cache

        cluster_data, cluster_last_run = get_cluster_cache()

        return {
            "status": "healthy",
            "database": "connected" if database.is_connected else "disconnected",
            "caches": {
                "vector": {
                    "loaded": vector_loaded,
                    "items": len(_inovasi_data_cache) if _inovasi_data_cache else 0,
                },
                "clustering": {
                    "loaded": len(cluster_data) > 0 if cluster_data else False,
                    "clusters": len(cluster_data) if cluster_data else 0,
                },
            },
        }
    except Exception as e:
        from app.database import database

        return {
            "status": "degraded",
            "database": "connected" if database.is_connected else "disconnected",
            "error": str(e),
        }


# ===============================
# INCLUDE ROUTERS
# ===============================

# Dashboard routes (✅ ADDED FIRST - untuk endpoint /dashboard/*)
app.include_router(dashboard_router)

# Chatbot routes
app.include_router(chatbot_router)

# Recommendation routes
app.include_router(
    recommendations_router,
    prefix="/api/recommendations",
)

# AI Insight routes
app.include_router(insight_router)

# AI Collaboration routes
app.include_router(collaboration_router)

# Admin routes
app.include_router(admin_router)

# Login
app.include_router(auth)

# Visitor Counter 
app.include_router(visitor_counter_router)

# Peta Inovasi
app.include_router(peta_inovasi.router)

# ===============================
# ADDITIONAL ENDPOINTS (Optional)
# ===============================


# Test vector search directly (for debugging)
@app.get("/test/vector-search")
async def test_vector_search(query: str):
    """
    Test vector search functionality directly
    Example: /test/vector-search?query=POP SURGA
    """
    try:
        from app.services.vector_search_service import vector_search_inovasi

        results = await vector_search_inovasi(query, top_k=5)

        return {
            "query": query,
            "results": results,
            "count": len(results),
        }
    except Exception as e:
        return {
            "error": str(e),
            "query": query,
        }


# Test hybrid search directly (for debugging)
@app.get("/test/hybrid-search")
async def test_hybrid_search(query: str):
    """
    Test hybrid search functionality directly
    Example: /test/hybrid-search?query=POP SURGO
    """
    try:
        from app.services.vector_search_service import hybrid_search_inovasi
        from app.services.chatbot_service import extract_keywords

        keywords = extract_keywords(query)
        result = await hybrid_search_inovasi(query, keywords, top_k=3)

        return {
            "query": query,
            "keywords": keywords,
            "result": result,
        }
    except Exception as e:
        return {
            "error": str(e),
            "query": query,
        }


# ===============================
# ERROR HANDLERS (✅ FIXED - Now using JSONResponse)
# ===============================


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception):
    """Handle 404 Not Found errors"""
    return JSONResponse(
        status_code=404,
        content={
            "status": "error",
            "message": "Endpoint not found",
            "path": str(request.url),
        },
    )


@app.exception_handler(500)
async def server_error_handler(request: Request, exc: Exception):
    """Handle 500 Internal Server errors"""
    import traceback

    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "Internal server error",
            "details": str(exc),
            "traceback": traceback.format_exc() if app.debug else None,
        },
    )


# ✅ ADDED: General exception handler for all other exceptions
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions"""
    import traceback

    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "An unexpected error occurred",
            "details": str(exc),
            "path": str(request.url),
            "traceback": traceback.format_exc() if app.debug else None,
        },
    )


# ===============================
# RUN APPLICATION
# ===============================
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Disable in production
        log_level="info",
    )