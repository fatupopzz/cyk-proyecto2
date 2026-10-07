"""Estructuras de árbol y "patrones" para reconstruir el parse tree original.

Cada producción guarda un *patrón*: una tupla de items (Node, Leaf o Slot)
que describe cómo se ve esa producción en términos de la gramática ORIGINAL.
Un Slot(i) es un hueco que se llena con el sub-árbol del i-ésimo hijo.

Cuando una transformación de la CNF cambia una producción, también
transforma su patrón. Así, al final del CYK podemos convertir el árbol en
CNF de vuelta a un árbol de la gramática original (con sus ε incluidas).
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

EPS = "ε"


@dataclass(frozen=True)
class Slot:
    i: int


@dataclass(frozen=True)
class Leaf:
    text: str
    eps: bool = False


@dataclass(frozen=True)
class Node:
    sym: str
    kids: tuple


EPS_LEAF = Leaf(EPS, eps=True)


def subst(pattern: tuple, f) -> tuple:
    """Reemplaza cada Slot(i) del patrón por la tupla de items f(i) (splice)."""
    out = []
    for it in pattern:
        if isinstance(it, Slot):
            out.extend(f(it.i))
        elif isinstance(it, Node):
            out.append(Node(it.sym, subst(it.kids, f)))
        else:
            out.append(it)
    return tuple(out)


def tree_yield(t) -> list[str]:
    """Las hojas terminales del árbol, de izquierda a derecha (sin ε)."""
    if isinstance(t, Leaf):
        return [] if t.eps else [t.text]
    out = []
    for k in t.kids:
        out.extend(tree_yield(k))
    return out


def tree_size(t) -> int:
    if isinstance(t, Leaf):
        return 1
    return 1 + sum(tree_size(k) for k in t.kids)


def tree_height(t) -> int:
    if isinstance(t, Leaf):
        return 0
    return 1 + max(tree_height(k) for k in t.kids)


def to_bracket(t) -> str:
    """Notación con corchetes: [S [NP she] [VP ...]]"""
    if isinstance(t, Leaf):
        return t.text
    return "[" + t.sym + " " + " ".join(to_bracket(k) for k in t.kids) + "]"


def to_ascii(t) -> str:
    lines: list[str] = []

    def label(n):
        return n.text if isinstance(n, Leaf) else n.sym

    def rec(n, prefix: str, last: bool, root: bool):
        if root:
            lines.append(label(n))
            child_prefix = ""
        else:
            lines.append(prefix + ("└── " if last else "├── ") + label(n))
            child_prefix = prefix + ("    " if last else "│   ")
        if isinstance(n, Node):
            for j, k in enumerate(n.kids):
                rec(k, child_prefix, j == len(n.kids) - 1, False)

    rec(t, "", True, True)
    return "\n".join(lines)


def _dot_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def to_dot(t, title: str = "") -> str:
    out = [
        "digraph ParseTree {",
        '  graph [ordering=out, nodesep=0.3, ranksep=0.45, fontname="Helvetica", '
        f'labelloc=t, label="{_dot_escape(title)}"];',
        '  node [fontname="Helvetica", fontsize=13];',
        "  edge [arrowhead=none, color=\"#555555\"];",
    ]
    counter = [0]

    def rec(n) -> str:
        nid = f"n{counter[0]}"
        counter[0] += 1
        if isinstance(n, Leaf):
            if n.eps:
                out.append(f'  {nid} [label="ε", shape=plaintext, fontcolor="#888888"];')
            else:
                out.append(
                    f'  {nid} [label="{_dot_escape(n.text)}", shape=box, style="rounded,filled", '
                    'fillcolor="#FDE7C8", color="#C98A2B"];'
                )
            return nid
        out.append(
            f'  {nid} [label="{_dot_escape(n.sym)}", shape=ellipse, style=filled, '
            'fillcolor="#DCE8FA", color="#3D6CB3"];'
        )
        for k in n.kids:
            kid = rec(k)
            out.append(f"  {nid} -> {kid};")
        return nid

    rec(t)
    # Las hojas terminales en la misma fila, como en los libros.
    leaves = [line.split()[0] for line in out if "shape=box" in line]
    if leaves:
        out.append("  { rank=same; " + " ".join(leaves) + " }")
    out.append("}")
    return "\n".join(out)


def render_dot(dot_src: str, path_without_ext: Path, fmt: str = "png") -> Path | None:
    """Escribe el .dot y, si Graphviz está instalado, también la imagen."""
    path_without_ext.parent.mkdir(parents=True, exist_ok=True)
    dot_path = path_without_ext.with_suffix(".dot")
    dot_path.write_text(dot_src, encoding="utf-8")
    if not shutil.which("dot"):
        return None
    img = path_without_ext.with_suffix("." + fmt)
    subprocess.run(["dot", f"-T{fmt}", "-Gdpi=150", str(dot_path), "-o", str(img)], check=True)
    return img
