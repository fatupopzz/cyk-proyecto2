#!/usr/bin/env python3
"""Mide el tiempo del CYK contra la longitud n de la entrada y grafica.

    python benchmark.py            # imprime la tabla y genera ejemplos/tiempos_cyk.png

Se usan entradas que crecen de forma controlada:
  * inglés:       she eats a cake (with a fork)^k        n = 4 + 3k
  * expresiones:  id (+ id)^k                            n = 1 + 2k
  * ambigua:      id (+ id)^k  con E -> E + E | ...      (Catalan(k) árboles)
"""

import statistics
from pathlib import Path

from cfg import cyk, load_grammar, to_cnf

ROOT = Path(__file__).resolve().parent
REPS = 7

CASES = [
    ("Inglés (enunciado)", "ingles.txt", lambda k: "she eats a cake".split() + ["with", "a", "fork"] * k),
    ("Expresiones (con ε)", "expresiones.txt", lambda k: ["id"] + ["+", "id"] * k),
    ("Expresiones ambigua", "ambigua.txt", lambda k: ["id"] + ["+", "id"] * k),
]


def measure(cnf, w):
    cyk(cnf, w)  # calentamiento
    return statistics.median(cyk(cnf, w).elapsed_ns for _ in range(REPS))


def main():
    results = {}
    for label, gfile, make in CASES:
        cnf, _ = to_cnf(load_grammar(ROOT / "grammars" / gfile))
        pts = []
        for k in range(0, 40):
            w = make(k)
            if len(w) > 80:
                break
            ns = measure(cnf, w)
            r = cyk(cnf, w)
            pts.append((len(w), ns / 1e6, r.accepted, r.tree_count))
        results[label] = pts

    print(f"{'gramática':<22} {'n':>4} {'tiempo (ms)':>12} {'árboles':>22}")
    for label, pts in results.items():
        for n, ms, ok, cnt in pts[::3]:
            print(f"{label:<22} {n:>4} {ms:>12.3f} {cnt:>22}")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("(instale matplotlib para generar la gráfica)")
        return

    colors = ["#2a78d6", "#eb6834", "#1baf7a"]  # orden categórico fijo
    fig, ax = plt.subplots(figsize=(8, 4.8), dpi=150)
    for (label, pts), col in zip(results.items(), colors):
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        ax.plot(xs, ys, color=col, lw=2, marker="o", ms=4, label=label)
    # referencia n³ anclada en el último punto de inglés
    n_ref, t_ref = results[CASES[0][0]][-1][:2]
    xs = list(range(4, 82))
    ax.plot(xs, [t_ref * (x / n_ref) ** 3 for x in xs], color="#999999", lw=1.2, ls="--",
            label="referencia ∝ n³")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("n (número de tokens)")
    ax.set_ylabel("tiempo del CYK (ms, mediana de 7)")
    ax.set_title("Tiempo del CYK vs longitud de la entrada", loc="left", fontsize=12)
    ax.grid(True, which="major", color="#e5e5e5", lw=0.8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    fig.tight_layout()
    out = ROOT / "ejemplos" / "tiempos_cyk.png"
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out)
    print(f"Gráfica guardada en {out}")


if __name__ == "__main__":
    main()
