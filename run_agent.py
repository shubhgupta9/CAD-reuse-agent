# run_agent.py - SysML input -> agent -> best matching PLM part for each component
from agent import recommend, matcher
from sysml_parser import parse_sysml

parts = parse_sysml("gear_reducer.sysml")
matcher.warm([p["attributes"] for p in parts])      # one-time reading of PLM parts + requirements
for part in parts:
    print(f"{part['part_name']}: {recommend(part['attributes'])}", flush=True)
