# matching.py - find the best existing part by FUNCTION + DIMENSIONS, not by name.
# The LLM only READS part names into specs. All pass/fail and scoring is plain Python.
import copy, hashlib, json, math, os, re, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

CACHE_FILE = Path(__file__).parent / "spec_cache.json"

# -- Rules are data (so there are no if-statements per part type) -------------
DEFAULT_TOL_PCT = 10   # how far a size may differ and still count as fitting
EXACT_KEYS = {"thread_size", "teeth", "module_mm", "pressure_angle_deg", "standard"}  # must match exactly
MIN_KEYS = {"load_rating_kn", "load_capacity_kn", "torque_rating_nm", "strength_mpa"}  # part must be >= required
MAX_KEYS = {"mass_kg"}                                                                # part must be <= required
STRICT_KEYS = {"bore_diameter_mm", "shaft_diameter_mm", "inner_diameter_mm", "diameter_mm"}  # fit-critical sizes
STRICT_TOL = 0.02      # these may differ by 2 percent at most, even when the tolerance is widened
SAME_GROUP_SIM = 0.9   # function score when the part kind differs but does the same job (bolt vs screw)
WEIGHTS = {"function": 0.3, "dimensions": 0.5, "material": 0.2}
UNKNOWN = 0.5          # score for a value the part does not state
MIN_VERIFIED = 0.4     # at least this share of the required values must be checkable
BATCH = 20             # parts read per LLM call
WORKERS = int(os.environ.get("MATCH_WORKERS", "4"))   # LLM calls running at the same time
REQ_SPECIAL = {"part_type", "function", "material"}

EXTRACT_PROMPT = """You read engineering part descriptions and turn them into specs.
For every part below return one JSON object. Reply with ONLY a JSON list, nothing else.
Keys:
- "id": the id given
- "category": ONE lowercase singular noun for what the part is (screw, nut, washer, key, gear, shaft, bearing, seal, housing, bracket, motor, tire ...)
- "type": short full type, e.g. "socket head cap screw"
- "function": 3 to 6 words on what it does, e.g. "fastens parts together"
- "material": lowercase, "" if unknown. A2 or A4 mean "stainless steel". Use "aluminum" for aluminium.
- "attrs": object with the part's properties. Use these names when they apply:
  length_mm, width_mm, height_mm, thickness_mm, diameter_mm, bore_diameter_mm, outer_diameter_mm,
  shaft_diameter_mm, thread_size (like "M6", no pitch), teeth, module_mm, pressure_angle_deg,
  load_rating_kn, mass_kg, head_type. Numbers are plain numbers in mm, kg, kN or degrees.
  Any other property: snake_case name with a unit suffix. Only include what the text states
  or what the named standard fixes for certain. Never guess.
Parts:
"""

GROUP_PROMPT = """Below is a list of part category words from an engineering parts catalogue.
Group the words that name parts which do the same job and can replace each other in a design.
Example: "screw" and "bolt" are one group. "nut", "washer", "shaft", "bearing" and "gear" are each their own group.
Generic words such as part, item, assembly or component stay alone.
Every word must be in exactly one group. Reply with ONLY a JSON list of lists of words.
Words:
"""


# -- small helpers -------------------------------------------------------------
def snake(name):
    s = re.sub(r"(?<!^)(?=[A-Z])", "_", str(name).strip())
    return re.sub(r"_+", "_", s.replace(" ", "_").replace("-", "_")).lower()

def num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip())
    except ValueError:
        return None

def norm_val(v):
    n = num(v)
    return n if n is not None else str(v).strip().lower()

def tokens(s):
    return set(re.findall(r"[a-z0-9]+", str(s).lower()))

def jaccard(a, b):
    ta, tb = tokens(a), tokens(b)
    return len(ta & tb) / len(ta | tb) if ta | tb else 0.0

def empty_spec():
    return {"category": "", "type": "", "function": "", "material": "", "attrs": {}}

