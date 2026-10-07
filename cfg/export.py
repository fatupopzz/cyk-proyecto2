"""Salida en JSON para la interfaz visual (web/index.html).

web/cyk-engine.js implementa exactamente el mismo contrato en JavaScript;
tests/test_engines.py verifica que ambos motores den el mismo resultado.

analyze(texto_gramatica, frase | None, max_arboles) -> dict:

{
  "error": str | None,
  "steps": [{"key", "title", "notes": [..], "start", "rules": [{"lhs", "alts": [[sym, ..], ..]}]}],
  "cnf":   {"start", "rules": [...], "nonterminals": [..], "terminals": [..]},
  "original": {"nonterminals": [..], "terminals": [..], "size": int},
  "result": None | {
      "tokens": [..] | None, "tokenError": str | None,
      "accepted": bool, "ns": float, "reps": int, "firstNs": int,
      "treeCount": str,                       # str porque puede ser enorme
      "table": [[ [[A, [[k, B, C] | [None, a], ..]], ..] ]],   # table[l-1][i]
      "trees": [{"cnf": T, "orig": T}]        # T = {"s": A, "c": [..]} | {"t": a} | {"e": 1}
  }
}
"""

from __future__ import annotations

import time

from .cnf import to_cnf
from .cyk import cyk
from .grammar import Grammar, GrammarError, parse_grammar
from .tokenizer import TokenizeError, tokenize
from .tree import Leaf, Node

MIN_BENCH_NS = 5_000_000      # repetir hasta acumular al menos 5 ms
MAX_REPS = 1000


def rules_json(g: Grammar) -> list:
    return [{"lhs": a, "alts": [list(p.rhs) for p in g.prods[a]]} for a in g.nonterminals]


def tree_json(t) -> dict:
    if isinstance(t, Leaf):
        return {"e": 1} if t.eps else {"t": t.text}
    return {"s": t.sym, "c": [tree_json(k) for k in t.kids]}


def analyze(grammar_text: str, sentence: str | None = None, max_trees: int = 20) -> dict:
    out: dict = {"error": None, "steps": [], "cnf": None, "original": None, "result": None}
    try:
        g = parse_grammar(grammar_text)
    except GrammarError as e:
        out["error"] = str(e)
        return out

    t0 = time.perf_counter_ns()
    cnf, steps = to_cnf(g)
    out["cnfNs"] = time.perf_counter_ns() - t0
    out["steps"] = [
        {"key": st.key, "title": st.title, "notes": st.notes,
         "start": st.grammar.start, "rules": rules_json(st.grammar)}
        for st in steps
    ]
    out["original"] = {"nonterminals": g.nonterminals, "terminals": g.terminals, "size": g.size()}
    out["cnf"] = {"start": cnf.start, "rules": rules_json(cnf),
                  "nonterminals": cnf.nonterminals, "terminals": cnf.terminals, "size": cnf.size()}

    if sentence is None:
        return out

    res: dict = {"tokens": None, "tokenError": None, "accepted": False, "ns": 0, "reps": 0,
                 "firstNs": 0, "treeCount": "0", "table": [], "trees": []}
    out["result"] = res
    try:
        tokens = tokenize(sentence, g.terminals)
    except TokenizeError as e:
        res["tokenError"] = str(e)
        return out
    res["tokens"] = tokens

    r = cyk(cnf, tokens)
    total, reps = r.elapsed_ns, 1
    while total < MIN_BENCH_NS and reps < MAX_REPS:
        total += cyk(cnf, tokens).elapsed_ns
        reps += 1
    res.update(accepted=r.accepted, firstNs=r.elapsed_ns, ns=total / reps, reps=reps,
               treeCount=str(r.tree_count))

    n = len(tokens)
    table = []
    for l in range(1, n + 1):
        row = []
        for i in range(n - l + 1):
            cell = []
            for a, backs in r.table[i][l].items():
                cell.append([a, [[None, p.rhs[0]] if k is None else [k, p.rhs[0], p.rhs[1]]
                                 for p, k in backs]])
            row.append(cell)
        table.append(row)
    res["table"] = table
    res["trees"] = [{"cnf": tree_json(c), "orig": tree_json(o)} for c, o in r.trees(max_trees)]
    return out
