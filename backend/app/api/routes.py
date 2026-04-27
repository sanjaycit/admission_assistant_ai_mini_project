from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.web_rag import query_web_system
from app.core.entity_extractor import extract_query_entities
from app.services.llm_service import analyze_query

router = APIRouter()


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    answer: str
    sources: list[str]
    mode: str                          # "cache" | "web"
    entities: list[str]
    is_comparison: bool
    admission_guidance_type: str | None  # "eligibility" | "documents" | "deadlines" | "process" | "fees" | None


@router.post("/query", response_model=QueryResponse)
async def query_endpoint(body: QueryRequest):
    import asyncio

    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    entities = extract_query_entities(question)
    lower = question.lower()
    comparison = len(entities) >= 2 and any(t in lower for t in ["compare", "vs", "versus", "difference", "better", "which is", "both", "and"])

    # Analyze the query to get admission_guidance_type (no extra LLM call — same call as the pipeline)
    _, is_comparison_llm, admission_guidance_type = await asyncio.to_thread(analyze_query, question)

    # query_web_system is a blocking sync function (does web I/O + LLM calls).
    # Running it in a thread pool gives it its own event loop context so
    # nest_asyncio / loop-is-running conflicts never occur.
    raw = await asyncio.to_thread(query_web_system, question)

    # Split out answer and sources that the pipeline appended
    answer_part = raw
    sources: list[str] = []

    if "**Sources:**" in raw:
        answer_part, src_block = raw.split("**Sources:**", 1)
        answer_part = answer_part.strip()
        for line in src_block.strip().splitlines():
            line = line.strip().lstrip("- ").strip()
            if line:
                sources.append(line)

    # Determine mode heuristically (sources present = web, else cache)
    mode = "web" if sources else "cache"

    return QueryResponse(
        answer=answer_part,
        sources=sources,
        mode=mode,
        entities=entities,
        is_comparison=comparison or is_comparison_llm,
        admission_guidance_type=admission_guidance_type,
    )


@router.get("/health")
async def health():
    return {"status": "ok"}
