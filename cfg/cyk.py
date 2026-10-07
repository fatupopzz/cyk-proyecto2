"""Algoritmo CYK (Cocke-Younger-Kasami) con programación dinámica.

table[i][l] guarda, para la subcadena que empieza en la posición i y tiene
longitud l, un diccionario  A -> [backpointers]  con todas las formas en que
A deriva esa subcadena. Un backpointer es (producción, k) donde k es el punto
de corte (None para A -> a). Así la tabla sirve para:

  * decidir si w ∈ L(G)                 (¿S está en table[0][n]?)
  * contar cuántos árboles hay           (ambigüedad)
  * reconstruir uno o varios parse trees

Complejidad: O(n³ · |G|) en tiempo y O(n² · |V|) en espacio.
"""

from __future__ import annotations

import itertools
import time
from dataclasses import dataclass

from .grammar import Grammar, Production
from .tree import Leaf, Node, Slot, subst


@dataclass
class CYKResult:
    tokens: list[str]
    accepted: bool
    table: list        # table[i][l] -> {A: [(prod, k), ...]}
    counts: list       # counts[i][l] -> {A: número de árboles}
    elapsed_ns: int
    grammar: Grammar

    @property
    def n(self) -> int:
        return len(self.tokens)

    @property
    def tree_count(self) -> int:
        if not self.accepted:
            return 0
        if self.n == 0:
            return 1
        return self.counts[0][self.n][self.grammar.start]

    # ---- reconstrucción de árboles --------------------------------------
    def derivations(self, limit: int | None = 1):
        """Genera derivaciones (prod, hijos) desde la raíz, hasta `limit`."""
        g = self.grammar
        if not self.accepted:
            return []
        if self.n == 0:
            eps = next(p for p in g.prods[g.start] if not p.rhs)
            return [(eps, [])]

        def gen(i, l, a):
            for prod, k in self.table[i][l][a]:
                if k is None:
                    yield (prod, [self.tokens[i]])
                else:
                    b, c = prod.rhs
                    for left in gen(i, k, b):
                        for right in gen(i + k, l - k, c):
                            yield (prod, [left, right])

        return list(itertools.islice(gen(0, self.n, g.start), limit))

    def trees(self, limit: int | None = 1):
        """Lista de (árbol_cnf, árbol_original)."""
        return [(cnf_tree(d), original_tree(d)) for d in self.derivations(limit)]


def cnf_tree(d) -> Node:
    prod, kids = d
    if not prod.rhs:
        return Node(prod.lhs, (Leaf("ε", eps=True),))
    return Node(prod.lhs, tuple(Leaf(k) if isinstance(k, str) else cnf_tree(k) for k in kids))


def _forest(d) -> tuple:
    """Convierte una derivación CNF en un bosque de la gramática original."""
    prod, kids = d
    flat = []
    for k in kids:
        flat.extend((Leaf(k),) if isinstance(k, str) else _forest(k))
    if prod.pattern is None:            # auxiliar transparente (T_a, BIN)
        return tuple(flat)
    return subst(prod.pattern, lambda i: (flat[i],))


def original_tree(d) -> Node:
    forest = _forest(d)
    assert len(forest) == 1, "la raíz debe producir exactamente un árbol"
    return forest[0]


def cyk(g: Grammar, tokens: list[str]) -> CYKResult:
    """CYK sobre una gramática en CNF."""
    term_index: dict[str, list[Production]] = {}
    bin_index: dict[tuple, list[Production]] = {}
    for p in g.all():
        if len(p.rhs) == 1:
            term_index.setdefault(p.rhs[0], []).append(p)
        elif len(p.rhs) == 2:
            bin_index.setdefault(p.rhs, []).append(p)

    n = len(tokens)
    t0 = time.perf_counter_ns()

    if n == 0:
        accepted = any(not p.rhs for p in g.prods.get(g.start, []))
        return CYKResult(tokens, accepted, [], [], time.perf_counter_ns() - t0, g)

    # table[i][l], l = 1..n (el índice 0 no se usa)
    table = [[None] * (n + 1) for _ in range(n)]
    counts = [[None] * (n + 1) for _ in range(n)]

    # Fila 1: A -> a
    for i, a in enumerate(tokens):
        cell, cnt = {}, {}
        for p in term_index.get(a, ()):
            cell.setdefault(p.lhs, []).append((p, None))
            cnt[p.lhs] = cnt.get(p.lhs, 0) + 1
        table[i][1], counts[i][1] = cell, cnt

    # Filas 2..n: A -> B C con B en [i, i+k) y C en [i+k, i+l)
    for l in range(2, n + 1):
        for i in range(n - l + 1):
            cell, cnt = {}, {}
            for k in range(1, l):
                left, right = table[i][k], table[i + k][l - k]
                if not left or not right:
                    continue
                lc, rc = counts[i][k], counts[i + k][l - k]
                for b in left:
                    for c in right:
                        for p in bin_index.get((b, c), ()):
                            cell.setdefault(p.lhs, []).append((p, k))
                            cnt[p.lhs] = cnt.get(p.lhs, 0) + lc[b] * rc[c]
            table[i][l], counts[i][l] = cell, cnt

    accepted = g.start in table[0][n]
    elapsed = time.perf_counter_ns() - t0
    return CYKResult(tokens, accepted, table, counts, elapsed, g)


def format_table(res: CYKResult, max_cell: int = 40) -> str:
    """Tabla triangular: fila = longitud de la subcadena, columna = inicio."""
    n = res.n
    if n == 0:
        return "(cadena vacía)"
    cells = [[None] * n for _ in range(n + 1)]
    for l in range(1, n + 1):
        for i in range(n - l + 1):
            names = sorted(res.table[i][l]) if res.table[i][l] else []
            s = "{" + ", ".join(names) + "}" if names else "∅"
            if len(s) > max_cell:
                s = s[: max_cell - 2] + "…}"
            cells[l][i] = s
    head = [f"{i}:{t}" for i, t in enumerate(res.tokens)]
    widths = [
        max(len(head[i]), *(len(cells[l][i]) for l in range(1, n - i + 1)))
        for i in range(n)
    ]
    lw = len(f"l={n}")
    sep = "+" + "-" * (lw + 2) + "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    out = [sep, "| " + " " * lw + " | " + " | ".join(h.ljust(w) for h, w in zip(head, widths)) + " |", sep]
    for l in range(n, 0, -1):
        row = []
        for i in range(n):
            row.append((cells[l][i] if i <= n - l else "").ljust(widths[i]))
        out.append(f"| {('l=' + str(l)).ljust(lw)} | " + " | ".join(row) + " |")
    out.append(sep)
    return "\n".join(out)
