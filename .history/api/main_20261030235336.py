from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import health, matches, teams

app = FastAPI(title="UCL Predictor API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

for router in (health.router, matches.router, teams.router):
    app.include_router(router)