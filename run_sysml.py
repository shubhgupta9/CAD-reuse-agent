# run_sysml.py — run the CAD Reuse Agent on every part in a SysML file
from graph import app
from sysml_parser import parse_sysml

parts = parse_sysml("gear_reducer.sysml")
print(f"Loaded {len(parts)} parts from gear_reducer.sysml\n")

for req in parts:
    name = req.pop("part_name")
    print("=" * 60)
    print(f"PART: {name}  ({req['part_type']}, {req['material']})")
    print("=" * 60)

    result = app.invoke({
        "requirements": req,
        "candidates": [], "filtered": [], "scored": [],
        "recommendation": None,
    })

    print(f"candidates: {len(result['candidates'])} | "
          f"passed gate: {len(result['filtered'])} | "
          f"scored: {len(result['scored'])}")
    if result["scored"]:
        top = result["scored"][0]
        print(f"TOP MATCH: {top['name']}  (overall={top.get('scores',{}).get('overall')})")
    print("RECOMMENDATION:")
    print(result["recommendation"])
    print()
