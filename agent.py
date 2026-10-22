# agent.py - tool-calling CAD Reuse agent (Ollama Cloud).
# The agent has ONE tool. The tool matches by function + dimensions in plain Python (matching.py).
# The agent only decides whether to widen the size tolerance when nothing fits.
import os
from pathlib import Path
from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from matching import Matcher, DEFAULT_TOL_PCT

# -- Load settings from the local .env file (never committed to git) ----------
_env = Path(__file__).parent / ".env"
if _env.exists():
    for _line in _env.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

# -- Ollama Cloud ---------------------------------------------------------------
API_KEY = os.environ.get("OLLAMA_API_KEY", "")
HOST = os.environ.get("OLLAMA_HOST", "https://ollama.com")
MODEL = os.environ.get("OLLAMA_MODEL", "deepseek-v4.1-flash")

llm = ChatOllama(model=MODEL, base_url=HOST,
                 client_kwargs={"headers": {"Authorization": f"Bearer {API_KEY}"}},
                 temperature=0, reasoning=False)    # no thinking mode: faster, fewer tokens

matcher = Matcher(llm)    # loads the PLM parts once and reuses them for every requirement

SYSTEM = """You find an existing part to reuse for a required part.
Call find_matching_parts first, with the default tolerance.
If it finds no match, you may call it again with a larger tolerance_pct (for example 20, then 30; max 30).
The near_misses list shows how much tolerance each part would need.
Stop as soon as a match is found, or after 3 calls. When finished, reply with one word: done"""


def recommend(req_attributes: dict) -> str:
    """req_attributes: the SysML part's attributes. Returns the best PLM part, or 'No suitable part found'."""
    state = {}

    @tool
    def find_matching_parts(tolerance_pct: float = DEFAULT_TOL_PCT) -> dict:
        """Find the existing PLM part that best matches the required part by function,
        dimensions and material. tolerance_pct is how far a size may differ (default 10, max 30).
        Returns the best match, or the closest near misses with the tolerance each would need."""
        tol = min(max(float(tolerance_pct), 0.0), 30.0)
        res = matcher.find(req_attributes, tol)
        state["last"] = res
        if res["best"]:
            return {"best": res["best"], "tolerance_pct": tol}
        return {"best": None, "near_misses": res["near_misses"], "tolerance_pct": tol}

    agent = create_react_agent(llm, tools=[find_matching_parts], prompt=SYSTEM)
    agent.invoke({"messages": [("user", "Required part (SysML attributes): " + str(req_attributes))]},
                 config={"recursion_limit": 12})
    if "last" not in state:                        # the model skipped the tool: run it once ourselves
        state["last"] = matcher.find(req_attributes, DEFAULT_TOL_PCT)
    res = state["last"]
    best = res["best"]
    if not best:
        return "No suitable part found"
    return f"{best['item_number']} - {best['name']}  (score {best['score']}, tolerance {res['tolerance_pct']:g}%)"
