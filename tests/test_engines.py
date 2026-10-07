"""El motor JavaScript de la interfaz (web/cyk-engine.js) debe dar EXACTAMENTE
el mismo resultado que el motor Python: mismos pasos de CNF, misma tabla,
mismo conteo de árboles y mismos árboles. Requiere Node.js (si no está, se omite).
"""

import itertools
import json
import random
import shutil
import subprocess
import unittest
from pathlib import Path

import cfg.export as export_mod
from cfg.export import analyze
from tests.test_cyk import random_grammar

ROOT = Path(__file__).resolve().parent.parent
TIMING = ("cnfNs", "ns", "reps", "firstNs")


def strip_timing(d):
    d = dict(d)
    for k in TIMING:
        d.pop(k, None)
    if d.get("result"):
        d["result"] = {k: v for k, v in d["result"].items() if k not in TIMING}
    return d


def build_cases():
    cases = []
    for path in sorted((ROOT / "grammars").glob("*.txt")):
        text = path.read_text(encoding="utf-8")
        cases.append((text, None))
    for gname, fname in [("ingles.txt", "frases_ingles.txt"), ("expresiones.txt", "frases_expresiones.txt")]:
        text = (ROOT / "grammars" / gname).read_text(encoding="utf-8")
        for line in (ROOT / "pruebas" / fname).read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.startswith("#"):
                cases.append((text, line))
    amb = (ROOT / "grammars" / "ambigua.txt").read_text(encoding="utf-8")
    for m in range(6):
        cases.append((amb, "id" + "+id*id" * m))
    ing = (ROOT / "grammars" / "ingles.txt").read_text(encoding="utf-8")
    rng = random.Random(11)
    words = "she he eats cooks a the cake fork with in cat oven drinks beer".split()
    for _ in range(150):
        cases.append((ing, " ".join(rng.choice(words) for _ in range(rng.randint(1, 9)))))
    rng = random.Random(99)
    for _ in range(150):
        g = random_grammar(rng)
        for n in range(5):
            for w in itertools.product("ab", repeat=n):
                cases.append((g, " ".join(w) if w else "ε"))
    # errores de gramática y de tokens
    cases += [("S -> ", "x"), ("esto no es una gramatica", "x"), ("S -> a S b | e", "a c b"),
              ("S -> S + T_PLUS | x\nT_PLUS -> y\nS0 -> z", "x+y+y"), ("A B -> c", None)]
    return cases


@unittest.skipUnless(shutil.which("node"), "Node.js no está instalado")
class TestEngines(unittest.TestCase):
    def test_js_engine_matches_python(self):
        export_mod.MIN_BENCH_NS = 0  # aquí no medimos tiempos
        cases = build_cases()
        proc = subprocess.run(["node", str(ROOT / "tests" / "run_js.js")], input=json.dumps(cases),
                              capture_output=True, text=True, check=True)
        js = json.loads(proc.stdout)
        self.assertEqual(len(js), len(cases))
        accepted = sum(1 for o in js if o.get("result") and o["result"]["accepted"])
        self.assertGreater(accepted, 500)  # que la comparación no sea trivial
        for (g, s), out_js in zip(cases, js):
            py = json.loads(json.dumps(analyze(g, s, 20)))
            self.assertEqual(strip_timing(out_js), strip_timing(py), f"gramática:\n{g}\nfrase: {s}")


if __name__ == "__main__":
    unittest.main()


class TestPresets(unittest.TestCase):
    def test_presets_js_is_up_to_date(self):
        import build_presets
        current = (ROOT / "web" / "presets.js").read_text(encoding="utf-8")
        self.assertEqual(current, build_presets.build(),
                         "web/presets.js está desactualizado: ejecute python3 build_presets.py")
