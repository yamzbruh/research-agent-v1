import json
import os
from dotenv import load_dotenv
load_dotenv()
from typing import Dict, List, Optional, TypedDict
from uuid import uuid4

import anthropic
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from agent import summarize, search_web


class ResearchState(TypedDict):
    topic: str
    sources: List[str]
    summaries: List[str]
    awaiting_approval: bool


class JobData(TypedDict):
    state: ResearchState
    approvals: List[Optional[bool]]


class ResearchRequest(BaseModel):
    topic: str


class ApproveRequest(BaseModel):
    source_index: int
    approved: bool


app = FastAPI(title="Research Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000",
    "https://research-agent-v1-tau.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple in-memory store: {job_id: JobData}
jobs: Dict[str, JobData] = {}


@app.post("/research")
def create_research_job(payload: ResearchRequest):
    topic = payload.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Topic cannot be empty.")

    initial_state: ResearchState = {
        "topic": topic,
        "sources": [],
        "summaries": [],
        "awaiting_approval": False,
    }

    try:
        searched_state = search_web(initial_state)
        summarized_state = summarize(searched_state)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Research failed: {exc}") from exc

    job_id = str(uuid4())
    jobs[job_id] = {
        "state": summarized_state,
        "approvals": [None for _ in summarized_state["sources"]],
    }

    return {"job_id": job_id}


@app.get("/research/{job_id}/sources")
def get_sources(job_id: str):
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    state = job["state"]
    approvals = job["approvals"]
    items = []
    for idx, (source, summary) in enumerate(zip(state["sources"], state["summaries"])):
        items.append(
            {
                "source_index": idx,
                "source": source,
                "summary": summary,
                "approved": approvals[idx],
            }
        )

    return {"topic": state["topic"], "items": items}


@app.post("/research/{job_id}/approve")
def approve_source(job_id: str, payload: ApproveRequest):
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    index = payload.source_index
    approvals = job["approvals"]
    if index < 0 or index >= len(approvals):
        raise HTTPException(status_code=400, detail="source_index out of range.")

    approvals[index] = payload.approved
    return {"job_id": job_id, "source_index": index, "approved": payload.approved}


@app.get("/research/{job_id}/report")
def get_report(job_id: str):
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    state = job["state"]
    approvals = job["approvals"]

    approved_items = []
    for source, summary, approved in zip(state["sources"], state["summaries"], approvals):
        if approved is True:
            approved_items.append({"source": source, "summary": summary})

    return {"topic": state["topic"], "approved_items": approved_items}


@app.post("/research/{job_id}/synthesize")
def synthesize_essay(job_id: str):
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not anthropic_api_key:
        raise HTTPException(status_code=500, detail="Missing ANTHROPIC_API_KEY in environment.")

    state = job["state"]
    approvals = job["approvals"]

    approved_items = []
    for source, summary, approved in zip(state["sources"], state["summaries"], approvals):
        if approved is True:
            approved_items.append({"source": source, "summary": summary})

    if not approved_items:
        raise HTTPException(status_code=400, detail="No approved sources to synthesize.")

    topic = state["topic"]
    approved_items_str = json.dumps(approved_items, ensure_ascii=False)

    prompt = (
        "You are a research assistant. Based on the following approved sources "
        "and their summaries, write a comprehensive, well-structured essay "
        "synthesizing all the key findings. Remove duplicate information, "
        "identify common themes, and present the information as a cohesive "
        "narrative. Include an introduction, main body with key findings, "
        "and a conclusion.\n\n"
        f"Topic: {topic}\n"
        f"Sources and Summaries: {approved_items_str}"
    )

    client = anthropic.Anthropic(api_key=anthropic_api_key)
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    text_chunks = [
        block.text for block in message.content if getattr(block, "type", "") == "text"
    ]
    essay = " ".join(text_chunks).strip()

    return {"essay": essay}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
