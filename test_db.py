# test_db.py — Test just the DB search (no LLM needed)
from graph import app, search_plm, filter_requirements, AgentState

state: AgentState = {
    "requirements": {
        "part_type": "Motor Mount",
        "function": "Secure BLDC motor to aluminum chassis",
        "mounting": "M8 bolts, 4-point",
        "load_capacity_kg": 50,
        "material": "Aluminum",
        "dimensions_mm": {"length": 120, "width": 80}
    },
    "candidates": [],
    "filtered": [],
    "scored": [],
    "recommendation": None
}

# Run just search + filter (no LLM)
state = search_plm(state)
state = filter_requirements(state)

print(f"\nCandidates from DB: {len(state['candidates'])}")
print(f"After hard gate: {len(state['filtered'])}")
print("\nTop 10 matches:")
for p in state["filtered"][:10]:
    print(f"  - {p['name']}  ({p['item_number']})")