def material_score(r, c):
    if not r or not c:
        return UNKNOWN
    if r == c:
        return 1.0
    return 0.6 if tokens(r) & tokens(c) else 0.0     # "steel" vs "stainless steel" shares a word

def clean_spec(o):
    attrs = {}
    for k, v in (o.get("attrs") or {}).items():
        if v is None or v == "":
            continue
        attrs[snake(k)] = norm_val(v)
    return {"category": str(o.get("category", "")).strip().lower(),
            "type": str(o.get("type", "")).strip().lower(),
            "function": str(o.get("function", "")).strip().lower(),
            "material": str(o.get("material", "")).strip().lower(),
            "attrs": attrs}

def parse_nested(raw):
    s = str(raw)
    a, b = s.find("["), s.rfind("]")
    if a < 0 or b < a:
        raise ValueError("no JSON list")
    return [[str(w) for w in g] for g in json.loads(s[a:b + 1]) if isinstance(g, list)]

def parse_json_list(raw):
    s = str(raw)
    a, b = s.find("["), s.rfind("]")
    if a < 0 or b < a:
        raise ValueError("no JSON list")
    try:
        data = json.loads(s[a:b + 1])
    except json.JSONDecodeError as e:
        raise ValueError(str(e))
    return [d for d in data if isinstance(d, dict)]


