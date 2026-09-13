"""Previzualizări: cum arată asamblat, şi unde cad planele de tăiere.

Desenele au fundal transparent, nu alb. Aplicaţia se foloseşte mai ales de pe
laptop, unde imaginile sunt mari şi stau pe cartonul aplicaţiei: un dreptunghi
alb în jurul capului se vedea ca un petic, iar pe tema întunecată ar fi fost o
lanternă. Aşa, fundalul cardului trece prin ele în ambele teme.
"""
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
    img = np.zeros((H, lat_px, 4), np.uint8)
    ox, oy = -min(xs) / esc + 20, -min(ys) / esc + 20

    for i, pl in enumerate(placi):
        f = i / max(len(placi) - 1, 1)
        umbra = (int(196 - 76 * f), int(208 - 46 * f), int(172 + 72 * f), 255)
        ext = pl.silueta
        for c in ext:
            cv2.fillPoly(img, [_puncte(c, esc, ox, oy)], umbra)
        for c in ext:
            cv2.polylines(img, [_puncte(c, esc, ox, oy)], True, (105, 90, 76, 255), 1, cv2.LINE_AA)
    ok, buf = cv2.imencode(".png", img)
    return buf.tobytes() if ok else b""


def plane(z, cap, reglaje, mm_pe_px, lat_px: int = 480) -> bytes:
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
    img = np.zeros((PH, PW, 4), np.uint8)

    poli = [(22, 12)]
    for i in range(L):
        poli.append((int(22 + d[i] / esc), int(12 + i * mm_pe_px / esc)))
    poli.append((22, PH - 12))
    # Capul NU se umple. Numai plăcile au material; între ele trebuie să se
    # vadă fundalul paginii, altfel golul arată tot a ceva.

    # Plăcile se desenează aşa cum sunt: dreptunghiuri.
    #
    # O placă e o foaie plată. Conturul ei e uniunea a tot ce cade în felia de
    # adâncime -- `sel = (hh >= niv[k]) & (hh < niv[k] + pas)` în feliator --
    # deci nu se schimbă pe toată grosimea tablei. Desenul o tăia după curba
    # capului, ceea ce sugera un detaliu pe muchie pe care tabla nu-l are:
    # muchia unei plăci e un perete drept, iar tot detaliul stă în contur.
    #
    # Aşa se vede şi scara adevărată a obiectului: treapta dintre plăci e exact
    # grosimea tablei, iar asta e rezoluţia reliefului, nu o aproximaţie.
    nn = float(np.hypot(na, nb)) or 1.0
    pas = reglaje.grosime_mm * reglaje.sari
    proiectii = (np.arange(L) * mm_pe_px) * na + d * nb

    inauntru = np.zeros(img.shape[:2], np.uint8)
    cv2.fillPoly(inauntru, [np.array(poli, np.int32)], 255)

    # Coordonatele fiecărui pixel în sistemul felierii: `pr` de-a lungul
    # normalei (adică numărul plăcii), `sp` perpendicular pe ea (adică poziţia
    # în conturul plăcii).
    yy, xx = np.mgrid[0:img.shape[0], 0:img.shape[1]]
    Dm = (xx - 22) * esc
    Hm = (yy - 12) * esc
    pr = (Hm * na + Dm * nb) / nn
    sp = (-Hm * nb + Dm * na) / nn

    cap_px = inauntru > 0
    metal = np.zeros(img.shape[:2], bool)
    k = float(proiectii.min())
    while k < proiectii.max():
        felie = cap_px & (pr >= k / nn) & (pr < (k + reglaje.grosime_mm) / nn)
        if felie.any():
            # Conturul plăcii: cât se întinde tot ce cade în felie. Constant pe
            # toată grosimea -- de aici dreptunghiul.
            lo, hi = sp[felie].min(), sp[felie].max()
            banda = (pr >= k / nn) & (pr < (k + reglaje.grosime_mm) / nn)
            metal |= banda & (sp >= lo) & (sp <= hi)
        k += pas

    img[metal] = (150, 163, 176, 255)
    contur = metal.astype(np.uint8) - cv2.erode(metal.astype(np.uint8),
                                                np.ones((3, 3), np.uint8))
    img[contur > 0] = (96, 112, 128, 255)

    # Conturul capului, ca reper: se vede cât din formă prinde fiecare placă.
    cv2.polylines(img, [np.array(poli, np.int32)], False,
                  (150, 136, 120, 110), 1, cv2.LINE_AA)

    ok, buf = cv2.imencode(".png", img)
    return buf.tobytes() if ok else b""
