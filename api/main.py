from contextlib import asynccontextmanager
import time

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.config import get_settings
from core.database import init_db
from core.observability import get_logger, set_request_id, Timer, request_id_var

settings = get_settings()
logger = get_logger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized.")
    yield
    logger.info("Shutting down...")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", "")
    set_request_id(request_id)
    
    start_time = time.perf_counter()
    
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.exception("Unhandled exception in request")
        response = JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )
    
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    response.headers["X-Request-ID"] = request_id_var.get()
    response.headers["X-Response-Time-Ms"] = str(round(elapsed_ms, 2))
    
    logger.info(
        "%s %s - %s - %.2fms",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    
    return response


# Import and include routers
from api.routers import documents, analysis, audit

app.include_router(documents.router, prefix="/api/v1/documents", tags=["documents"])
app.include_router(analysis.router, prefix="/api/v1/analysis", tags=["analysis"])
app.include_router(audit.router, prefix="/api/v1/audit", tags=["audit"])


@app.get("/health")
def health_check():
    return {"status": "ok", "version": settings.app_version}
