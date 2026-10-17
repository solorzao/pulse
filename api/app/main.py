from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from . import agent
from .store import Store

logging.basicConfig(level=logging.INFO)

STATE: dict = {}


def get_store() -> Store:
    if "store" not in STATE:
        STATE["store"] = Store()
    return STATE["store"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_store()
    yield


app = FastAPI(title="Pulse API", version="0.1.0", lifespan=lifespan)

origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
origins += [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskBody(BaseModel):
    question: str
    topic: str | None = None
    region_id: str | None = None


@app.get("/health")
def health():
    return {"ok": True, "posts": get_store().post_count()}


@app.get("/topics")
def topics():
    return get_store().topics_summary()


@app.get("/globe")
def globe(topic: str, days: int = Query(30, ge=0, le=3650)):
    return get_store().globe(topic, days)


@app.get("/region")
def region(topic: str, region_id: str):
    return get_store().region(topic, region_id)


@app.get("/spread")
def spread():
    return get_store().spread()


@app.get("/trending")
def trending():
    return get_store().trending


@app.post("/ask")
async def ask(body: AskBody):
    if not body.question.strip():
        raise HTTPException(400, "question is required")
    return await run_in_threadpool(agent.ask, get_store(), body.question, body.topic, body.region_id)
