# graph.py — CAD Reuse Assistant (LangGraph pipeline)
from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Optional
import json, re

class AgentState(TypedDict):
    requirements: dict
    candidates: List[dict]
    filtered: List[dict]
    scored: List[dict]
    recommendation: Optional[str]

# ── Node 1: Input Requirements ──────────────────────────────
def input_requirements(state: AgentState) -> AgentState:
    return state

# ── Node 2: Search PLM ──────────────────────────────────────
def search_plm(state: AgentState) -> AgentState:
    import psycopg2
    conn = psycopg2.connect(
        host="localhost", port=5432,
        dbname="cascadia", user="postgres", password="postgres"
    )
    cur = conn.cursor()

    reqs = state["requirements"]
    keywords = []

    # Pull keywords from part_type and function description
    if reqs.get("part_type"):
        keywords.extend(reqs["part_type"].lower().split())
    if reqs.get("function"):
        # grab important nouns from the function description
        for w in reqs["function"].lower().split():
            if len(w) > 3 and w not in ("with", "that", "this", "from", "into"):
                keywords.append(w)
    if reqs.get("material"):
        for m in reqs["material"].lower().replace(" or ", ",").split(","):
            keywords.append(m.strip())

    # Remove duplicates, keep order
    seen = set()
    unique = []
    for k in keywords:
        if k not in seen:
            seen.add(k)
            unique.append(k)
    keywords = unique

    # Build ILIKE conditions — match ANY keyword in the part name
    conditions = " OR ".join(["name ILIKE %s"] * len(keywords))
    params = [f"%{kw}%" for kw in keywords]

    query = f"""
        SELECT id, item_number, name, item_type, attributes, state
        FROM items
        WHERE item_type IN ('Part', 'PhysicalPart')
          AND is_current = true
          AND ({conditions})
        ORDER BY name
        LIMIT 50
    """
    cur.execute(query, params)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    
    # Convert to dicts, handle non-serializable types
    candidates = []
    for row in rows:
        d = {}
        for col, val in zip(cols, row):
            if isinstance(val, (dict, list, str, int, float, bool, type(None))):
                d[col] = val
            else:
                d[col] = str(val)
        candidates.append(d)

    state["candidates"] = candidates
    conn.close()
    print(f"[search_plm] Found {len(candidates)} candidates for keywords: {keywords}")
    return state

# ── Node 3: Filter (Hard Constraint Gate) ────────────────────
def filter_requirements(state: AgentState) -> AgentState:
    reqs = state["requirements"]
    filtered = []

    for c in state["candidates"]:
        name_lower = c.get("name", "").lower()
        passes = True

        # Hard gate: if material specified, part name must hint at it
        if reqs.get("material"):
            materials = [m.strip().lower() for m in reqs["material"].replace(" or ", ",").split(",")]
            if not any(m in name_lower for m in materials):
                passes = False

        if passes:
            filtered.append(c)

    state["filtered"] = filtered
    print(f"[filter] {len(filtered)} of {len(state['candidates'])} passed hard gate")
    return state

# ── Node 4: Score Similarity (LLM) ──────────────────────────
def score_similarity(state: AgentState) -> AgentState:
    from langchain_ollama import OllamaLLM
    llm = OllamaLLM(model="llama3")

    for part in state["filtered"]:
        prompt = f"""You are a CAD reuse engineer. Score how well this existing part 
matches the required specifications. Return ONLY valid JSON, no other text.

Required specifications:
- Type: {state['requirements'].get('part_type', 'N/A')}
- Function: {state['requirements'].get('function', 'N/A')}
- Material: {state['requirements'].get('material', 'N/A')}
- Mounting: {state['requirements'].get('mounting', 'N/A')}
- Load capacity: {state['requirements'].get('load_capacity_kg', 'N/A')} kg
- Dimensions: {state['requirements'].get('dimensions_mm', 'N/A')}

Existing part name: "{part['name']}"
Part number: {part.get('item_number', 'N/A')}

Score each dimension from 0.0 to 1.0:
{{"function": <score>, "interface": <score>, "geometry": <score>, "material": <score>, "context": <score>}}"""

        raw = llm.invoke(prompt)
        # Try to parse JSON from LLM response
        try:
            match = re.search(r'\{[^}]+\}', raw)
            if match:
                scores = json.loads(match.group())
                # Calculate overall ourselves — average of 5 dimensions
                dims = ["function", "interface", "geometry", "material", "context"]
                dim_scores = [float(scores.get(d, 0)) for d in dims]
                valid = [s for s in dim_scores if 0 <= s <= 1]
                scores["overall"] = round(sum(valid) / len(valid), 2) if valid else 0.0
                part["scores"] = scores
            else:
                part["scores"] = {"overall": 0.0}
        except (json.JSONDecodeError, AttributeError, ValueError):
            part["scores"] = {"overall": 0.0}

        print(f"[score] {part['name'][:50]}... → overall={part['scores'].get('overall', 0)}")

    state["scored"] = sorted(
        state["filtered"],
        key=lambda x: x.get("scores", {}).get("overall", 0),
        reverse=True
    )
    return state

# ── Node 5: Explain ─────────────────────────────────────────
def explain(state: AgentState) -> AgentState:
    from langchain_ollama import OllamaLLM
    llm = OllamaLLM(model="llama3")

    if not state["scored"]:
        state["recommendation"] = "No suitable component found in the PLM database."
        return state

    top = state["scored"][0]
    runners = state["scored"][1:3]

    prompt = f"""You are a CAD reuse engineer. Explain your recommendation.

The engineer needs: {json.dumps(state['requirements'], indent=2)}

Best match: "{top['name']}" (Part #{top.get('item_number','N/A')})
Scores: {json.dumps(top.get('scores', {}))}

Runner-ups: {json.dumps([{'name': r['name'], 'scores': r.get('scores',{})} for r in runners], indent=2)}

Write 3-5 sentences explaining:
1. Why the top match is recommended
2. What fits well and what trade-offs exist
3. Whether modification might be needed"""

    state["recommendation"] = llm.invoke(prompt)
    return state

# ── Build Graph ──────────────────────────────────────────────
graph = StateGraph(AgentState)
graph.add_node("input_requirements", input_requirements)
graph.add_node("search_plm", search_plm)
graph.add_node("filter_requirements", filter_requirements)
graph.add_node("score_similarity", score_similarity)
graph.add_node("explain", explain)

graph.set_entry_point("input_requirements")
graph.add_edge("input_requirements", "search_plm")
graph.add_edge("search_plm", "filter_requirements")
graph.add_edge("filter_requirements", "score_similarity")
graph.add_edge("score_similarity", "explain")
graph.add_edge("explain", END)

app = graph.compile()
