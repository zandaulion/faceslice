"""Plăcile, ca fişier pentru maşina de tăiat.

DXF R12, cu POLYLINE şi nu LWPOLYLINE: e formatul cel mai vechi şi de aceea
cel pe care îl citeşte orice atelier, indiferent cu ce lucrează.

Două straturi, fiindcă maşina trebuie să le trateze altfel:

  TAIERE    conturul propriu-zis
  GRAVARE   numărul plăcii şi conturul plăcii următoare

Conturul gravat e răspunsul la alinierea teancului. Fără el, plăcile se aşază
din ochi şi portretul iese strâmb; cu găuri şi tije, găurile trebuie să încapă
în fiecare inel, ceea ce la vârful nasului nu se poate. Gravat, montajul devine
o instrucţiune: pui placa următoare exact pe linia desenată.
"""
from __future__ import annotations

import io
from dataclasses import dataclass


@dataclass
class Coala:
    latime_mm: float = 1000.0
    inaltime_mm: float = 500.0
    spatiu_mm: float = 6.0        # între piese, ca tăieturile să nu se atingă
    margine_mm: float = 10.0


def _limite(contururi):
    xs = [p[0] for c in contururi for p in c]
    ys = [p[1] for c in contururi for p in c]
    return min(xs), min(ys), max(xs), max(ys)


def impacheteaza(placi, coala: Coala):
    """Aşază piesele pe coli, pe rafturi. Ordonate descrescător după înălţime,
    ca rândurile să iasă strânse -- e cea mai simplă regulă care nu risipeşte."""
    piese = []
    for p in placi:
        x0, y0, x1, y1 = _limite(p.contururi)
        for k in range(p.repetari):
            piese.append({"placa": p, "exemplar": k, "w": x1 - x0, "h": y1 - y0,
                          "dx": -x0, "dy": -y0})
    piese.sort(key=lambda q: -q["h"])

    coli, cur, x, y, h_raft = [], [], coala.margine_mm, coala.margine_mm, 0.0
    util_w = coala.latime_mm - coala.margine_mm
    util_h = coala.inaltime_mm - coala.margine_mm
    for q in piese:
        if x + q["w"] > util_w:
            x = coala.margine_mm
            y += h_raft + coala.spatiu_mm
            h_raft = 0.0
        if y + q["h"] > util_h:
            coli.append(cur)
            cur, x, y, h_raft = [], coala.margine_mm, coala.margine_mm, 0.0
        q["x"], q["y"] = x, y
        cur.append(q)
        x += q["w"] + coala.spatiu_mm
        h_raft = max(h_raft, q["h"])
    if cur:
        coli.append(cur)
    return coli


def _g(out, cod, val):
    out.write(f"{cod}\n{val}\n")


def _polilinie(out, pts, strat, inchisa=True):
    _g(out, 0, "POLYLINE"); _g(out, 8, strat); _g(out, 66, 1)
    _g(out, 70, 1 if inchisa else 0)
    for x, y in pts:
        _g(out, 0, "VERTEX"); _g(out, 8, strat)
        _g(out, 10, f"{x:.4f}"); _g(out, 20, f"{y:.4f}"); _g(out, 30, "0.0")
    _g(out, 0, "SEQEND"); _g(out, 8, strat)


def _text(out, x, y, h, s, strat):
    _g(out, 0, "TEXT"); _g(out, 8, strat)
    _g(out, 10, f"{x:.4f}"); _g(out, 20, f"{y:.4f}"); _g(out, 30, "0.0")
    _g(out, 40, f"{h:.4f}"); _g(out, 1, s)


def scrie_dxf(coala_piese, urmatoarele: dict, coala: Coala) -> str:
    out = io.StringIO()
    _g(out, 0, "SECTION"); _g(out, 2, "HEADER")
    _g(out, 9, "$INSUNITS"); _g(out, 70, 4)          # milimetri
    _g(out, 9, "$EXTMIN"); _g(out, 10, "0.0"); _g(out, 20, "0.0"); _g(out, 30, "0.0")
    _g(out, 9, "$EXTMAX"); _g(out, 10, f"{coala.latime_mm:.1f}")
    _g(out, 20, f"{coala.inaltime_mm:.1f}"); _g(out, 30, "0.0")
    _g(out, 0, "ENDSEC")

    _g(out, 0, "SECTION"); _g(out, 2, "TABLES")
    _g(out, 0, "TABLE"); _g(out, 2, "LAYER"); _g(out, 70, 2)
    for nume, culoare in (("TAIERE", 1), ("GRAVARE", 3)):
        _g(out, 0, "LAYER"); _g(out, 2, nume); _g(out, 70, 0)
        _g(out, 62, culoare); _g(out, 6, "CONTINUOUS")
    _g(out, 0, "ENDTAB"); _g(out, 0, "ENDSEC")

    _g(out, 0, "SECTION"); _g(out, 2, "ENTITIES")
    for q in coala_piese:
        ox, oy = q["x"] + q["dx"], q["y"] + q["dy"]
        p = q["placa"]
        for c in p.contururi:
            _polilinie(out, [(x + ox, y + oy) for x, y in c], "TAIERE")

        urm = urmatoarele.get(p.indice)
        if urm:
            for c in urm:
                _polilinie(out, [(x + ox, y + oy) for x, y in c], "GRAVARE")

        et = f"{p.indice + 1}" + (f".{q['exemplar'] + 1}" if p.repetari > 1 else "")
        _text(out, q["x"] + 2, q["y"] + 2, 5.0, et, "GRAVARE")
    _g(out, 0, "ENDSEC"); _g(out, 0, "EOF")
    return out.getvalue()


def exporta(placi, coala: Coala) -> list[tuple[str, str]]:
    """-> [(nume fişier, conţinut DXF)] -- câte unul pe coală."""
    # Conturul următoarei plăci, gravat pe cea de acum: reperul de montaj.
    urmatoarele = {}
    for i, p in enumerate(placi[:-1]):
        urmatoarele[p.indice] = placi[i + 1].contururi
    coli = impacheteaza(placi, coala)
    return [(f"coala-{i + 1}.dxf", scrie_dxf(c, urmatoarele, coala))
            for i, c in enumerate(coli)]
