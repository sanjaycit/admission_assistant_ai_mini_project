from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.web_rag import query_web_system, extract_query_entities, is_comparison_query

router = APIRouter()


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    answer: str
    sources: list[str]
    mode: str          # "cache" | "web"
    entities: list[str]
    is_comparison: bool


@router.post("/query", response_model=QueryResponse)
async def query_endpoint(body: QueryRequest):
    import asyncio

    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    entities = extract_query_entities(question)
    comparison = is_comparison_query(question)

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
        is_comparison=comparison,
    )


@router.get("/health")
async def health():
    return {"status": "ok"}
