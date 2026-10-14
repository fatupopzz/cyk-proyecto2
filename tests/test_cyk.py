"""Pruebas del proyecto. Ejecutar desde la raíz:

    python -m unittest -v

Estrategia: comparar CYK (sobre la CNF generada) contra un reconocedor de
Earley que trabaja con la gramática ORIGINAL, en TODAS las cadenas cortas
posibles y en cientos de gramáticas aleatorias con ε, unitarias, ciclos y
símbolos inútiles.
"""

import itertools
import random
import unittest
from pathlib import Path

from cfg import cyk, is_cnf, load_grammar, parse_grammar, to_cnf, tokenize
from cfg.cnf import MAX_NULLABLE
from cfg.export import tree_json
from cfg.grammar import GrammarError, grammar_warnings
from cfg.tree import EPS, Leaf, Node, tree_yield
from tests.earley import earley_accepts

ROOT = Path(__file__).resolve().parent.parent
G = ROOT / "grammars"


def all_strings(alphabet, max_len):
    for n in range(max_len + 1):
        yield from itertools.product(alphabet, repeat=n)


def check_tree(tc, g, tree, tokens):
    """El árbol reconstruido debe usar SOLO producciones de la gramática original."""
    rules = {(p.lhs, p.rhs) for p in g.all()}
    tc.assertIsInstance(tree, Node)
    tc.assertEqual(tree.sym, g.start)
    tc.assertEqual(tree_yield(tree), list(tokens))

    def rec(n):
        if isinstance(n, Leaf):
            return
        if len(n.kids) == 1 and isinstance(n.kids[0], Leaf) and n.kids[0].eps:
            tc.assertIn((n.sym, ()), rules, f"{n.sym} → ε no existe en la gramática")
            return
        rhs = tuple(k.text if isinstance(k, Leaf) else k.sym for k in n.kids)
        tc.assertIn((n.sym, rhs), rules, f"{n.sym} → {' '.join(rhs)} no existe en la gramática")
        for k in n.kids:
            rec(k)

    rec(tree)


def random_grammar(rng: random.Random) -> str:
    nts = ["S", "A", "B", "C"][: rng.randint(1, 4)]
    terms = ["a", "b"]
    lines = []
    for a in nts:
        alts = []
        for _ in range(rng.randint(1, 3)):
            k = rng.choice([0, 1, 1, 2, 2, 3])
            rhs = [rng.choice(nts + terms) for _ in range(k)]
            alts.append(" ".join(rhs) if rhs else "ε")
        lines.append(f"{a} -> " + " | ".join(alts))
    return "\n".join(lines)


class TestGrammarFiles(unittest.TestCase):
    def test_all_grammar_files_convert_to_valid_cnf(self):
        for path in sorted(G.glob("*.txt")):
            with self.subTest(path.name):
                cnf, _ = to_cnf(load_grammar(path))
                self.assertEqual(is_cnf(cnf), [])

    def test_enunciado_examples(self):
        g = load_grammar(G / "ingles.txt")
        cnf, _ = to_cnf(g)
        for s in ["She eats a cake with a fork", "The cat drinks the beer"]:
            r = cyk(cnf, tokenize(s, g.terminals))
            self.assertTrue(r.accepted, s)
            check_tree(self, g, r.trees()[0][1], r.tokens)

    def test_test_files_match_expected(self):
        cases = [("ingles.txt", "frases_ingles.txt"), ("expresiones.txt", "frases_expresiones.txt")]
        for gname, fname in cases:
            g = load_grammar(G / gname)
            cnf, _ = to_cnf(g)
            expect = None
            for line in (ROOT / "pruebas" / fname).read_text(encoding="utf-8").splitlines():
                if line.startswith("#"):
                    expect = "SÍ" in line
                    continue
                if not line.strip():
                    continue
                with self.subTest(gname, frase=line):
                    try:
                        toks = tokenize(line, g.terminals)
                    except ValueError:
                        self.assertFalse(expect)
                        continue
                    self.assertEqual(cyk(cnf, toks).accepted, expect)
                    self.assertEqual(earley_accepts(g, toks), expect)


