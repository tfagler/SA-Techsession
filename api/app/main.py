import os
import logging
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import get_settings
from app.routers import auth, quiz, search, sessions, settings


settings_obj = get_settings()
app = FastAPI(title=settings_obj.app_name, version='1.0.0')
logger = logging.getLogger(__name__)
logging.getLogger('app.services.ollama_client').setLevel(logging.INFO)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in settings_obj.cors_origins.split(',') if x.strip()],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

os.makedirs(settings_obj.docs_dir, exist_ok=True)

app.include_router(auth.router)
app.include_router(sessions.router)
app.include_router(quiz.router)
app.include_router(settings.router)
app.include_router(search.router)


def _sanitize_validation_errors(errors: list[dict]) -> list[dict]:
    sanitized: list[dict] = []
    for err in errors:
        sanitized.append({k: v for k, v in err.items() if k != 'input'})
    return sanitized


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={'detail': _sanitize_validation_errors(exc.errors())},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception('Unhandled server error: %s', request.url.path)
    return JSONResponse(status_code=500, content={'detail': 'Internal server error'})


@app.get('/healthz')
async def healthz():
    return {'ok': True}
