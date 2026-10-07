"""Simplificación de gramáticas y conversión a Forma Normal de Chomsky.

Pasos (en este orden, ver README para la justificación):

  1. START    nuevo símbolo inicial S0 -> S si S aparece en algún lado derecho
  2. DEL      eliminar producciones ε (anulables)
  3. UNIT     eliminar producciones unitarias A -> B
  4. USELESS  eliminar símbolos inútiles (no generadores y no alcanzables)
  5. TERM     sacar terminales de las reglas largas: A -> a B  =>  A -> T_a B, T_a -> a
  6. BIN      partir reglas largas: A -> B C D  =>  A -> B A_1, A_1 -> C D

Cada paso conserva el "patrón" de cada producción (ver tree.py) para poder
reconstruir, al final del CYK, el árbol en términos de la gramática original.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, field

from .grammar import Grammar, Production
from .tree import Slot, subst


@dataclass
class Step:
    key: str
    title: str
    grammar: Grammar
    notes: list[str] = field(default_factory=list)


def _unit(g: Grammar, p: Production) -> bool:
    return len(p.rhs) == 1 and g.is_nt(p.rhs[0])


# ---------------------------------------------------------------------------
# 1. START
# ---------------------------------------------------------------------------
def step_start(g: Grammar) -> Step:
    on_rhs = any(g.start in p.rhs for p in g.all())
    if not on_rhs:
        return Step("START", "Símbolo inicial", g,
                    [f"{g.start} no aparece en ningún lado derecho: no hace falta S0."])
    s0 = g.fresh(g.start + "0")
    ng = Grammar(s0)
    ng.add(s0, (g.start,), (Slot(0),))
    for p in g.all():
        ng.add(p.lhs, p.rhs, p.pattern)
    return Step("START", "Símbolo inicial", ng,
                [f"{g.start} aparece en un lado derecho, se agrega {s0} → {g.start}."])


# ---------------------------------------------------------------------------
# 2. DEL: producciones ε
# ---------------------------------------------------------------------------
def nullable_witnesses(g: Grammar) -> dict[str, tuple]:
    """Conjunto de anulables. Para cada uno guarda un árbol testigo A =>* ε
    (en términos de la gramática original), que luego se inserta en el parse
    tree donde la producción nueva "se saltó" ese símbolo."""
    wit: dict[str, tuple] = {}
    changed = True
    while changed:
        changed = False
        for p in g.all():
            if p.lhs in wit:
                continue
            if all(s in wit for s in p.rhs):
                wit[p.lhs] = subst(p.pattern, lambda i, p=p: wit[p.rhs[i]])
                changed = True
    return wit


def step_del(g: Grammar) -> Step:
    wit = nullable_witnesses(g)
    ng = Grammar(g.start)
    removed = []
    for p in g.all():
        if not p.rhs:
            if p.lhs != g.start:
                removed.append(str(p))
            continue
        pos = [i for i, s in enumerate(p.rhs) if s in wit]
        for mask in itertools.product((True, False), repeat=len(pos)):
            omit = {i for i, keep in zip(pos, mask) if not keep}
            kept = [i for i in range(len(p.rhs)) if i not in omit]
            if not kept and p.lhs != g.start:
                continue
            new_index = {old: new for new, old in enumerate(kept)}
            pattern = subst(
                p.pattern,
                lambda i, omit=omit, new_index=new_index, p=p:
                    wit[p.rhs[i]] if i in omit else (Slot(new_index[i]),),
            )
            ng.add(p.lhs, tuple(p.rhs[i] for i in kept), pattern)
    # S -> ε se conserva solo para el símbolo inicial
    if g.start in wit:
        ng.add(g.start, (), wit[g.start])
    for a in g.order:
        ng.add_nt(a)
    nulls = [a for a in g.order if a in wit]
    notes = [
        "Anulables: {" + ", ".join(nulls) + "}" if nulls else "No hay símbolos anulables.",
    ]
    if removed:
        notes.append("Se eliminan: " + ", ".join(removed))
    if g.start in wit:
        notes.append(f"ε ∈ L(G): se conserva {g.start} → ε.")
    return Step("DEL", "Eliminar producciones ε", ng, notes)


# ---------------------------------------------------------------------------
# 3. UNIT: producciones unitarias
# ---------------------------------------------------------------------------
def step_unit(g: Grammar) -> Step:
    ng = Grammar(g.start)
    pairs = []
    for a in g.order:
        ng.add_nt(a)
        # BFS sobre A => B1 => B2 ... guardando el patrón compuesto de la cadena
        chains: dict[str, tuple] = {a: (Slot(0),)}
        queue = [a]
        while queue:
            b = queue.pop(0)
            for p in g.prods.get(b, []):
                if _unit(g, p) and p.rhs[0] not in chains:
                    chains[p.rhs[0]] = subst(chains[b], lambda i, p=p: p.pattern)
                    queue.append(p.rhs[0])
        for b, chain in chains.items():
            if b != a:
                pairs.append(f"({a},{b})")
            for p in g.prods.get(b, []):
                if not _unit(g, p):
                    ng.add(a, p.rhs, subst(chain, lambda i, p=p: p.pattern))
    units = [str(p) for p in g.all() if _unit(g, p)]
    notes = []
    if units:
        notes.append("Unitarias eliminadas: " + ", ".join(units))
        notes.append("Pares unitarios (A =>* B): " + ", ".join(pairs))
    else:
        notes.append("No hay producciones unitarias.")
    return Step("UNIT", "Eliminar producciones unitarias", ng, notes)


# ---------------------------------------------------------------------------
# 4. USELESS: no generadores y no alcanzables
# ---------------------------------------------------------------------------
def step_useless(g: Grammar) -> Step:
    gen: set[str] = set()
    changed = True
    while changed:
        changed = False
        for p in g.all():
            if p.lhs not in gen and all(s in gen or not g.is_nt(s) for s in p.rhs):
                gen.add(p.lhs)
                changed = True
    non_gen = [a for a in g.order if a not in gen]

    reach = {g.start} if g.start in gen else set()
    queue = list(reach)
    while queue:
        a = queue.pop()
        for p in g.prods.get(a, []):
            if all(s in gen or not g.is_nt(s) for s in p.rhs):
                for s in p.rhs:
                    if g.is_nt(s) and s not in reach:
                        reach.add(s)
                        queue.append(s)
    non_reach = [a for a in g.order if a in gen and a not in reach]

    ng = Grammar(g.start)
    ng.add_nt(g.start)
    for p in g.all():
        if p.lhs in reach and all((s in reach) or not g.is_nt(s) for s in p.rhs):
            ng.add(p.lhs, p.rhs, p.pattern)
    notes = [
        "No generadores: {" + ", ".join(non_gen) + "}" if non_gen else "Todos los símbolos son generadores.",
        "No alcanzables: {" + ", ".join(non_reach) + "}" if non_reach else "Todos los símbolos son alcanzables.",
    ]
    if g.start not in gen:
        notes.append(f"{g.start} no genera ninguna cadena: L(G) = ∅.")
    return Step("USELESS", "Eliminar símbolos inútiles", ng, notes)


# ---------------------------------------------------------------------------
# 5. TERM: terminales en reglas de longitud >= 2
# ---------------------------------------------------------------------------
_PUNCT = {
    "+": "PLUS", "-": "MINUS", "*": "STAR", "/": "SLASH", "(": "LPAR", ")": "RPAR",
    "[": "LBRACK", "]": "RBRACK", "{": "LBRACE", "}": "RBRACE", ",": "COMMA",
    ";": "SEMI", ".": "DOT", "=": "EQ", "<": "LT", ">": "GT", "^": "CARET",
    "!": "BANG", "?": "QMARK", ":": "COLON", "&": "AMP", "|": "BAR", "%": "PCT",
}


def _term_name(a: str) -> str:
    if a in _PUNCT:
        return "T_" + _PUNCT[a]
    clean = re.sub(r"\W", "", a).upper()
    return "T_" + (clean or "SYM")


def step_term(g: Grammar) -> Step:
    ng = Grammar(g.start)
    names: dict[str, str] = {}
    taken: set[str] = set()
    # primero los nombres, para que no choquen entre sí
    for p in g.all():
        if len(p.rhs) >= 2:
            for s in p.rhs:
                if not g.is_nt(s) and s not in names:
                    names[s] = g.fresh(_term_name(s), taken)
                    taken.add(names[s])
    for a in g.order:
        ng.add_nt(a)
    for p in g.all():
        if len(p.rhs) >= 2:
            rhs = tuple(names.get(s, s) if not g.is_nt(s) else s for s in p.rhs)
            ng.add(p.lhs, rhs, p.pattern)
        else:
            ng.add(p.lhs, p.rhs, p.pattern)
    for a, t in names.items():
        ng.add(t, (a,), None)
    notes = (["Nuevos: " + ", ".join(f"{t} → {a}" for a, t in names.items())]
             if names else ["No hay terminales mezclados en reglas largas."])
    return Step("TERM", "Separar terminales", ng, notes)


# ---------------------------------------------------------------------------
# 6. BIN: lados derechos de longitud > 2
# ---------------------------------------------------------------------------
def step_bin(g: Grammar) -> Step:
    ng = Grammar(g.start)
    for a in g.order:
        ng.add_nt(a)
    cache: dict[tuple, str] = {}
    taken: set[str] = set()
    created: list[str] = []
    counters: dict[str, int] = {}

    def helper(owner: str, tail: tuple) -> str:
        # Las colas idénticas comparten auxiliar (sigue siendo equivalente).
        if tail in cache:
            return cache[tail]
        counters[owner] = counters.get(owner, 0) + 1
        name = g.fresh(f"{owner}_{counters[owner]}", taken)
        while name in taken:
            counters[owner] += 1
            name = g.fresh(f"{owner}_{counters[owner]}", taken)
        taken.add(name)
        cache[tail] = name
        rhs = tail if len(tail) == 2 else (tail[0], helper(owner, tail[1:]))
        ng.add(name, rhs, None)
        created.append(f"{name} → {' '.join(rhs)}")
        return name

    for p in g.all():
        if len(p.rhs) > 2:
            ng.add(p.lhs, (p.rhs[0], helper(p.lhs, p.rhs[1:])), p.pattern)
        else:
            ng.add(p.lhs, p.rhs, p.pattern)
    notes = (["Auxiliares: " + ", ".join(created)] if created
             else ["Ya no hay lados derechos con más de 2 símbolos."])
    return Step("BIN", "Binarizar reglas largas", ng, notes)


# ---------------------------------------------------------------------------
STEPS = (step_start, step_del, step_unit, step_useless, step_term, step_bin)


def is_cnf(g: Grammar) -> list[str]:
    """Devuelve la lista de violaciones (vacía si está en CNF)."""
    bad = []
    for p in g.all():
        if len(p.rhs) == 2 and all(g.is_nt(s) for s in p.rhs):
            if g.start in p.rhs:
                bad.append(f"{p}: el inicial aparece a la derecha")
            continue
        if len(p.rhs) == 1 and not g.is_nt(p.rhs[0]):
            continue
        if not p.rhs and p.lhs == g.start:
            continue
        bad.append(str(p))
    return bad


def to_cnf(g: Grammar) -> tuple[Grammar, list[Step]]:
    steps = [Step("ORIG", "Gramática original", g)]
    cur = g
    for fn in STEPS:
        st = fn(cur)
        steps.append(st)
        cur = st.grammar
    bad = is_cnf(cur)
    if bad:  # no debería pasar nunca; lo revisan las pruebas
        raise AssertionError("La gramática resultante no está en CNF: " + "; ".join(bad))
    return cur, steps
