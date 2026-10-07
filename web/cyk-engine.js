/*
 * Motor CYK en JavaScript: traducción directa de cfg/ (Python).
 * Produce el mismo JSON que cfg/export.py:analyze, para que la interfaz
 * funcione igual con el motor de Python (app.py) o solo en el navegador.
 * tests/test_engines.py compara ambos motores salida por salida.
 */
(function (root) {
  "use strict";

  // ---------------------------------------------------------------- árboles
  const EPS = "ε";
  const Slot = (i) => ({ slot: i });
  const Node = (s, c) => ({ s, c });
  const Leaf = (t) => ({ t });
  const EPS_LEAF = { e: 1 };

  function subst(pattern, f) {
    const out = [];
    for (const it of pattern) {
      if (it.slot !== undefined) out.push(...f(it.slot));
      else if (it.s !== undefined) out.push(Node(it.s, subst(it.c, f)));
      else out.push(it);
    }
    return out;
  }

  // -------------------------------------------------------------- gramática
  const EPS_TOKENS = new Set(["ε", "e", "eps", "epsilon", "λ", "lambda", "''", '""']);
  const ARROWS = ["->", "→", "::="];

  class GrammarError extends Error {}

  const key = (lhs, rhs) => lhs + "\u0000" + rhs.join("\u0001");

  class Grammar {
    constructor(start) {
      this.start = start;
      this.order = [];
      this.prods = new Map();
      this.keys = new Set();
    }
    addNt(a) {
      if (!this.prods.has(a)) { this.prods.set(a, []); this.order.push(a); }
    }
    add(lhs, rhs, pattern) {
      this.addNt(lhs);
      const k = key(lhs, rhs);
      if (this.keys.has(k)) return false;
      this.keys.add(k);
      this.prods.get(lhs).push({ lhs, rhs: rhs.slice(), pattern: pattern === undefined ? null : pattern });
      return true;
    }
    isNt(s) { return this.prods.has(s); }
    get(a) { return this.prods.get(a) || []; }
    *all() { for (const a of this.order) yield* this.prods.get(a); }
    get nonterminals() {
      const nts = this.order.filter((a) => this.prods.get(a).length);
      const i = nts.indexOf(this.start);
      if (i >= 0) { nts.splice(i, 1); nts.unshift(this.start); }
      return nts;
    }
    get terminals() {
      const seen = new Set();
      for (const p of this.all()) for (const s of p.rhs) if (!this.isNt(s)) seen.add(s);
      return [...seen];
    }
    symbols() { return new Set([...this.prods.keys(), ...this.terminals]); }
    size() { let n = 0; for (const v of this.prods.values()) n += v.length; return n; }
    fresh(base, taken) {
      const used = this.symbols();
      if (taken) for (const t of taken) used.add(t);
      if (!used.has(base)) return base;
      let k = 1;
      while (used.has(base + k)) k++;
      return base + k;
    }
  }

  function originalPattern(lhs, rhs) {
    if (!rhs.length) return [Node(lhs, [EPS_LEAF])];
    return [Node(lhs, rhs.map((_, i) => Slot(i)))];
  }

  function pySplit(s) { const t = s.trim(); return t ? t.split(/\s+/) : []; }

  function parseGrammar(text) {
    const raw = [];
    text.split(/\r\n|\r|\n/).forEach((line, idx) => {
      const lineno = idx + 1;
      line = line.trimStart().startsWith("#") ? "" : line.split("#")[0].trim();
      if (!line) return;
      const arrow = ARROWS.find((a) => line.includes(a));
      if (!arrow) throw new GrammarError(`Línea ${lineno}: falta '->' en «${line}»`);
      const at = line.indexOf(arrow);
      const lhs = line.slice(0, at).trim();
      const rhs = line.slice(at + arrow.length);
      if (!lhs || pySplit(lhs).length !== 1) throw new GrammarError(`Línea ${lineno}: lado izquierdo inválido «${lhs}»`);
      raw.push([lhs, rhs.split("|").map(pySplit)]);
    });
    if (!raw.length) throw new GrammarError("La gramática está vacía");
    const nts = new Set(raw.map((r) => r[0]));
    const g = new Grammar(raw[0][0]);
    for (const [lhs, alts] of raw) {
      g.addNt(lhs);
      for (const toks of alts) {
        let rhs;
        if (!toks.length || (toks.length === 1 && EPS_TOKENS.has(toks[0]) && !nts.has(toks[0]))) rhs = [];
        else rhs = toks.filter((t) => t !== "ε" && t !== "λ");
        g.add(lhs, rhs, originalPattern(lhs, rhs));
      }
    }
    return g;
  }

  // -------------------------------------------------------------------- CNF
  const isUnit = (g, p) => p.rhs.length === 1 && g.isNt(p.rhs[0]);
  const str = (p) => `${p.lhs} → ${p.rhs.length ? p.rhs.join(" ") : "ε"}`;

  function stepStart(g) {
    const onRhs = [...g.all()].some((p) => p.rhs.includes(g.start));
    if (!onRhs) return { key: "START", title: "Símbolo inicial", grammar: g,
      notes: [`${g.start} no aparece en ningún lado derecho: no hace falta S0.`] };
    const s0 = g.fresh(g.start + "0");
    const ng = new Grammar(s0);
    ng.add(s0, [g.start], [Slot(0)]);
    for (const p of g.all()) ng.add(p.lhs, p.rhs, p.pattern);
    return { key: "START", title: "Símbolo inicial", grammar: ng,
      notes: [`${g.start} aparece en un lado derecho, se agrega ${s0} → ${g.start}.`] };
  }

  function nullableWitnesses(g) {
    const wit = new Map();
    let changed = true;
    while (changed) {
      changed = false;
      for (const p of g.all()) {
        if (wit.has(p.lhs)) continue;
        if (p.rhs.every((s) => wit.has(s))) {
          wit.set(p.lhs, subst(p.pattern, (i) => wit.get(p.rhs[i])));
          changed = true;
        }
      }
    }
    return wit;
  }

  function stepDel(g) {
    const wit = nullableWitnesses(g);
    const ng = new Grammar(g.start);
    const removed = [];
    for (const p of g.all()) {
      if (!p.rhs.length) { if (p.lhs !== g.start) removed.push(str(p)); continue; }
      const pos = [];
      p.rhs.forEach((s, i) => { if (wit.has(s)) pos.push(i); });
      const k = pos.length;
      for (let m = 0; m < (1 << k); m++) {
        const omit = new Set();
        for (let j = 0; j < k; j++) if ((m >> (k - 1 - j)) & 1) omit.add(pos[j]);
        const kept = [];
        for (let i = 0; i < p.rhs.length; i++) if (!omit.has(i)) kept.push(i);
        if (!kept.length && p.lhs !== g.start) continue;
        const newIndex = new Map(kept.map((old, nw) => [old, nw]));
        const pattern = subst(p.pattern, (i) => (omit.has(i) ? wit.get(p.rhs[i]) : [Slot(newIndex.get(i))]));
        ng.add(p.lhs, kept.map((i) => p.rhs[i]), pattern);
      }
    }
    if (wit.has(g.start)) ng.add(g.start, [], wit.get(g.start));
    for (const a of g.order) ng.addNt(a);
    const nulls = g.order.filter((a) => wit.has(a));
    const notes = [nulls.length ? "Anulables: {" + nulls.join(", ") + "}" : "No hay símbolos anulables."];
    if (removed.length) notes.push("Se eliminan: " + removed.join(", "));
    if (wit.has(g.start)) notes.push(`ε ∈ L(G): se conserva ${g.start} → ε.`);
    return { key: "DEL", title: "Eliminar producciones ε", grammar: ng, notes };
  }

  function stepUnit(g) {
    const ng = new Grammar(g.start);
    const pairs = [];
    for (const a of g.order) {
      ng.addNt(a);
      const chains = new Map([[a, [Slot(0)]]]);
      const queue = [a];
      while (queue.length) {
        const b = queue.shift();
        for (const p of g.get(b)) {
          if (isUnit(g, p) && !chains.has(p.rhs[0])) {
            chains.set(p.rhs[0], subst(chains.get(b), () => p.pattern));
            queue.push(p.rhs[0]);
          }
        }
      }
      for (const [b, chain] of chains) {
        if (b !== a) pairs.push(`(${a},${b})`);
        for (const p of g.get(b)) if (!isUnit(g, p)) ng.add(a, p.rhs, subst(chain, () => p.pattern));
      }
    }
    const units = [...g.all()].filter((p) => isUnit(g, p)).map(str);
    const notes = units.length
      ? ["Unitarias eliminadas: " + units.join(", "), "Pares unitarios (A =>* B): " + pairs.join(", ")]
      : ["No hay producciones unitarias."];
    return { key: "UNIT", title: "Eliminar producciones unitarias", grammar: ng, notes };
  }

  function stepUseless(g) {
    const gen = new Set();
    let changed = true;
    while (changed) {
      changed = false;
      for (const p of g.all()) {
        if (!gen.has(p.lhs) && p.rhs.every((s) => gen.has(s) || !g.isNt(s))) { gen.add(p.lhs); changed = true; }
      }
    }
    const nonGen = g.order.filter((a) => !gen.has(a));
    const reach = new Set(gen.has(g.start) ? [g.start] : []);
    const queue = [...reach];
    while (queue.length) {
      const a = queue.pop();
      for (const p of g.get(a)) {
        if (p.rhs.every((s) => gen.has(s) || !g.isNt(s))) {
          for (const s of p.rhs) if (g.isNt(s) && !reach.has(s)) { reach.add(s); queue.push(s); }
        }
      }
    }
    const nonReach = g.order.filter((a) => gen.has(a) && !reach.has(a));
    const ng = new Grammar(g.start);
    ng.addNt(g.start);
    for (const p of g.all()) {
      if (reach.has(p.lhs) && p.rhs.every((s) => reach.has(s) || !g.isNt(s))) ng.add(p.lhs, p.rhs, p.pattern);
    }
    const notes = [
      nonGen.length ? "No generadores: {" + nonGen.join(", ") + "}" : "Todos los símbolos son generadores.",
      nonReach.length ? "No alcanzables: {" + nonReach.join(", ") + "}" : "Todos los símbolos son alcanzables.",
    ];
    if (!gen.has(g.start)) notes.push(`${g.start} no genera ninguna cadena: L(G) = ∅.`);
    return { key: "USELESS", title: "Eliminar símbolos inútiles", grammar: ng, notes };
  }

  const PUNCT = { "+": "PLUS", "-": "MINUS", "*": "STAR", "/": "SLASH", "(": "LPAR", ")": "RPAR",
    "[": "LBRACK", "]": "RBRACK", "{": "LBRACE", "}": "RBRACE", ",": "COMMA", ";": "SEMI", ".": "DOT",
    "=": "EQ", "<": "LT", ">": "GT", "^": "CARET", "!": "BANG", "?": "QMARK", ":": "COLON", "&": "AMP",
    "|": "BAR", "%": "PCT" };

  function termName(a) {
    if (Object.prototype.hasOwnProperty.call(PUNCT, a)) return "T_" + PUNCT[a];
    const clean = a.replace(/[^\p{L}\p{N}_]/gu, "").toUpperCase();
    return "T_" + (clean || "SYM");
  }

  function stepTerm(g) {
    const ng = new Grammar(g.start);
    const names = new Map();
    const taken = new Set();
    for (const p of g.all()) {
      if (p.rhs.length >= 2) {
        for (const s of p.rhs) {
          if (!g.isNt(s) && !names.has(s)) { const nm = g.fresh(termName(s), taken); names.set(s, nm); taken.add(nm); }
        }
      }
    }
    for (const a of g.order) ng.addNt(a);
    for (const p of g.all()) {
      if (p.rhs.length >= 2) ng.add(p.lhs, p.rhs.map((s) => (!g.isNt(s) && names.has(s) ? names.get(s) : s)), p.pattern);
      else ng.add(p.lhs, p.rhs, p.pattern);
    }
    for (const [a, t] of names) ng.add(t, [a], null);
    const notes = names.size
      ? ["Nuevos: " + [...names].map(([a, t]) => `${t} → ${a}`).join(", ")]
      : ["No hay terminales mezclados en reglas largas."];
    return { key: "TERM", title: "Separar terminales", grammar: ng, notes };
  }

  function stepBin(g) {
    const ng = new Grammar(g.start);
    for (const a of g.order) ng.addNt(a);
    const cache = new Map();
    const taken = new Set();
    const created = [];
    const counters = new Map();
    const tk = (tail) => tail.join("\u0001");

    function helper(owner, tail) {
      if (cache.has(tk(tail))) return cache.get(tk(tail));
      counters.set(owner, (counters.get(owner) || 0) + 1);
      let name = g.fresh(`${owner}_${counters.get(owner)}`, taken);
      while (taken.has(name)) {
        counters.set(owner, counters.get(owner) + 1);
        name = g.fresh(`${owner}_${counters.get(owner)}`, taken);
      }
      taken.add(name);
      cache.set(tk(tail), name);
      const rhs = tail.length === 2 ? tail : [tail[0], helper(owner, tail.slice(1))];
      ng.add(name, rhs, null);
      created.push(`${name} → ${rhs.join(" ")}`);
      return name;
    }

    for (const p of g.all()) {
      if (p.rhs.length > 2) ng.add(p.lhs, [p.rhs[0], helper(p.lhs, p.rhs.slice(1))], p.pattern);
      else ng.add(p.lhs, p.rhs, p.pattern);
    }
    const notes = created.length ? ["Auxiliares: " + created.join(", ")] : ["Ya no hay lados derechos con más de 2 símbolos."];
    return { key: "BIN", title: "Binarizar reglas largas", grammar: ng, notes };
  }

  function isCnf(g) {
    const bad = [];
    for (const p of g.all()) {
      if (p.rhs.length === 2 && p.rhs.every((s) => g.isNt(s))) {
        if (p.rhs.includes(g.start)) bad.push(`${str(p)}: el inicial aparece a la derecha`);
        continue;
      }
      if (p.rhs.length === 1 && !g.isNt(p.rhs[0])) continue;
      if (!p.rhs.length && p.lhs === g.start) continue;
      bad.push(str(p));
    }
    return bad;
  }

  function toCnf(g) {
    const steps = [{ key: "ORIG", title: "Gramática original", grammar: g, notes: [] }];
    let cur = g;
    for (const fn of [stepStart, stepDel, stepUnit, stepUseless, stepTerm, stepBin]) {
      const st = fn(cur);
      steps.push(st);
      cur = st.grammar;
    }
    const bad = isCnf(cur);
    if (bad.length) throw new Error("La gramática resultante no está en CNF: " + bad.join("; "));
    return { cnf: cur, steps };
  }

  // -------------------------------------------------------------- tokenizer
  class TokenizeError extends Error {}
  const WORD = /^[\p{L}\p{N}_]+$/u;

  function tokenize(text, terminals) {
    const terms = new Set(terminals);
    const lower = new Map();
    for (const t of [...terms].sort()) if (!lower.has(t.toLowerCase())) lower.set(t.toLowerCase(), t);
    const punct = [...terms].filter((t) => !WORD.test(t)).sort((a, b) => b.length - a.length);
    const resolve = (s) => (terms.has(s) ? s : lower.has(s.toLowerCase()) ? lower.get(s.toLowerCase()) : null);
    const fail = (piece) => { throw new TokenizeError(`«${piece}» no es un terminal de la gramática`); };

    const out = [];
    const chunks = pySplit(text);
    if (chunks.length === 1 && (chunks[0] === "ε" || chunks[0] === "λ") && !terms.has(chunks[0])) return [];
    chunks.forEach((chunk0, idx) => {
      let chunk = chunk0;
      if (idx === chunks.length - 1 && chunk.length > 1 && ".!?".includes(chunk[chunk.length - 1])
          && resolve(chunk) === null && !terms.has(chunk[chunk.length - 1])) chunk = chunk.slice(0, -1);
      const hit = resolve(chunk);
      if (hit !== null) { out.push(hit); return; }
      for (const m of chunk.matchAll(/[\p{L}\p{N}_]+|[^\p{L}\p{N}_\s]+/gu)) {
        const piece = m[0];
        const h = resolve(piece);
        if (h !== null) { out.push(h); continue; }
        if (WORD.test(piece)) fail(piece);
        let pos = 0;
        while (pos < piece.length) {
          const cand = punct.find((c) => piece.startsWith(c, pos));
          if (cand === undefined) fail(piece.slice(pos));
          out.push(cand);
          pos += cand.length;
        }
      }
    });
    return out;
  }

  // -------------------------------------------------------------------- CYK
  const now = () => (typeof performance !== "undefined" ? performance.now() : Date.now());

  function cyk(g, tokens) {
    const termIndex = new Map();
    const binIndex = new Map();
    for (const p of g.all()) {
      if (p.rhs.length === 1) { if (!termIndex.has(p.rhs[0])) termIndex.set(p.rhs[0], []); termIndex.get(p.rhs[0]).push(p); }
      else if (p.rhs.length === 2) { const k = key("", p.rhs); if (!binIndex.has(k)) binIndex.set(k, []); binIndex.get(k).push(p); }
    }
    const n = tokens.length;
    const t0 = now();
    if (n === 0) {
      const accepted = g.get(g.start).some((p) => !p.rhs.length);
      return { tokens, accepted, table: [], counts: [], ms: now() - t0, g };
    }
    const table = Array.from({ length: n }, () => new Array(n + 1).fill(null));
    const counts = Array.from({ length: n }, () => new Array(n + 1).fill(null));
    tokens.forEach((a, i) => {
      const cell = new Map(), cnt = new Map();
      for (const p of termIndex.get(a) || []) {
        if (!cell.has(p.lhs)) cell.set(p.lhs, []);
        cell.get(p.lhs).push([p, null]);
        cnt.set(p.lhs, (cnt.get(p.lhs) || 0n) + 1n);
      }
      table[i][1] = cell; counts[i][1] = cnt;
    });
    for (let l = 2; l <= n; l++) {
      for (let i = 0; i <= n - l; i++) {
        const cell = new Map(), cnt = new Map();
        for (let k = 1; k < l; k++) {
          const left = table[i][k], right = table[i + k][l - k];
          if (!left.size || !right.size) continue;
          const lc = counts[i][k], rc = counts[i + k][l - k];
          for (const b of left.keys()) {
            for (const c of right.keys()) {
              const ps = binIndex.get(key("", [b, c]));
              if (!ps) continue;
              for (const p of ps) {
                if (!cell.has(p.lhs)) cell.set(p.lhs, []);
                cell.get(p.lhs).push([p, k]);
                cnt.set(p.lhs, (cnt.get(p.lhs) || 0n) + lc.get(b) * rc.get(c));
              }
            }
          }
        }
        table[i][l] = cell; counts[i][l] = cnt;
      }
    }
    const accepted = table[0][n].has(g.start);
    return { tokens, accepted, table, counts, ms: now() - t0, g };
  }

  function treeCount(r) {
    if (!r.accepted) return 0n;
    if (!r.tokens.length) return 1n;
    return r.counts[0][r.tokens.length].get(r.g.start);
  }

  function derivations(r, limit) {
    const g = r.g;
    if (!r.accepted) return [];
    if (!r.tokens.length) return [[g.get(g.start).find((p) => !p.rhs.length), []]];
    const out = [];
    function* gen(i, l, a) {
      for (const [p, k] of r.table[i][l].get(a)) {
        if (k === null) yield [p, [r.tokens[i]]];
        else {
          const [b, c] = p.rhs;
          for (const left of gen(i, k, b)) for (const right of gen(i + k, l - k, c)) yield [p, [left, right]];
        }
      }
    }
    for (const d of gen(0, r.tokens.length, g.start)) { out.push(d); if (out.length >= limit) break; }
    return out;
  }

  function cnfTree(d) {
    const [p, kids] = d;
    if (!p.rhs.length) return Node(p.lhs, [EPS_LEAF]);
    return Node(p.lhs, kids.map((k) => (typeof k === "string" ? Leaf(k) : cnfTree(k))));
  }

  function forest(d) {
    const [p, kids] = d;
    const flat = [];
    for (const k of kids) { if (typeof k === "string") flat.push(Leaf(k)); else flat.push(...forest(k)); }
    if (p.pattern === null) return flat;
    return subst(p.pattern, (i) => [flat[i]]);
  }

  // ---------------------------------------------------------------- analyze
  const rulesJson = (g) => g.nonterminals.map((a) => ({ lhs: a, alts: g.get(a).map((p) => p.rhs.slice()) }));

  function analyze(grammarText, sentence, maxTrees) {
    if (maxTrees === undefined) maxTrees = 20;
    const out = { error: null, steps: [], cnf: null, original: null, result: null };
    let g;
    try { g = parseGrammar(grammarText); } catch (e) {
      if (e instanceof GrammarError) { out.error = e.message; return out; }
      throw e;
    }
    const t0 = now();
    const { cnf, steps } = toCnf(g);
    out.cnfNs = Math.round((now() - t0) * 1e6);
    out.steps = steps.map((st) => ({ key: st.key, title: st.title, notes: st.notes, start: st.grammar.start, rules: rulesJson(st.grammar) }));
    out.original = { nonterminals: g.nonterminals, terminals: g.terminals, size: g.size() };
    out.cnf = { start: cnf.start, rules: rulesJson(cnf), nonterminals: cnf.nonterminals, terminals: cnf.terminals, size: cnf.size() };
    if (sentence === null || sentence === undefined) return out;

    const res = { tokens: null, tokenError: null, accepted: false, ns: 0, reps: 0, firstNs: 0, treeCount: "0", table: [], trees: [] };
    out.result = res;
    let tokens;
    try { tokens = tokenize(sentence, g.terminals); } catch (e) {
      if (e instanceof TokenizeError) { res.tokenError = e.message; return out; }
      throw e;
    }
    res.tokens = tokens;
    const r = cyk(cnf, tokens);
    // El reloj del navegador tiene poca resolución: se repite hasta juntar 5 ms.
    let total = r.ms, reps = 1;
    while (total < 5 && reps < 1000) { total += cyk(cnf, tokens).ms; reps++; }
    res.accepted = r.accepted;
    res.firstNs = Math.round(r.ms * 1e6);
    res.ns = (total / reps) * 1e6;
    res.reps = reps;
    res.treeCount = treeCount(r).toString();
    const n = tokens.length;
    for (let l = 1; l <= n; l++) {
      const row = [];
      for (let i = 0; i <= n - l; i++) {
        const cell = [];
        for (const [a, backs] of r.table[i][l]) {
          cell.push([a, backs.map(([p, k]) => (k === null ? [null, p.rhs[0]] : [k, p.rhs[0], p.rhs[1]]))]);
        }
        row.push(cell);
      }
      res.table.push(row);
    }
    res.trees = derivations(r, maxTrees).map((d) => {
      const f = forest(d);
      if (f.length !== 1) throw new Error("la raíz debe producir exactamente un árbol");
      return { cnf: cnfTree(d), orig: f[0] };
    });
    return out;
  }

  const api = { analyze, parseGrammar, toCnf, tokenize, cyk, isCnf, EPS };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.CYKEngine = api;
})(typeof window !== "undefined" ? window : globalThis);
