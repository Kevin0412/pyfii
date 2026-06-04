from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from .config import settings
from .errors import AppError
from .routers.projects import router as projects_router
from .schemas import AppConfigResponse


app = FastAPI(title=settings.app_title, default_response_class=ORJSONResponse)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> ORJSONResponse:
    return ORJSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True}


@app.get("/api/config", response_model=AppConfigResponse)
async def app_config() -> AppConfigResponse:
    return AppConfigResponse(
        title=settings.app_title,
        features={"local_project_import": settings.enable_local_project_import},
        deployment={
            "icp_beian": settings.icp_beian,
            "icp_url": settings.icp_url,
            "gongan_beian": settings.gongan_beian,
            "gongan_url": settings.gongan_url,
        },
    )


app.include_router(projects_router, prefix="/api/projects", tags=["projects"])