class TestAgainstEarley(unittest.TestCase):
    def assert_same_language(self, g, alphabet, max_len):
        cnf, _ = to_cnf(g)
        self.assertEqual(is_cnf(cnf), [])
        for w in all_strings(alphabet, max_len):
            r = cyk(cnf, list(w))
            self.assertEqual(r.accepted, earley_accepts(g, list(w)), f"w = {' '.join(w) or EPS}")
            if r.accepted:
                for _, t in r.trees(3):
                    check_tree(self, g, t, w)

    def test_expresiones_exhaustive(self):
        g = load_grammar(G / "expresiones.txt")
        self.assert_same_language(g, ["id", "+", "*", "(", ")"], 7)

    def test_ingles_exhaustive_short(self):
        g = load_grammar(G / "ingles.txt")
        self.assert_same_language(g, g.terminals, 3)

    def test_ingles_random_long(self):
        g = load_grammar(G / "ingles.txt")
        cnf, _ = to_cnf(g)
        rng = random.Random(7)
        vocab = g.terminals
        for _ in range(3000):
            w = [rng.choice(vocab) for _ in range(rng.randint(4, 12))]
            self.assertEqual(cyk(cnf, w).accepted, earley_accepts(g, w), " ".join(w))

    def test_ingles_generated_sentences_are_accepted(self):
        g = load_grammar(G / "ingles.txt")
        cnf, _ = to_cnf(g)
        rng = random.Random(3)

        def gen(sym, depth):
            if not g.is_nt(sym):
                return [sym]
            prods = g.prods[sym]
            if depth > 6:  # cortar la recursión VP -> VP PP
                prods = [p for p in prods if sym not in p.rhs] or prods
            p = rng.choice(prods)
            return [t for s in p.rhs for t in gen(s, depth + 1)]

        for _ in range(500):
            w = gen(g.start, 0)
            r = cyk(cnf, w)
            self.assertTrue(r.accepted, " ".join(w))
            check_tree(self, g, r.trees()[0][1], w)

    def test_random_grammars(self):
        rng = random.Random(2025)
        for k in range(400):
            src = random_grammar(rng)
            with self.subTest(k, grammar=src):
                self.assert_same_language(parse_grammar(src), ["a", "b"], 6)


class TestAmbiguity(unittest.TestCase):
    def test_catalan_numbers(self):
        # E -> E + E | ... : id (+ id)^m tiene Catalan(m) árboles
        g = load_grammar(G / "ambigua.txt")
        cnf, _ = to_cnf(g)
        catalan = [1, 1, 2, 5, 14, 42, 132, 429]
        for m, expected in enumerate(catalan):
            w = ["id"] + ["+", "id"] * m
            r = cyk(cnf, w)
            self.assertEqual(r.tree_count, expected, f"m = {m}")
            trees = r.trees(None)
            self.assertEqual(len(trees), expected)
            self.assertEqual(len({str(t) for _, t in trees}), expected)  # todos distintos
            for _, t in trees:
                check_tree(self, g, t, w)


class TestManualCNF(unittest.TestCase):
    def test_manual_cnf_generates_same_language(self):
        orig = load_grammar(G / "expresiones.txt")
        manual = load_grammar(G / "expresiones_cnf_manual.txt")
        c1, _ = to_cnf(orig)
        c2, _ = to_cnf(manual)
        for w in all_strings(["id", "+", "*", "(", ")"], 7):
            self.assertEqual(cyk(c1, list(w)).accepted, cyk(c2, list(w)).accepted, " ".join(w))


