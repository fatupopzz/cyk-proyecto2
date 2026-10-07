"""Reconocedor de Earley, usado SOLO en las pruebas como "oráculo".

Trabaja directo sobre la gramática ORIGINAL (con ε y unitarias), así que
sirve para comprobar que la conversión a CNF + CYK no cambió el lenguaje.
Incluye la corrección de Aycock & Horspool para símbolos anulables.
"""

from cfg.cnf import nullable_witnesses


def earley_accepts(g, tokens) -> bool:
    nullable = set(nullable_witnesses(g))
    n = len(tokens)
    start_item = ("$S'", (g.start,), 0, 0)
    chart = [set() for _ in range(n + 1)]
    chart[0].add(start_item)
    for i in range(n + 1):
        agenda = list(chart[i])
        while agenda:
            lhs, rhs, dot, origin = agenda.pop()
            new = []
            if dot < len(rhs):
                x = rhs[dot]
                if g.is_nt(x):
                    for p in g.prods[x]:
                        new.append((x, p.rhs, 0, i))
                    if x in nullable:
                        new.append((lhs, rhs, dot + 1, origin))
                elif i < n and tokens[i] == x:
                    item = (lhs, rhs, dot + 1, origin)
                    chart[i + 1].add(item)
            else:
                for (l2, r2, d2, o2) in list(chart[origin]):
                    if d2 < len(r2) and r2[d2] == lhs:
                        new.append((l2, r2, d2 + 1, o2))
            for item in new:
                if item not in chart[i]:
                    chart[i].add(item)
                    agenda.append(item)
    return ("$S'", (g.start,), 1, 0) in chart[n]
