#!/usr/bin/env python3
"""Proyecto 2, Teoría de la Computación: CYK sobre una CFG cualquiera.

Uso rápido:
    python main.py grammars/ingles.txt "She eats a cake with a fork"
    python main.py grammars/expresiones.txt "(id+id)*id" --pasos --tabla
    python main.py grammars/ingles.txt -f pruebas/frases_ingles.txt
    python main.py grammars/ingles.txt              # modo interactivo
"""

from __future__ import annotations

import argparse
import re
import statistics
import sys
import time
from pathlib import Path

from cfg import (GrammarError, TokenizeError, cyk, format_table, load_grammar,
                 to_cnf, tokenize)
from cfg.tree import render_dot, to_ascii, to_bracket, to_dot

COLOR = sys.stdout.isatty()


def c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if COLOR else text


def bold(t): return c(t, "1")
def green(t): return c(t, "1;32")
def red(t): return c(t, "1;31")
def dim(t): return c(t, "2")


def fmt_time(ns: int | float) -> str:
    if ns < 1_000:
        return f"{ns:.0f} ns"
    if ns < 1_000_000:
        return f"{ns / 1_000:.2f} µs"
    if ns < 1_000_000_000:
        return f"{ns / 1_000_000:.3f} ms"
    return f"{ns / 1_000_000_000:.3f} s"


def banner(title: str) -> str:
    return bold(f"\n=== {title} " + "=" * max(0, 60 - len(title)))


_SLUG = {"(": " lp ", ")": " rp ", "+": " mas ", "*": " por ", "-": " menos ", "/": " div "}


def slug(text: str) -> str:
    s = "".join(_SLUG.get(ch, ch) for ch in text.strip().lower())
    s = re.sub(r"[^\w]+", "_", s).strip("_")
    return (s or "vacia")[:50]


def print_steps(steps) -> None:
    for n, st in enumerate(steps):
        print(banner(f"{n}. {st.key}: {st.title}"))
        for note in st.notes:
            print(dim("  · " + note))
        print(st.grammar.to_text())
        print(dim(f"  ({len(st.grammar.nonterminals)} no terminales, {st.grammar.size()} producciones)"))


