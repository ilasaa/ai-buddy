from fastapi import FastAPI
from app.api.teams import router as teams_router

app = FastAPI(
    title="AI-buddy API",
    description="Backend ИИ-наставника для стажёров",
    version="0.1.0",
)
app.include_router(teams_router)

@app.get("/health")
async def health_check():
    return {"status": "ok"}