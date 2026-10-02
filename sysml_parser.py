# sysml_parser.py — read a SysML v2 file, extract each part's specs
import re

# attributes that map to our fixed requirement fields
_SPECIAL = {"partType", "function", "material", "mounting"}

def parse_sysml(path):
    """Return a list of requirements dicts, one per leaf part in the SysML file."""
    with open(path, "r") as f:
        text = f.read()

    parts = []
    # leaf part blocks only: body has no nested braces
    for m in re.finditer(r'part\s+(\w+)\s*:\s*\w+\s*\{([^{}]*)\}', text, re.DOTALL):
        name, body = m.group(1), m.group(2)
        attrs = {}
        # value assignments:  :>> key = "value";   or   :>> key = 20;
        for a in re.finditer(r':>>\s*(\w+)\s*=\s*"?([^";]+)"?\s*;', body):
            attrs[a.group(1).strip()] = a.group(2).strip()

        if not attrs:            # skips the assembly wrapper and part defs
            continue

        req = {
            "part_name": name,
            "part_type": attrs.get("partType", ""),
            "function": attrs.get("function", ""),
            "material": attrs.get("material", ""),
            "mounting": attrs.get("mounting", ""),
            "load_capacity_kg": attrs.get("loadRatingKn", ""),
            "dimensions_mm": {k: v for k, v in attrs.items() if k not in _SPECIAL},
        }
        parts.append(req)

    return parts


if __name__ == "__main__":
    import json, sys
    f = sys.argv[1] if len(sys.argv) > 1 else "gear_reducer.sysml"
    out = parse_sysml(f)
    print(f"Parsed {len(out)} parts from {f}\n")
    for p in out:
        print(json.dumps(p, indent=2))
