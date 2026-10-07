// Generado por build_presets.py a partir de grammars/ y pruebas/. No editar a mano.
window.CYK_PRESETS = [
  {
    "id": "ingles",
    "label": "Inglés (enunciado)",
    "file": "grammars/ingles.txt",
    "grammar": "# Gramática de ejemplo del enunciado (Proyecto 2, Teoría de la Computación)\nS  -> NP VP\nVP -> VP PP\nVP -> V NP\nVP -> cooks | drinks | eats | cuts\nPP -> P NP\nNP -> Det N\nNP -> he | she\nV  -> cooks | drinks | eats | cuts\nP  -> in | with\nN  -> cat | dog\nN  -> beer | cake | juice | meat | soup\nN  -> fork | knife | oven | spoon\nDet -> a | the\n",
    "yes": [
      "She eats a cake with a fork",
      "The cat drinks the beer",
      "he cooks",
      "she eats",
      "the dog eats the soup with a spoon",
      "she cuts the meat with a knife in the oven",
      "he drinks the juice in the oven with a spoon",
      "a fork eats the cat",
      "the cat cooks in a cat with the dog"
    ],
    "no": [
      "the cat",
      "eats she",
      "she a cake",
      "cat drinks the beer",
      "the cat drinks beer",
      "she eats a cake with",
      "he he eats",
      "she eats the cake with a fork and a knife",
      "the dog barks"
    ]
  },
  {
    "id": "expresiones",
    "label": "Expresiones con ε",
    "file": "grammars/expresiones.txt",
    "grammar": "# Expresiones aritméticas (LL(1) clásica, con producciones ε)\n# 'e' representa la cadena vacía\nE -> T X\nX -> + T X | e\nT -> F Y\nY -> * F Y | e\nF -> ( E ) | id\n",
    "yes": [
      "id",
      "id + id",
      "id * id",
      "(id+id)*id",
      "id+id*id",
      "((id))",
      "id*(id+id*id)+id",
      "(((id)+id)*(id))"
    ],
    "no": [
      "ε",
      "id +",
      "+ id",
      "(id",
      "id id",
      "()",
      "id**id",
      "id+*id",
      "x + id"
    ]
  },
  {
    "id": "cnf_manual",
    "label": "CNF hecha a mano",
    "file": "grammars/expresiones_cnf_manual.txt",
    "grammar": "# CNF de expresiones.txt hecha a mano (para comparar contra la del programa)\nE -> T X | F Y | L Z | id\nX -> P W | P T\nT -> F Y | L Z | id\nY -> M V | M F\nF -> L Z | id\nZ -> E R\nW -> T X\nV -> F Y\nL -> (\nR -> )\nP -> +\nM -> *\n",
    "yes": [
      "id",
      "id + id",
      "id * id",
      "(id+id)*id",
      "id+id*id",
      "((id))",
      "id*(id+id*id)+id",
      "(((id)+id)*(id))"
    ],
    "no": [
      "ε",
      "id +",
      "+ id",
      "(id",
      "id id",
      "()",
      "id**id",
      "id+*id",
      "x + id"
    ]
  },
  {
    "id": "ambigua",
    "label": "Expresiones ambigua",
    "file": "grammars/ambigua.txt",
    "grammar": "# Gramática ambigua de expresiones (para probar el conteo de árboles)\nE -> E + E | E * E | ( E ) | id\n",
    "yes": [
      "id+id*id",
      "id+id+id+id",
      "(id+id)*id",
      "id*id*id*id*id",
      "((id))"
    ],
    "no": [
      "id+",
      "id id",
      "(id",
      "*id"
    ]
  }
];
