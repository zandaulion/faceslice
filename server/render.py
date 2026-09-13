"""Previzualizări: cum arată asamblat, şi unde cad planele de tăiere."""
from __future__ import annotations

import cv2
import numpy as np


def _puncte(c, mm_pe_px_desen, ox, oy):
    return (np.array(c, np.float32) / mm_pe_px_desen + [ox, oy]).astype(np.int32)


def asamblat(placi, lat_px: int = 720) -> bytes:
    """Vedere din faţă a teancului: se desenează de la bază spre vârf, deci
    fiecare placă acoperă ce e sub ea -- exact ce face şi obiectul."""
    xs = [p[0] for pl in placi for c in pl.silueta for p in c]
    ys = [p[1] for pl in placi for c in pl.silueta for p in c]
    if not xs:
        return b""
    w_mm, h_mm = max(xs) - min(xs), max(ys) - min(ys)
    esc = w_mm / (lat_px - 40)
    H = int(h_mm / esc) + 40
    img = np.full((H, lat_px, 3), 250, np.uint8)
    ox, oy = -min(xs) / esc + 20, -min(ys) / esc + 20

    for i, pl in enumerate(placi):
        f = i / max(len(placi) - 1, 1)
        umbra = (int(196 - 76 * f), int(208 - 46 * f), int(172 + 72 * f))
        ext = pl.silueta
        for c in ext:
            cv2.fillPoly(img, [_puncte(c, esc, ox, oy)], umbra)
        for c in ext:
            cv2.polylines(img, [_puncte(c, esc, ox, oy)], True, (105, 90, 76), 1, cv2.LINE_AA)
    ok, buf = cv2.imencode(".png", img)
    return buf.tobytes() if ok else b""


def plane(z, cap, reglaje, mm_pe_px, lat_px: int = 320) -> bytes:
    """Profilul capului cu planele de tăiere peste el.

    Un unghi e greu de judecat dintr-un număr; peste profil se vede imediat ce
    taie. Vederea se alege după direcţie -- planele verticale nu apar ca linii
    într-un profil lateral, fiindcă sunt perpendiculare pe el.
    """
    zz = np.nan_to_num(z, nan=0.0)
    lo, hi = np.percentile(z[cap], [0.5, 99.8])
    t = np.clip((zz - lo) / max(hi - lo, 1e-9), 0, 1) ** reglaje.curba
    adanc = np.where(cap, t * reglaje.adancime_mm, 0.0)

    a, b = np.radians(reglaje.inclinare), np.radians(reglaje.rotire)
    n = np.array([np.sin(b) * np.cos(a), np.sin(a), np.cos(b) * np.cos(a)])
    lateral = abs(n[0]) <= abs(n[1]) or abs(n[2]) > abs(n[0])

    # Secţiunea se taie la marginile capului, nu peste toată fotografia. Prima
    # versiune desena toate cele 1200 de rânduri ale imaginii, din care capul
    # ocupa o treime: profilul ieşea o dungă subţire într-o pânză de trei ori
    # prea înaltă.
    ys = np.where(cap.any(axis=1))[0]
    xs = np.where(cap.any(axis=0))[0]
    if lateral:
        col = int(np.median(xs))
        d = adanc[ys.min():ys.max() + 1, col]
        na, nb = n[1], n[2]
    else:
        rand = int(np.median(ys))
        d = adanc[rand, xs.min():xs.max() + 1]
        na, nb = n[0], n[2]

    L = len(d)
    lung_mm = L * mm_pe_px
    adanc_mm = max(reglaje.adancime_mm, 1.0)
    # Scara se alege din latura mai mare, ca desenul să încapă în ambele sensuri.
    esc = max(adanc_mm / (lat_px * 0.5), lung_mm / (lat_px * 1.9))
    PW = int(adanc_mm / esc) + 46
    PH = int(lung_mm / esc) + 24
    img = np.full((PH, PW, 3), 250, np.uint8)

    poli = [(22, 12)]
    for i in range(L):
        poli.append((int(22 + d[i] / esc), int(12 + i * mm_pe_px / esc)))
    poli.append((22, PH - 12))
    cv2.fillPoly(img, [np.array(poli, np.int32)], (214, 205, 194))
    cv2.polylines(img, [np.array(poli, np.int32)], False, (120, 106, 92), 2, cv2.LINE_AA)

    nn = float(np.hypot(na, nb)) or 1.0
    pas = reglaje.grosime_mm * reglaje.sari
    proiectii = (np.arange(L) * mm_pe_px) * na + d * nb
    k = float(proiectii.min())
    while k < proiectii.max():
        px, py = na * k / nn**2, nb * k / nn**2
        dx, dy = -nb / nn, na / nn
        p1 = (int(22 + (py - dy * 9000) / esc), int(12 + (px - dx * 9000) / esc))
        p2 = (int(22 + (py + dy * 9000) / esc), int(12 + (px + dx * 9000) / esc))
        cv2.line(img, p1, p2, (70, 130, 220), 1, cv2.LINE_AA)
        k += pas
    ok, buf = cv2.imencode(".png", img)
    return buf.tobytes() if ok else b""
