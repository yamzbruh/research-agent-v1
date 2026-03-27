from dotenv import load_dotenv
load_dotenv()
from typing import Dict, List, Optional, TypedDict
from uuid import uuid4

from fastapi import FastAPI, HTTPException
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


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
