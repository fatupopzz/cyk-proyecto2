// Lee [[gramatica, frase|null], ...] por stdin y escribe los análisis del motor JS.
const engine = require("../web/cyk-engine.js");
let buf = "";
process.stdin.on("data", (d) => (buf += d));
process.stdin.on("end", () => {
  const cases = JSON.parse(buf);
  const out = cases.map(([g, s]) => engine.analyze(g, s, 20));
  process.stdout.write(JSON.stringify(out));
});
