"""Relieful, tăiat în plăci.

Solidul e relieful cu spatele plat -- obiectul care se agaţă pe perete. Norul
de puncte al solidului se construieşte o singură dată; după el, orice unghi de
tăiere costă doar un produs scalar. De aceea reglajele din interfaţă răspund
imediat: modelele grele au rulat deja.

Ce se decupează din fiecare placă e regula care ţine la orice unghi: dintr-o
placă se vede doar ce nu acoperă vecinele ei. La feliere frontală vecina e
placa următoare, care stă în întregime înăuntru; la felii orizontale sunt
două, deasupra şi dedesubt. Se scade deci intersecţia vecinelor, erodată cu o
margine de lipire -- şi merge în ambele cazuri, fără ramificaţie.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class Reglaje:
    grosime_mm: float = 3.0
    adancime_mm: float = 60.0      # relieful comprimat la atât
    inclinare: float = 0.0         # 0 = plane paralele cu faţa
    rotire: float = 0.0            # 90 = plane verticale
    sari: int = 1                  # 1 = fiecare strat, 2 = strat-gol-strat
    goleste: bool = True
    margine_mm: float = 12.0       # suprapunerea de lipire
    kerf_mm: float = 0.2
    curba: float = 0.75            # <1 păstrează relieful feţei la comprimare
    netezire: float = 1.2          # mm; marginea segmentării e zimţată


@dataclass
class Placa:
    indice: int
    repetari: int
    contururi: list                # ce se taie: exterior + găurile de golire
    silueta: list                  # conturul plin, înainte de golire
    arie_cm2: float
    bucati: int


class Solid:
    """Norul de puncte al reliefului. Construit o dată, tăiat de oricâte ori."""

    def __init__(self, z: np.ndarray, cap: np.ndarray, mm_pe_px: float,
                 lat_lucru: int = 420):
        H, W = z.shape
        s = lat_lucru / W
        zs = cv2.resize(np.nan_to_num(z), (int(W * s), int(H * s)),
                        interpolation=cv2.INTER_AREA)
        cs = cv2.resize(cap.astype(np.uint8), (int(W * s), int(H * s)),
                        interpolation=cv2.INTER_NEAREST) > 0
        self.mm = mm_pe_px / s
        self.forma = zs.shape
        self._z = np.where(cs, zs, np.nan)
        self._cap = cs

    def _comprimat(self, r: Reglaje) -> np.ndarray:
        z, cap = self._z, self._cap
        lo, hi = np.percentile(z[cap], [0.5, 99.8])
        t = np.clip((z - lo) / max(hi - lo, 1e-9), 0, 1) ** r.curba
        return np.where(cap, t * (r.adancime_mm / self.mm), np.nan)

    def _puncte(self, r: Reglaje) -> np.ndarray:
        """(x, y, w) pentru fiecare voxel plin. Spatele e plat, la w = 0."""
        zc = self._comprimat(r)
        h, w = zc.shape
        D = int(np.ceil(np.nanmax(zc))) + 1
        ws = np.arange(D)[None, None, :]
        plin = (ws <= np.nan_to_num(zc, nan=-1)[:, :, None])
        idx = np.argwhere(plin)
        return np.stack([idx[:, 1], idx[:, 0], idx[:, 2]], 1).astype(np.float32)

    def felieaza(self, r: Reglaje) -> tuple[list[Placa], dict]:
        P = self._puncte(r)
        a, b = np.radians(r.inclinare), np.radians(r.rotire)
        n = np.array([np.sin(b) * np.cos(a), np.sin(a), np.cos(b) * np.cos(a)])
        n /= np.linalg.norm(n)
        tmp = np.array([0., 0., 1.]) if abs(n[1]) > 0.9 else np.array([0., 1., 0.])
        u = np.cross(tmp, n); u /= np.linalg.norm(u)
        v = np.cross(n, u)

        hh = P @ n
        U, V = P @ u, P @ v
        pas = r.grosime_mm / self.mm
        niv = np.arange(hh.min(), hh.max(), pas)

        # Toate plăcile într-o pânză comună, ca poziţiile relative să se
        # păstreze: la montaj contează unde stă fiecare faţă de celelalte.
        u0, v0 = U.min() - 4, V.min() - 4
        LU = int(U.max() - u0) + 8
        LV = int(V.max() - v0) + 8

        masti = []
        for k in range(0, len(niv), r.sari):
            sel = (hh >= niv[k]) & (hh < niv[k] + pas)
            if sel.sum() < 40:
                continue
            m = np.zeros((LV, LU), np.uint8)
            m[np.round(V[sel] - v0).astype(int), np.round(U[sel] - u0).astype(int)] = 1
            m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
            m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
            masti.append(m)

        masti = self._contopeste(masti, r)
        placi = self._decupeaza(masti, r)
        info = {
            "placi": sum(p.repetari for p in placi),
            "contururi": len(placi),
            "inaltime_teanc_mm": round(sum(p.repetari for p in placi) * r.grosime_mm
                                       + (r.sari - 1) * r.grosime_mm * max(len(placi) - 1, 0), 1),
            "arie_dm2": round(sum(p.arie_cm2 * p.repetari for p in placi) / 100, 2),
        }
        return placi, info

    def _contopeste(self, masti, r: Reglaje):
        """Unde conturul nu se schimbă între niveluri, e aceeaşi placă repetată.

        La marginea siluetei suprafaţa e aproape paralelă cu privirea şi
        nivelurile se înghesuie: inele sub un milimetru, imposibil de tăiat şi
        de lipit. Nu se pierde nimic contopindu-le -- se taie de mai multe ori
        acelaşi contur."""
        prag = 2.0 / self.mm
        out, i = [], 0
        while i < len(masti):
            j = i + 1
            while j < len(masti):
                a, b = masti[i].astype(bool), masti[j].astype(bool)
                # Contopirea are sens doar între plăci cuibărite. La feliere
                # frontală placa următoare stă în întregime în cea dinainte; la
                # felii orizontale nu, iar „inelul" dintre ele n-ar însemna
                # nimic. Prima versiune contopea oricum şi strivea 76 de felii
                # orizontale în 3 contururi.
                if (b & ~a).sum() > 0.02 * b.sum():
                    break
                inel = a & ~b
                if inel.any():
                    d = cv2.distanceTransform(inel.astype(np.uint8), cv2.DIST_L2, 5)
                    if 2 * d.max() >= prag:
                        break
                j += 1
            out.append((masti[i], j - i))
            i = j
        return out

    def _decupeaza(self, masti, r: Reglaje) -> list[Placa]:
        placi = []
        k_er = max(int(r.margine_mm / self.mm) | 1, 3)
        ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_er, k_er))
        kerf_px = r.kerf_mm / 2 / self.mm

        for i, (m, rep) in enumerate(masti):
            vizibil = m
            if r.goleste and len(masti) > 1:
                vecini = [masti[j][0] for j in (i - 1, i + 1) if 0 <= j < len(masti)]
                ascuns = vecini[0]
                for w in vecini[1:]:
                    ascuns = ascuns & w
                ascuns = cv2.erode(ascuns, ker)
                vizibil = (m.astype(bool) & ~ascuns.astype(bool)).astype(np.uint8)
                if vizibil.sum() < 0.02 * m.sum():
                    vizibil = m

            # Silueta plină: ce se vede din faţă. Golirea scoate numai
            # material acoperit de placa următoare, deci vederea asamblată
            # trebuie desenată din conturul dinainte de golire -- altfel apar
            # găuri care în obiect nu se văd niciodată.
            plin_cn, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            silueta = [(self._neteze(c, r) * self.mm).round(3).tolist()
                       for c in plin_cn if cv2.contourArea(c) >= (3.0 / self.mm) ** 2]

            cn, ier = cv2.findContours(vizibil, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
            contururi = []
            for c, h in zip(cn, ier[0] if ier is not None else []):
                if cv2.contourArea(c) < (3.0 / self.mm) ** 2:
                    continue
                pts = self._neteze(c, r)
                # Kerf: scula mănâncă material, deci conturul exterior se
                # umflă şi găurile se strâng. Fără asta tot portretul iese
                # subţiat cu o jumătate de tăietură pe fiecare margine.
                gaura = h[3] >= 0
                pts = self._ofseteaza(pts, -kerf_px if gaura else kerf_px)
                contururi.append((pts * self.mm).round(3).tolist())
            if contururi:
                placi.append(Placa(indice=len(placi), repetari=rep,
                                   contururi=contururi, silueta=silueta,
                                   arie_cm2=float(vizibil.sum() * self.mm ** 2 / 100),
                                   bucati=sum(1 for c, h in zip(cn, ier[0]) if h[3] < 0
                                              and cv2.contourArea(c) >= (3.0 / self.mm) ** 2)))
        return placi

    def _neteze(self, c, r: Reglaje) -> np.ndarray:
        p = c[:, 0, :].astype(np.float64)
        if len(p) < 8:
            return p
        w = max(int(r.netezire / self.mm) | 1, 3)
        ker = np.ones(w) / w
        pad = np.vstack([p[-w:], p, p[:w]])
        s = np.stack([np.convolve(pad[:, 0], ker, "same"),
                      np.convolve(pad[:, 1], ker, "same")], 1)[w:-w]
        eps = 0.25 / self.mm
        ap = cv2.approxPolyDP(s.astype(np.float32).reshape(-1, 1, 2), eps, True)
        return ap[:, 0, :].astype(np.float64)

    @staticmethod
    def _ofseteaza(p: np.ndarray, d: float) -> np.ndarray:
        """Deplasează conturul cu d pe normala exterioară. Aproximare bună la
        distanţe mici faţă de raza de curbură -- iar kerful e tocmai asta."""
        if abs(d) < 1e-6 or len(p) < 3:
            return p
        ant, urm = np.roll(p, 1, 0), np.roll(p, -1, 0)
        t = urm - ant
        L = np.hypot(t[:, 0], t[:, 1])
        L[L < 1e-9] = 1
        nx, ny = t[:, 1] / L, -t[:, 0] / L
        if cv2.contourArea(p.astype(np.float32)) < 0:
            nx, ny = -nx, -ny
        return p + np.stack([nx, ny], 1) * d
