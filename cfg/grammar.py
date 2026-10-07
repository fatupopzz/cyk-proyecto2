"""Representación de gramáticas libres de contexto y lectura desde .txt.

Formato aceptado (una o varias reglas por línea):

    S  -> NP VP
    VP -> VP PP | V NP | cooks | drinks
    X  -> + T X | e          # 'e', 'ε', 'eps', 'λ' = cadena vacía
    # comentarios con '#'

* Se acepta '->', '→' o '::='.
* Los símbolos se separan con espacios.
* Un símbolo es NO terminal si aparece como lado izquierdo de alguna regla;
  todo lo demás es terminal.
* El símbolo inicial es el lado izquierdo de la primera regla.
"""

from __future__ import annotations

from dataclasses import dataclass

from .tree import EPS_LEAF, Node, Slot

EPS_TOKENS = {"ε", "e", "eps", "epsilon", "λ", "lambda", "''", '""'}
ARROWS = ("->", "→", "::=")


class GrammarError(ValueError):
    pass


@dataclass(frozen=True)
class Production:
    lhs: str
    rhs: tuple
    # Cómo se ve esta producción en la gramática original (ver tree.py).
    # None = producción auxiliar "transparente" (T_a -> a, auxiliares de BIN):
    # devuelve la secuencia de sus hijos tal cual.
    pattern: tuple | None = None

    def __str__(self) -> str:
        return f"{self.lhs} → {' '.join(self.rhs) if self.rhs else 'ε'}"


class Grammar:
    def __init__(self, start: str):
        self.start = start
        self.order: list[str] = []          # orden de aparición de los no terminales
        self.prods: dict[str, list[Production]] = {}
        self._keys: set[tuple] = set()

    # ---- construcción -------------------------------------------------
    def add_nt(self, a: str) -> None:
        if a not in self.prods:
            self.prods[a] = []
            self.order.append(a)

    def add(self, lhs: str, rhs: tuple, pattern=None) -> bool:
        """Agrega lhs -> rhs si no existe ya. Devuelve True si fue nueva."""
        self.add_nt(lhs)
        key = (lhs, tuple(rhs))
        if key in self._keys:
            return False
        self._keys.add(key)
        self.prods[lhs].append(Production(lhs, tuple(rhs), pattern))
        return True

    def copy_structure(self, start: str | None = None) -> "Grammar":
        g = Grammar(start or self.start)
        return g

    # ---- consultas ----------------------------------------------------
    def is_nt(self, s: str) -> bool:
        return s in self.prods

    @property
    def nonterminals(self) -> list[str]:
        nts = [a for a in self.order if self.prods.get(a)]
        if self.start in nts:
            nts.remove(self.start)
            nts.insert(0, self.start)
        return nts

    @property
    def terminals(self) -> list[str]:
        seen: dict[str, None] = {}
        for p in self.all():
            for s in p.rhs:
                if not self.is_nt(s):
                    seen[s] = None
        return list(seen)

    def all(self):
        for a in self.order:
            yield from self.prods[a]

    def symbols(self) -> set[str]:
        return set(self.prods) | set(self.terminals)

    def size(self) -> int:
        return sum(len(v) for v in self.prods.values())

    def fresh(self, base: str, taken: set[str] | None = None) -> str:
        """Nombre de no terminal que no choque con ningún símbolo existente."""
        used = self.symbols() | (taken or set())
        if base not in used:
            return base
        k = 1
        while f"{base}{k}" in used:
            k += 1
        return f"{base}{k}"

    # ---- salida -------------------------------------------------------
    def to_text(self, arrow: str = "→") -> str:
        lines = []
        nts = self.nonterminals
        width = max((len(a) for a in nts), default=1)
        for a in nts:
            alts = [" ".join(p.rhs) if p.rhs else "ε" for p in self.prods[a]]
            lines.append(f"{a.ljust(width)} {arrow} " + " | ".join(alts))
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.to_text()


def original_pattern(lhs: str, rhs: tuple) -> tuple:
    """Patrón de una producción de la gramática original: el nodo tal cual."""
    if not rhs:
        return (Node(lhs, (EPS_LEAF,)),)
    return (Node(lhs, tuple(Slot(i) for i in range(len(rhs)))),)


def parse_grammar(text: str) -> Grammar:
    raw: list[tuple[int, str, list[list[str]]]] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        line = line.split("#", 1)[0].strip() if not line.lstrip().startswith("#") else ""
        if not line:
            continue
        arrow = next((a for a in ARROWS if a in line), None)
        if arrow is None:
            raise GrammarError(f"Línea {lineno}: falta '->' en «{line}»")
        lhs, rhs = line.split(arrow, 1)
        lhs = lhs.strip()
        if not lhs or len(lhs.split()) != 1:
            raise GrammarError(f"Línea {lineno}: lado izquierdo inválido «{lhs}»")
        alts = [alt.split() for alt in rhs.split("|")]
        raw.append((lineno, lhs, alts))

    if not raw:
        raise GrammarError("La gramática está vacía")

    nts = {lhs for _, lhs, _ in raw}
    g = Grammar(raw[0][1])
    for _, lhs, alts in raw:
        g.add_nt(lhs)
        for toks in alts:
            # 'ε' sola (o vacía) = producción vacía. Una 'e' solo cuenta como
            # ε si nadie la definió como no terminal.
            if not toks or (len(toks) == 1 and toks[0] in EPS_TOKENS and toks[0] not in nts):
                rhs: tuple = ()
            else:
                rhs = tuple(t for t in toks if t not in ("ε", "λ"))
            g.add(lhs, rhs, original_pattern(lhs, rhs))
    return g


def load_grammar(path) -> Grammar:
    with open(path, encoding="utf-8") as fh:
        return parse_grammar(fh.read())
