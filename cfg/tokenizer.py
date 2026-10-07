"""Convierte la frase de entrada en la lista de terminales de la gramática.

* Separa por espacios.
* Si un pedazo no es un terminal, lo parte en palabras y signos:
  'id+id*id' -> id + id * id,  '(id)' -> ( id ).
  Las palabras deben coincidir completas con un terminal; los signos se
  parten con "longest match" (por si hay terminales como '**' o '->').
* Si no coincide exacto, prueba sin distinguir mayúsculas ('She' -> 'she').
* Ignora un punto o signo final ('... with a fork.') si no es terminal.
"""

from __future__ import annotations

import re


class TokenizeError(ValueError):
    def __init__(self, msg: str, bad: str):
        super().__init__(msg)
        self.bad = bad


_PIECES = re.compile(r"\w+|[^\w\s]+")


def tokenize(text: str, terminals) -> list[str]:
    terms = set(terminals)
    lower: dict[str, str] = {}
    for t in sorted(terms):
        lower.setdefault(t.lower(), t)
    punct_terms = sorted((t for t in terms if not re.fullmatch(r"\w+", t)), key=len, reverse=True)

    def resolve(s: str) -> str | None:
        if s in terms:
            return s
        return lower.get(s.lower())

    def fail(piece: str):
        raise TokenizeError(f"«{piece}» no es un terminal de la gramática", piece)

    out: list[str] = []
    chunks = text.strip().split()
    if len(chunks) == 1 and chunks[0] in ("ε", "λ") and chunks[0] not in terms:
        return []  # cadena vacía explícita
    for idx, chunk in enumerate(chunks):
        # punto final de oración
        if idx == len(chunks) - 1 and len(chunk) > 1 and chunk[-1] in ".!?" \
                and resolve(chunk) is None and chunk[-1] not in terms:
            chunk = chunk[:-1]
        hit = resolve(chunk)
        if hit is not None:
            out.append(hit)
            continue
        for m in _PIECES.finditer(chunk):
            piece = m.group()
            hit = resolve(piece)
            if hit is not None:
                out.append(hit)
                continue
            if re.fullmatch(r"\w+", piece):
                fail(piece)
            pos = 0
            while pos < len(piece):
                for cand in punct_terms:
                    if piece.startswith(cand, pos):
                        out.append(cand)
                        pos += len(cand)
                        break
                else:
                    fail(piece[pos:])
    return out