def run_sentence(sentence: str, g, cnf, args, out_dir: Path | None) -> tuple[bool, int, list[str] | None]:
    """Analiza una frase e imprime el resultado. Devuelve (aceptada, tiempo_ns, tokens)."""
    print(banner(f"w = {sentence}"))
    try:
        tokens = tokenize(sentence, g.terminals)
    except TokenizeError as e:
        # Un símbolo fuera del alfabeto: w ∉ L(G) sin necesidad de llenar la tabla.
        print(f"Tokens:    {red('error')}: {e}")
        print(f"Resultado: {red('NO')}  (la palabra no pertenece al alfabeto Σ de la gramática)")
        return False, 0, None

    print("Tokens:    [" + ", ".join(tokens) + f"]  (n = {len(tokens)})")
    res = cyk(cnf, tokens)

    times = [res.elapsed_ns]
    for _ in range(max(0, args.repetir - 1)):
        times.append(cyk(cnf, tokens).elapsed_ns)

    print(f"Resultado: {green('SÍ') if res.accepted else red('NO')}")
    if args.repetir > 1:
        print(f"Tiempo CYK: {fmt_time(statistics.median(times))} (mediana de {len(times)} corridas; "
              f"mín {fmt_time(min(times))}, máx {fmt_time(max(times))})")
    else:
        print(f"Tiempo CYK: {fmt_time(res.elapsed_ns)}")

    if args.tabla and tokens:
        print(bold("\nTabla CYK") + dim("  (fila l = longitud de la subcadena, columna = posición inicial)"))
        print(format_table(res))

    if res.accepted:
        total = res.tree_count
        if total > 1:
            print(f"Árboles de derivación: {total}  " + c("(la frase es AMBIGUA)", "1;33"))
        else:
            print("Árboles de derivación: 1")
        limit = max(1, args.todos)
        pairs = res.trees(limit)
        for idx, (t_cnf, t_orig) in enumerate(pairs, 1):
            tag = f" #{idx}" if len(pairs) > 1 else ""
            print(bold(f"\nParse tree{tag} (gramática original)"))
            print(to_ascii(t_orig))
            print(dim(to_bracket(t_orig)))
            if not args.sin_cnf:
                print(bold(f"\nParse tree{tag} (gramática en CNF)"))
                print(to_ascii(t_cnf))
            if out_dir is not None:
                base = out_dir / f"{slug(sentence)}{('_' + str(idx)) if len(pairs) > 1 else ''}"
                img1 = render_dot(to_dot(t_orig, f"{sentence}  (original)"), base.with_name(base.name + "_original"))
                img2 = render_dot(to_dot(t_cnf, f"{sentence}  (CNF)"), base.with_name(base.name + "_cnf"))
                for img in (img1, img2):
                    if img:
                        print(dim(f"  imagen: {img}"))
                if not img1:
                    print(dim(f"  .dot guardado en {out_dir} (instale Graphviz para generar PNG)"))
        if total > len(pairs):
            print(dim(f"\n(se muestran {len(pairs)} de {total}; use --todos N para ver más)"))
    return res.accepted, int(statistics.median(times)), tokens


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Convierte una CFG a Forma Normal de Chomsky y decide w ∈ L(G) con CYK.")
    ap.add_argument("gramatica", help="archivo .txt con la gramática")
    ap.add_argument("frase", nargs="*", help="frase a analizar (si se omite: modo interactivo)")
    ap.add_argument("-f", "--archivo", help="archivo con una frase por línea (# = comentario)")
    ap.add_argument("--pasos", action="store_true", help="mostrar cada paso de la conversión a CNF")
    ap.add_argument("--cnf", action="store_true", help="mostrar la gramática en CNF")
    ap.add_argument("--tabla", action="store_true", help="mostrar la tabla de programación dinámica")
    ap.add_argument("--todos", type=int, default=1, metavar="N",
                    help="mostrar hasta N parse trees si la frase es ambigua (default 1)")
    ap.add_argument("--sin-cnf", action="store_true", help="no imprimir el árbol en CNF")
    ap.add_argument("--png", metavar="DIR", help="guardar los árboles como .dot/.png en DIR")
    ap.add_argument("--repetir", type=int, default=1, metavar="N",
                    help="repetir el CYK N veces y reportar la mediana del tiempo")
    ap.add_argument("--guardar-cnf", metavar="ARCHIVO", help="escribir la gramática CNF en un .txt")
    args = ap.parse_args(argv)

    try:
        g = load_grammar(args.gramatica)
    except (OSError, GrammarError) as e:
        print(red("Error al leer la gramática: ") + str(e), file=sys.stderr)
        return 2

    t0 = time.perf_counter_ns()
    cnf, steps = to_cnf(g)
    t_cnf = time.perf_counter_ns() - t0

    print(bold(f"Gramática: {args.gramatica}"))
    print(f"  Original: {len(g.nonterminals)} no terminales, {len(g.terminals)} terminales, "
          f"{g.size()} producciones")
    print(f"  CNF:      {len(cnf.nonterminals)} no terminales, {cnf.size()} producciones, "
          f"símbolo inicial {cnf.start}  (conversión en {fmt_time(t_cnf)})")

    if args.pasos:
        print_steps(steps)
    elif args.cnf:
        print(banner("Gramática en Forma Normal de Chomsky"))
        print(cnf.to_text())
    if args.guardar_cnf:
        Path(args.guardar_cnf).write_text(cnf.to_text("->") + "\n", encoding="utf-8")
        print(dim(f"  CNF guardada en {args.guardar_cnf}"))

    out_dir = Path(args.png) if args.png else None

    if args.archivo:
        sentences = []
        for line in Path(args.archivo).read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s and not s.startswith("#"):
                sentences.append(s)
        summary = []
        for s in sentences:
            ok, ns, toks = run_sentence(s, g, cnf, args, out_dir)
            summary.append((s, ok, ns, len(toks) if toks is not None else None))
        print(banner("Resumen"))
        w = max(len(s) for s, *_ in summary) if summary else 10
        print(f"{'frase'.ljust(w)}  {'n':>3}  {'resultado':<9}  tiempo CYK")
        for s, ok, ns, n in summary:
            res = green("SÍ") if ok else red("NO")
            n_txt = str(n) if n is not None else "-"
            t_txt = fmt_time(ns) if n is not None else "(fuera de Σ)"
            print(f"{s.ljust(w)}  {n_txt:>3}  {res}{' ' * 7}  {t_txt}")
        yes = sum(1 for _, ok, *_ in summary if ok)
        print(dim(f"{yes} aceptadas, {len(summary) - yes} rechazadas"))
        return 0

    if args.frase:
        run_sentence(" ".join(args.frase), g, cnf, args, out_dir)
        return 0

    # Modo interactivo
    print(dim("Escriba una frase (Enter vacío o Ctrl-D para salir). Use 'ε' para la cadena vacía."))
    while True:
        try:
            s = input(bold("\nw = "))
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not s.strip():
            break
        run_sentence(s, g, cnf, args, out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
