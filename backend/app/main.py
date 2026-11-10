from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.auth import router as auth_router
from app.api.onboarding import router as onboarding_router
from app.api.teams import router as teams_router
from app.core.config import settings

app = FastAPI(title="AI-buddy API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type", "X-Requested-With"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    # Mandatory custom header triggers CORS preflight; Origin allowlist blocks
    # cross-site form login/logout and cookie-authenticated mutations.
    if request.method not in ("GET", "HEAD", "OPTIONS") and (
        request.headers.get("origin") not in settings.allowed_origins
        or request.headers.get("x-requested-with") != "AI-buddy"
    ):
        return JSONResponse({"detail": "Недопустимый источник запроса"}, status_code=403)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


app.include_router(auth_router)
app.include_router(onboarding_router)
app.include_router(teams_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