class TestEdgeCases(unittest.TestCase):
    def test_empty_string(self):
        g = parse_grammar("S -> a S b | e")
        cnf, _ = to_cnf(g)
        r = cyk(cnf, [])
        self.assertTrue(r.accepted)
        check_tree(self, g, r.trees()[0][1], [])
        self.assertTrue(cyk(cnf, ["a", "a", "b", "b"]).accepted)
        self.assertFalse(cyk(cnf, ["a", "b", "b"]).accepted)

    def test_empty_language(self):
        g = parse_grammar("S -> A b\nA -> a A")
        cnf, _ = to_cnf(g)
        self.assertEqual(is_cnf(cnf), [])
        for w in all_strings(["a", "b"], 4):
            self.assertFalse(cyk(cnf, list(w)).accepted)

    def test_unit_cycle(self):
        g = parse_grammar("S -> A\nA -> B | a\nB -> A | b | S")
        cnf, _ = to_cnf(g)
        self.assertTrue(cyk(cnf, ["a"]).accepted)
        self.assertTrue(cyk(cnf, ["b"]).accepted)
        check_tree(self, g, cyk(cnf, ["b"]).trees()[0][1], ["b"])

    def test_name_clash(self):
        # ya existe un no terminal llamado T_PLUS y otro S0
        g = parse_grammar("S -> S + T_PLUS | x\nT_PLUS -> y\nS0 -> z")
        cnf, _ = to_cnf(g)
        self.assertEqual(is_cnf(cnf), [])
        self.assertTrue(cyk(cnf, ["x", "+", "y", "+", "y"]).accepted)


class TestRobustness(unittest.TestCase):
    """Casos que rompían el programa en las pruebas de estrés."""

    EXPR = "E -> T X\nX -> + T X | e\nT -> F Y\nY -> * F Y | e\nF -> ( E ) | id\n"

    def test_bom_from_windows_notepad(self):
        g = parse_grammar("\ufeff" + self.EXPR)
        self.assertEqual(g.start, "E")
        self.assertNotIn("E", g.terminals)
        cnf, _ = to_cnf(g)
        self.assertTrue(cyk(cnf, tokenize("(id)", g.terminals)).accepted)

    def test_control_separators(self):
        g = parse_grammar("S -> a\x1cb\u2028S -> c")   # \x1c y U+2028 son espacios, no saltos de línea
        self.assertEqual([p.rhs for p in g.prods["S"]], [("a", "b", "S", "->", "c")])

    def test_empty_alternative_is_an_error(self):
        for text in ("S -> a |", "S -> | a", "S ->", "S -> a || b"):
            with self.assertRaises(GrammarError, msg=text):
                parse_grammar(text)
        self.assertEqual(parse_grammar("S -> a | e").prods["S"][1].rhs, ())

    def test_undefined_nonterminal_warning(self):
        self.assertTrue(grammar_warnings(parse_grammar("S -> Tt a\nT -> b")))
        self.assertEqual(grammar_warnings(load_grammar(G / "ingles.txt")), [])
        self.assertEqual(grammar_warnings(load_grammar(G / "expresiones.txt")), [])

    def test_too_many_nullables_is_an_error_not_a_hang(self):
        g = parse_grammar("S -> " + " ".join(["A"] * (MAX_NULLABLE + 1)) + "\nA -> a | e")
        with self.assertRaises(GrammarError):
            to_cnf(g)
        g = parse_grammar("S -> " + " ".join(["A"] * MAX_NULLABLE) + "\nA -> a | e")
        cnf, _ = to_cnf(g)
        self.assertTrue(cyk(cnf, ["a"] * 3).accepted)

    def test_deep_tree(self):
        # antes: RecursionError con unas 500 palabras
        g = parse_grammar("S -> a S | a")
        cnf, _ = to_cnf(g)
        r = cyk(cnf, ["a"] * 550)
        t_cnf, t_orig = r.trees(1)[0]
        self.assertEqual(tree_yield(t_orig), ["a"] * 550)
        self.assertEqual(len(tree_json(t_cnf)["c"]), 2)


class TestTokenizer(unittest.TestCase):
    def test_tokens(self):
        g = load_grammar(G / "expresiones.txt")
        self.assertEqual(tokenize("(id+id)*id", g.terminals), ["(", "id", "+", "id", ")", "*", "id"])
        self.assertEqual(tokenize("ε", g.terminals), [])
        g2 = load_grammar(G / "ingles.txt")
        self.assertEqual(tokenize("She eats a cake.", g2.terminals), ["she", "eats", "a", "cake"])
        with self.assertRaises(ValueError):
            tokenize("she barks", g2.terminals)
        with self.assertRaises(ValueError):
            tokenize("idid", g.terminals)


if __name__ == "__main__":
    unittest.main()