class Matcher:
    def __init__(self, llm, candidates=None, cache_file=CACHE_FILE):
        """candidates: optional list of {item_number, name, attributes}; default reads Cascadia."""
        self.llm = llm
        self._raw = candidates
        self._cands = None
        self._group = {}
        self.cache_file = Path(cache_file)
        self._lock = threading.Lock()
        self.cache = {"specs": {}, "groups": {}}
        if self.cache_file.exists():
            try:
                self.cache.update(json.loads(self.cache_file.read_text()))
            except Exception:
                pass
        self.cache.setdefault("specs", {})
        self.cache.setdefault("groups", {})
        self.cache.pop("emb", None)

    # -- cache -----------------------------------------------------------------
    def _save(self):
        with self._lock:
            self.cache_file.write_text(json.dumps(self.cache))

    # -- 1. the LLM reads text into specs (cached, batched) ---------------------
    def _ask(self, batch):
        prompt = EXTRACT_PROMPT + json.dumps([{"id": i, "text": t} for i, (_, t) in enumerate(batch)])
        raw = self.llm.invoke(prompt)
        got = {}
        for o in parse_json_list(getattr(raw, "content", raw)):
            try:
                i = int(o.get("id"))
            except (TypeError, ValueError):
                continue
            if 0 <= i < len(batch):
                got[i] = clean_spec(o)
        return got

    def _extract_batch(self, batch):
        try:
            got = self._ask(batch)
        except ValueError:
            got = {}
        with self._lock:
            for i, spec in got.items():
                self.cache["specs"][batch[i][0]] = spec
        missing = [b for i, b in enumerate(batch) if i not in got]
        if not missing:
            return
        if len(batch) == 1:
            with self._lock:
                self.cache["specs"][batch[0][0]] = {**empty_spec(), "failed": True}
        elif len(missing) == len(batch):          # nothing readable: split and retry
            mid = len(batch) // 2
            self._extract_batch(batch[:mid])
            self._extract_batch(batch[mid:])
        else:
            self._extract_batch(missing)

    def _extract(self, items):
        """items: list of (key, text). Fills the spec cache for keys not read yet."""
        specs = self.cache["specs"]
        todo = [(k, t) for k, t in items if k not in specs or specs[k].get("failed")]
        batches = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]
        if batches:
            with ThreadPoolExecutor(WORKERS) as pool:
                futures = [pool.submit(self._extract_batch, b) for b in batches]
                for n, f in enumerate(as_completed(futures), 1):
                    f.result()                      # raises if the LLM call itself failed
                    self._save()                    # progress is kept after every batch
                    if len(batches) > 1:
                        print(f"[matching] read {n}/{len(batches)} batches", flush=True)
        return len(todo)

    # -- 2. function groups: which kinds of part do the same job (one LLM call, cached) ----
    def _ensure_groups(self, categories):
        words = sorted({w for w in categories if w})
        h = hashlib.sha1("|".join(words).encode()).hexdigest()[:12]
        g = self.cache["groups"].get(h)
        if g is None:
            lists = []
            try:
                raw = self.llm.invoke(GROUP_PROMPT + json.dumps(words))
                lists = parse_nested(getattr(raw, "content", raw))
            except ValueError:
                print("[matching] could not group part kinds; only the exact same kind will match")
            g, nid = {}, len(lists)
            for i, grp in enumerate(lists):
                for w in grp:
                    w = w.strip().lower()
                    if w in words and w not in g:
                        g[w] = i
            for w in words:
                if w not in g:
                    g[w] = nid
                    nid += 1
            self.cache["groups"][h] = g
            self._save()
        self._group = g

    def _func_sim(self, req, c):
        rc, cc = req["category"], c["category"]
        if rc and rc == cc:
            return 1.0
        if rc and cc and self._group.get(rc) is not None and self._group.get(rc) == self._group.get(cc):
            return SAME_GROUP_SIM
        return 0.0

    # -- 3. load the PLM parts ---------------------------------------------------
    def _read_db(self):
        import psycopg2
        conn = psycopg2.connect(host=os.environ.get("PGHOST", "localhost"),
                                port=os.environ.get("PGPORT", "5432"),
                                dbname=os.environ.get("PGDATABASE", "cascadia"),
                                user=os.environ.get("PGUSER", "postgres"),
                                password=os.environ.get("PGPASSWORD", "postgres"))
        cur = conn.cursor()
        cur.execute("SELECT item_number, name, attributes FROM items "
                    "WHERE item_type IN ('Part','PhysicalPart') AND is_current = true")
        rows = [{"item_number": r[0], "name": r[1], "attributes": r[2]} for r in cur.fetchall()]
        conn.close()
        return rows

    def _load(self):
        if self._cands is not None:
            return
        rows = self._raw if self._raw is not None else self._read_db()
        items = [(f"{r['item_number']}|{r['name']}", r["name"]) for r in rows]
        new = sum(1 for k, _ in items if k not in self.cache["specs"] or self.cache["specs"][k].get("failed"))
        if new:
            print(f"[matching] reading specs of {new} parts with the LLM (one time, then cached)...")
        self._extract(items)
        cands = []
        for r, (key, _) in zip(rows, items):
            spec = copy.deepcopy(self.cache["specs"][key])
            attrs = r.get("attributes") or {}
            if isinstance(attrs, str):
                try:
                    attrs = json.loads(attrs)
                except ValueError:
                    attrs = {}
            for k, v in attrs.items():                 # real PLM attributes win over name-reading
                if v is not None and v != "":
                    spec["attrs"][snake(k)] = norm_val(v)
            spec["item_number"], spec["name"] = r["item_number"], r["name"]
            cands.append(spec)
        self._cands = cands
        self._ensure_groups({c["category"] for c in cands})
        self._save()

    # -- 4. the requirement (from SysML) ------------------------------------------
    def _req_parts(self, attributes):
        a = {snake(k): v for k, v in attributes.items()}
        ptype = str(a.get("part_type", "")).strip().lower()
        func = str(a.get("function", "")).strip().lower()
        return a, ptype, func, f"{ptype}: {func}".strip(": ")

    def warm(self, list_of_attributes):
        """Read the PLM parts and all requirements up front (fewer, batched LLM calls)."""
        self._load()
        items = []
        for attrs in list_of_attributes:
            text = self._req_parts(attrs)[3]
            items.append((f"REQ|{text}", text))
        self._extract(items)
        cats = {self.requirement_spec(a)["category"] for a in list_of_attributes}
        self._ensure_groups(set(self._group) | cats)

    def requirement_spec(self, attributes):
        a, ptype, func, text = self._req_parts(attributes)
        key = f"REQ|{text}"
        self._extract([(key, text)])
        ex = self.cache["specs"].get(key) or empty_spec()
        category = ex["category"] or (ptype.split()[-1] if ptype else "")
        return {"category": category, "type": ptype or ex["type"], "function": func or ex["function"],
                "material": str(a.get("material", "")).strip().lower(),
                "attrs": {k: norm_val(v) for k, v in a.items() if k not in REQ_SPECIAL and v not in (None, "")}}

    # -- 5. compare one part with the requirement (plain Python) -------------------
    def _compare(self, req, c, tol):
        fs = self._func_sim(req, c)
        if fs <= 0:
            return None                                  # a different kind of part
        fails, parts, verified, needs, blocked = [], [], 0, 0.0, False
        for k, rv in req["attrs"].items():
            cv = c["attrs"].get(k)
            if cv is None:
                parts.append(UNKNOWN)                    # part does not state it
                continue
            verified += 1
            rn, cn = num(rv), num(cv)
            if rn is not None and cn is not None:
                if k in MIN_KEYS or k in MAX_KEYS:
                    good = cn >= rn - 1e-9 if k in MIN_KEYS else cn <= rn + 1e-9
                    parts.append(1.0 if good else 0.0)
                    if not good:
                        fails.append(f"{k} {cn:g} vs {rn:g}")
                        blocked = True
                else:
                    dev = abs(cn - rn) / max(abs(rn), 1e-9)
                    strict = k in STRICT_KEYS
                    t = 0.0 if k in EXACT_KEYS else (min(tol, STRICT_TOL) if strict else tol)
                    if dev <= t + 1e-9:
                        parts.append(1.0 if dev < 1e-9 else 1.0 - 0.5 * dev / t)
                    else:
                        parts.append(max(0.0, 1.0 - dev))
                        fails.append(f"{k} {cn:g} vs {rn:g}")
                        if k in EXACT_KEYS or strict:
                            blocked = True                     # widening the tolerance cannot fix this
                        else:
                            needs = max(needs, dev)
            elif k in EXACT_KEYS:
                same = str(cv).lower() == str(rv).lower()
                parts.append(1.0 if same else 0.0)
                if not same:
                    fails.append(f"{k} {cv} vs {rv}")
                    blocked = True
            else:
                parts.append(jaccard(rv, cv))            # words like head type: soft
        ms = material_score(req["material"], c["material"])
        if ms == 0.0:
            fails.append(f"material {c['material']} vs {req['material']}")
            blocked = True
        total = len(req["attrs"])
        if total and verified / total < MIN_VERIFIED:
            fails.append("too few values to check")
            blocked = True
        dim = sum(parts) / len(parts) if parts else UNKNOWN
        score = WEIGHTS["function"] * fs + WEIGHTS["dimensions"] * dim + WEIGHTS["material"] * ms
        return {"item_number": c["item_number"], "name": c["name"], "score": round(score, 3),
                "failures": fails, "passed": not fails,
                "needs_pct": None if blocked else (math.ceil(needs * 100) if fails else 0)}

    def find(self, req_attributes, tolerance_pct=DEFAULT_TOL_PCT):
        self._load()
        req = self.requirement_spec(req_attributes)
        if req["category"] and req["category"] not in self._group:
            self._ensure_groups(set(self._group) | {req["category"]})
        tol = max(float(tolerance_pct), 0.0) / 100
        results = [r for r in (self._compare(req, c, tol) for c in self._cands) if r]
        passed = sorted((r for r in results if r["passed"]), key=lambda r: -r["score"])
        near = sorted((r for r in results if not r["passed"]), key=lambda r: (len(r["failures"]), -r["score"]))
        pick = lambda r: {"item_number": r["item_number"], "name": r["name"], "score": r["score"]}
        return {"best": pick(passed[0]) if passed else None,
                "near_misses": [{"item_number": r["item_number"], "name": r["name"],
                                 "failures": r["failures"], "needs_tolerance_pct": r["needs_pct"]}
                                for r in near[:3]],
                "checked": len(self._cands), "same_function": len(results),
                "passed": len(passed), "tolerance_pct": float(tolerance_pct)}
