#!/usr/bin/env python3
"""Genera web/presets.js a partir de grammars/*.txt y pruebas/*.txt.

Así la interfaz usa exactamente los mismos archivos que el programa de consola.
Ejecutar después de modificar alguna gramática o archivo de frases:

    python3 build_presets.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PRESETS = [
    ("ingles", "Inglés (enunciado)", "ingles.txt", "frases_ingles.txt"),
    ("expresiones", "Expresiones con ε", "expresiones.txt", "frases_expresiones.txt"),
    ("cnf_manual", "CNF hecha a mano", "expresiones_cnf_manual.txt", "frases_expresiones.txt"),
    ("ambigua", "Expresiones ambigua", "ambigua.txt", "frases_ambigua.txt"),
]


def read_sentences(path: Path):
    yes, no, cur = [], [], None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            cur = yes if "SÍ" in line else no
            continue
        if line.strip() and cur is not None:
            cur.append(line.strip())
    return yes, no


def build() -> str:
    data = []
    for pid, label, gfile, sfile in PRESETS:
        yes, no = read_sentences(ROOT / "pruebas" / sfile)
        data.append({
            "id": pid, "label": label, "file": f"grammars/{gfile}",
            "grammar": (ROOT / "grammars" / gfile).read_text(encoding="utf-8"),
            "yes": yes, "no": no,
        })
    return ("// Generado por build_presets.py a partir de grammars/ y pruebas/. No editar a mano.\n"
            "window.CYK_PRESETS = " + json.dumps(data, ensure_ascii=False, indent=2) + ";\n")


if __name__ == "__main__":
    out = ROOT / "web" / "presets.js"
    out.write_text(build(), encoding="utf-8")
    print(f"Escrito {out}")
