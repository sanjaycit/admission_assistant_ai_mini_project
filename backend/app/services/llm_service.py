"""
Module providing LLM integration via LangChain for query analysis and answer generation.
"""
import os
import json
from typing import List, Tuple
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from app.core.config import GEMINI_MODEL

load_dotenv(override=True)

def _get_llm(temperature: float = 0.0) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        temperature=temperature,
        google_api_key=os.getenv("GOOGLE_API_KEY"),
    )

def analyze_query(query: str) -> tuple[str, bool, str | None]:
    """
    Analyzes the user's search query to determine search intent and structure.

    Returns:
        tuple[str, bool, str | None]: A tuple containing:
          - rewritten_query: search-engine-optimized version of the query
          - is_comparison: True if the query compares two or more colleges
          - admission_guidance_type: the specific type of admission guidance
            being asked about, or None if not an admission guidance query.
            One of: "eligibility" | "documents" | "deadlines" | "process" | "fees"
    """
    llm = _get_llm()
    prompt = f"""Analyze the following query regarding college admissions.
Rewrite the query to be highly specific for a search engine, expanding acronyms and clarifying intent.
Determine if it's a comparison query (true/false).
Determine the admission_guidance_type — the specific category of admission guidance
the user is asking about. Use exactly one of these values, or null if it doesn't fit:
  - "eligibility"  → asking about minimum qualifications, marks, age, entrance exams required
  - "documents"    → asking about required certificates, papers to submit
  - "deadlines"    → asking about important dates, last date to apply, schedule
  - "process"      → asking about steps to apply, how to apply, checklist, procedure
  - "fees"         → asking about tuition fees, course fees, hostel charges, or total cost

Query: {query}

Output JSON ONLY:
{{
    "rewritten_query": "...",
    "is_comparison": false,
    "admission_guidance_type": null
}}"""
    try:
        response = llm.invoke(prompt)
        text = response.content.strip()
        if text.startswith("```json"):
            text = text[7:-3]
        elif text.startswith("```"):
            text = text[3:-3]
        result = json.loads(text)
        return (
            result.get("rewritten_query", query),
            result.get("is_comparison", False),
            result.get("admission_guidance_type") or None,
        )
    except Exception as e:
        print(f"  [LLM] analyze_query failed: {e}")
        return query, False, None


def is_context_sufficient(query: str, context: str) -> bool:
    """
    Uses the LLM model to validate if the cached context provides enough information.
    """
    llm = _get_llm()
    prompt = f"""Evaluate if the following context contains enough factual information to accurately answer the user's query.
Return JSON ONLY: {{"is_sufficient": true/false}}

Query: {query}

Context:
{context[:4000]}"""
    try:
        response = llm.invoke(prompt)
        text = response.content.strip()
        if text.startswith("```json"):
            text = text[7:-3]
        elif text.startswith("```"):
            text = text[3:-3]
        return json.loads(text).get("is_sufficient", False)
    except Exception:
        return False

def generate_answer(
    query: str,
    context: str,
    is_comparison: bool = False,
    admission_guidance_type: str | None = None,
) -> str:
    """
    Generates the final response using the Gemini model.
    The response format is determined by is_comparison and admission_guidance_type:
      - is_comparison=True              → Markdown comparison table
      - admission_guidance_type not None → Structured guidance (eligibility /
                                          documents / deadlines / process)
      - otherwise                       → Concise factual answer
    """
    mode = "comparison" if is_comparison else (admission_guidance_type or "factual")
    print(f"  [GENERATE] Generating answer from {len(context)} chars of context (mode: {mode})...")
    llm = _get_llm()

    if admission_guidance_type is not None and not is_comparison:
        prompt = f"""### TASK
Read the CONTEXT below and answer the QUESTION with a well-structured guide.
Use only information present in the context.

### CONTEXT
{context}

### QUESTION
{query}

### RULES
Structure your answer using only the relevant sections below:

## Eligibility Criteria
(bullet list of minimum qualifications)

## Required Documents
- [ ] Document 1
- [ ] Document 2
(use "- [ ]" prefix for every document so the user can check them off)

## Key Deadlines
(bullet list of important dates with labels)

## Steps to Apply
1. Step one
2. Step two
(numbered, action-oriented steps in order)

## Additional Notes
(any important tips or warnings — optional)

- Use **bold** for important terms.
- Add inline citations like [1] next to facts, corresponding to the source URLs listed in the context.
- Omit any section the context has no data for.
- Do NOT add caveats or say you don't know.

### ANSWER"""
    elif is_comparison:
        prompt = f"""### TASK
Read the CONTEXT below and answer the QUESTION by comparing the entities.
The context is from trusted web sources.

### CONTEXT
{context}

### QUESTION
{query}

### RULES
- Format your response as a Markdown table comparing the entities on key metrics (e.g., Fees, Ranking, Acceptance Rate).
- Add inline citations like [1] inside the table corresponding to the sources listed in the context.
- Do not add caveats or disclaimers.

### ANSWER"""
    else:
        prompt = f"""### TASK
Read the CONTEXT below and answer the QUESTION.
The context is from a trusted web source and contains the correct answer.
Do NOT say you don't have information — the answer IS in the context.
Extract numbers, dollar amounts, and figures exactly as written.

### CONTEXT
{context}

### QUESTION
{query}

### RULES
- Find and quote the specific numbers or facts that answer the question.
- If you see a table, read it row by row to find the relevant figure.
- Keep your answer concise (2-3 sentences max).
- Add inline citations like [1] immediately after the fact/number, mapped to the sources listed in the context.
- Do not add caveats or disclaimers.

### ANSWER"""

    response = llm.invoke(prompt)
    return response.content

def llm_rerank(query: str, docs: List[Tuple], top_n: int) -> List[Tuple]:
    """Uses the LLM model to select and rerank the most relevant knowledge chunks."""
    if not docs:
        return []
    
    llm = _get_llm()
    
    docs_text = ""
    for i, (doc, _) in enumerate(docs):
        docs_text += f"\n[Document {i}]\n{doc.page_content}\n"
        
    prompt = f"""You are a relevance ranking assistant.
Your task is to select the top {top_n} most relevant documents for answering the query.
Query: {query}

Documents:
{docs_text}

Output ONLY a JSON array of integers corresponding to the indices of the most relevant documents, in order of relevance. Example: [3, 0, 1]"""
    
    try:
        response = llm.invoke(prompt)
        text = response.content.strip()
        if text.startswith("```json"):
            text = text[7:-3]
        elif text.startswith("```"):
            text = text[3:-3]
        indices = json.loads(text)
        return [docs[i] for i in indices if i < len(docs)][:top_n]
    except Exception as e:
        print(f"  [DB] LLM Rerank failed: {e}. Returning original top {top_n}.")
        return docs[:top_n]
