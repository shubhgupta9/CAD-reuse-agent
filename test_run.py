# test_run.py — Run the CAD Reuse Agent pipeline
from graph import app

# Example: engineer needs a motor mount
result = app.invoke({
  "requirements": {
    "part_type": "Screw",
    "function": "Fasten aluminum bracket to steel frame",
    "mounting": "Socket head cap",
    "load_capacity_kg": 10,
    "material": "Steel",
    "dimensions_mm": {"length": 12.7}
},
    "candidates": [],
    "filtered": [],
    "scored": [],
    "recommendation": None
})

print("\n" + "="*60)
print("RECOMMENDATION")
print("="*60)
print(result["recommendation"])
print(f"\nTotal candidates found: {len(result['candidates'])}")
print(f"Passed hard gate: {len(result['filtered'])}")
print(f"Scored & ranked: {len(result['scored'])}")

if result["scored"]:
    print(f"\nTop match: {result['scored'][0]['name']}")
    print(f"Scores: {result['scored'][0].get('scores', {})}")
