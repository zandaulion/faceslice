"""De la o fotografie la o hartă de adâncime a capului.

Trei modele, fiecare pentru ce ştie mai bine:

  segmentare   silueta cu păr, urechi şi linia maxilarului
  monocular    forma mare -- craniu, păr -- dar aplatizează faţa
  plasă facială  nas, orbite, buze, dar se opreşte la mijlocul frunţii

Niciunul singur nu dă un cap. Forma mare vine de la monocular, detaliul facial
de la plasă -- şi anume doar diferenţa faţă de propria variantă netezită, ca să
se împrumute relieful nasului fără să se importe şi eventuala eroare de formă
generală a plasei.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, asdict

import cv2
import numpy as np
import onnxruntime as ort
import mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions

MODELE = os.environ.get("MODEL_DIR", "models")
LAT_LUCRU = 900
INTRARE_ADANC = 518          # multiplu de 14, cum cere modelul

# Distanţa dintre pupile: reperul de scară cel mai uşor de cerut cuiva, şi
# singurul lucru din fotografie a cărui mărime reală se poate afla fără riglă.
DIP_IMPLICIT_MM = 63.0


# Cât se amplifică relieful facial peste forma mare.
#
# Nu e un număr ales din ochi. Modelul monocular turteşte feţele -- pielea
# n-are textură din care să deducă adâncime -- iar o fotografie din profil e o
# măsurătoare directă: marginea din faţă a siluetei ESTE curba nasului. Măsurat
# acolo, nasul iese cu 0,21 din cursa reliefului; netezind componentele separat, amestecul nepotenţat dă
# 0,18, iar plasa singură 0,06. La ×1,5 amestecul dă fix 0,21.
DETALIU_IMPLICIT = 1.5


@dataclass
class Reconstructie:
    # Forma mare şi detaliul facial se ţin separat, nu însumate. Amestecul lor
    # e un reglaj pe care omul îl vede pe ecran, iar recombinarea costă o
    # adunare -- faţă de două secunde şi jumătate cât ar lua reconstrucţia din
    # nou la fiecare mişcare de cursor.
    baza: np.ndarray         # de la modelul monocular, potrivit la scara plasei
    detaliu: np.ndarray      # relieful facial, ca abatere de la propria netezire
    alfa: np.ndarray         # trecerea moale de la faţă spre restul capului
    cap: np.ndarray          # masca siluetei
    intors: float            # orientarea capului la poză, în grade
    inclinat: float
    mm_pe_px: float
    dip_px: float
    latime_cap_mm: float
    inaltime_cap_mm: float
    relief_mm: float

    def combina(self, detaliu_x: float = DETALIU_IMPLICIT) -> np.ndarray:
        z = self.baza + detaliu_x * self.alfa * self.detaliu
        return np.where(self.cap, z, np.nan)

    @property
    def z(self) -> np.ndarray:
        return self.combina()

    def rezumat(self) -> dict:
        d = asdict(self)
        for k in ("baza", "detaliu", "alfa", "cap"):
            d.pop(k)
        return {k: (round(v, 2) if isinstance(v, float) else v) for k, v in d.items()}


class Modele:
    """Încărcate o singură dată. Pornirea lor costă mai mult decât o rulare."""

    def __init__(self) -> None:
        self._plasa = None
        self._seg = None
        self._adanc = None

    @property
    def plasa(self):
        if self._plasa is None:
            self._plasa = vision.FaceLandmarker.create_from_options(
                vision.FaceLandmarkerOptions(
                    base_options=BaseOptions(
                        model_asset_path=f"{MODELE}/face_landmarker.task"),
                    running_mode=vision.RunningMode.IMAGE, num_faces=1,
                    output_facial_transformation_matrixes=True,
                    min_face_detection_confidence=0.25))
        return self._plasa

    @property
    def seg(self):
        if self._seg is None:
            self._seg = vision.ImageSegmenter.create_from_options(
                vision.ImageSegmenterOptions(
                    base_options=BaseOptions(
                        model_asset_path=f"{MODELE}/selfie_multiclass.tflite"),
                    running_mode=vision.RunningMode.IMAGE,
                    output_category_mask=True))
        return self._seg

    @property
    def adanc(self):
        if self._adanc is None:
            self._adanc = ort.InferenceSession(
                f"{MODELE}/depth.onnx", providers=["CPUExecutionProvider"])
        return self._adanc


MODELE_INST = Modele()


class PozaNepotrivita(Exception):
    """Fotografia are o faţă, dar nu una din care se poate reconstrui."""


# Cât de întors poate fi capul. Peste atât, două lucruri se strică deodată:
# silueta prinde latura capului în loc de contur, iar distanţa dintre pupile se
# scurtează în imagine, deci scara iese prea mare. La 52° ieşea un cap de 333
# mm. Un cap de adult are între 130 şi 165 mm, aşa că verificăm şi rezultatul,
# nu doar unghiul -- un unghi bun cu un cap absurd înseamnă tot o poză proastă.
UNGHI_MAX = 20.0
LATIME_CAP_PLAUZIBILA = (120.0, 180.0)


class FaraFata(Exception):
    """Fotografia nu conţine o faţă utilizabilă."""


def _mp_image(bgr: np.ndarray) -> mp.Image:
    return mp.Image(image_format=mp.ImageFormat.SRGB,
                    data=cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))


def _unghiuri(res) -> tuple[float, float]:
    """Cât e întors şi cât e înclinat capul, în grade."""
    if not res.facial_transformation_matrixes:
        return 0.0, 0.0
    M = np.array(res.facial_transformation_matrixes[0])
    intors = float(np.degrees(np.arctan2(-M[2, 0], np.hypot(M[2, 1], M[2, 2]))))
    inclinat = float(np.degrees(np.arctan2(M[2, 1], M[2, 2])))
    return intors, inclinat


def _plasa_faciala(img: np.ndarray) -> tuple[np.ndarray, float, float, float]:
    """Adâncimea feţei din plasă, distanţa dintre pupile, şi orientarea capului."""
    H, W = img.shape[:2]
    res = MODELE_INST.plasa.detect(_mp_image(img))
    if not res.face_landmarks:
        raise FaraFata("Nu am găsit o faţă în fotografie.")
    intors, inclinat = _unghiuri(res)
    lm = res.face_landmarks[0]
    P = np.array([[p.x * W, p.y * H, p.z * W] for p in lm], np.float64)

    # 468 şi 473 sunt centrele irisurilor în plasa cu puncte rafinate.
    dip = float(np.hypot(*(P[468, :2] - P[473, :2]))) if len(P) > 473 else \
        float(np.hypot(*(P[33, :2] - P[263, :2])))

    # Pupilele se apropie în imagine când capul e întors, deci scara iese
    # prea mare. Corecţia e mică în intervalul acceptat, dar e gratuită.
    dip /= max(np.cos(np.radians(intors)), 0.5)

    from scipy.spatial import Delaunay
    tris = Delaunay(P[:, :2]).simplices

    z = np.full((H, W), np.nan)
    for a, b, c in tris:
        p0, p1, p2 = P[a], P[b], P[c]
        x0 = max(int(min(p0[0], p1[0], p2[0])), 0)
        x1 = min(int(max(p0[0], p1[0], p2[0])) + 1, W)
        y0 = max(int(min(p0[1], p1[1], p2[1])), 0)
        y1 = min(int(max(p0[1], p1[1], p2[1])) + 1, H)
        if x1 <= x0 or y1 <= y0:
            continue
        yy, xx = np.mgrid[y0:y1, x0:x1]
        det = ((p1[1] - p2[1]) * (p0[0] - p2[0]) + (p2[0] - p1[0]) * (p0[1] - p2[1]))
        if abs(det) < 1e-9:
            continue
        l0 = ((p1[1] - p2[1]) * (xx - p2[0]) + (p2[0] - p1[0]) * (yy - p2[1])) / det
        l1 = ((p2[1] - p0[1]) * (xx - p2[0]) + (p0[0] - p2[0]) * (yy - p2[1])) / det
        l2 = 1 - l0 - l1
        m = (l0 >= 0) & (l1 >= 0) & (l2 >= 0)
        vals = l0 * p0[2] + l1 * p1[2] + l2 * p2[2]
        bloc = z[y0:y1, x0:x1]
        bloc[m] = vals[m]
    return -z, dip, intors, inclinat   # semnul: mai mare = mai aproape


def _silueta_bruta(img: np.ndarray) -> np.ndarray:
    """Tot ce e om în cadru: păr, faţă şi piele. Fără curăţenia de portret.

    Pe o poză din profil, segmentarea pune nasul şi bărbia în clasa „corp", nu
    în „pielea feţei" -- masca de portret le-ar tăia exact pe alea."""
    res = MODELE_INST.seg.segment(_mp_image(img))
    cat = np.squeeze(res.category_mask.numpy_view())
    m = cv2.morphologyEx(np.isin(cat, (1, 2, 3)).astype(np.uint8),
                         cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m)
    if n > 1:
        m = (lab == 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))).astype(np.uint8)
    return m


def _curata(m: np.ndarray) -> np.ndarray:
    """Închide golurile şi păstrează doar bucata cea mai mare."""
    m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m)
    if n > 1:
        m = (lab == 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))).astype(np.uint8)
    return cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8))


def _silueta(img: np.ndarray, cu_gat: bool = True,
             mm_pe_px: float = 0.3) -> tuple[np.ndarray, np.ndarray]:
    """Silueta de tăiat, plus capul singur.

    Capul e păr şi pielea feţei. Cu gât, se adaugă pielea de corp aşa cum o dă
    segmentarea, fără s-o strunesc: forma care iese -- un gât care se subţiază
    spre bază, cu umerii unde se văd -- e a omului din poză, iar o limită
    impusă de mine o făcea a mea. Pe o poză apropiată iese un bust scurt; pe
    una depărtată, umerii întregi. Aşa şi trebuie.

    Întoarce şi capul singur, fiindcă lăţimea şi înălţimea capului se măsoară
    pe el. Fără asta, „lăţimea capului" devine lăţimea umerilor -- pe poza de
    probă, 278 mm în loc de 137 -- iar verificarea de plauzibilitate respingea
    tocmai pozele bune."""
    res = MODELE_INST.seg.segment(_mp_image(img))
    cat = np.squeeze(res.category_mask.numpy_view())
    doar_cap = _curata(np.isin(cat, (1, 3))).astype(bool)
    if not cu_gat:
        return doar_cap.astype(np.uint8), doar_cap
    return _curata(np.isin(cat, (1, 2, 3))), doar_cap


def _monocular(img: np.ndarray) -> np.ndarray:
    H, W = img.shape[:2]
    x = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2RGB),
                   (INTRARE_ADANC, INTRARE_ADANC)).astype(np.float32) / 255.0
    x = (x - np.array([0.485, 0.456, 0.406])) / np.array([0.229, 0.224, 0.225])
    x = x.transpose(2, 0, 1)[None].astype(np.float32)
    d = MODELE_INST.adanc.run(None, {"pixel_values": x})[0][0]
    return cv2.resize(d, (W, H), interpolation=cv2.INTER_CUBIC).astype(np.float64)


def _verifica(intors: float, inclinat: float, latime_cap_mm: float) -> None:
    """Poza e bună de reconstruit? Spune pe şleau ce anume e greşit.

    Refuzul e mai bun decât un rezultat tăcut şi fals: o poză din trei sferturi
    trece prin toate modelele fără nicio eroare şi scoate un cap de 33 cm.
    Omul n-are de unde şti că nu e vina lui -- deci i se spune."""
    if abs(intors) > UNGHI_MAX:
        raise PozaNepotrivita(
            f"Capul e întors cam {abs(intors):.0f}° într-o parte. "
            "E nevoie de o poză din faţă, privind drept în aparat.")
    if abs(inclinat) > UNGHI_MAX:
        sus = "pe spate" if inclinat > 0 else "în piept"
        raise PozaNepotrivita(
            f"Bărbia e lăsată {sus} cam {abs(inclinat):.0f}°. "
            "E nevoie de o poză din faţă, cu privirea la nivelul aparatului.")
    lo, hi = LATIME_CAP_PLAUZIBILA
    if not lo <= latime_cap_mm <= hi:
        raise PozaNepotrivita(
            f"Din poză iese un cap de {latime_cap_mm:.0f} mm, ceea ce nu e "
            "plauzibil. Încearcă o poză din faţă, cu tot capul în cadru şi "
            "faţa neacoperită.")


def reconstruieste(bgr: np.ndarray, dip_mm: float = DIP_IMPLICIT_MM,
                   cu_gat: bool = True) -> Reconstructie:
    h, w = bgr.shape[:2]
    img = cv2.resize(bgr, (LAT_LUCRU, int(h * LAT_LUCRU / w)))
    H, W = img.shape[:2]

    mp_z, dip_px, intors, inclinat = _plasa_faciala(img)
    cap, doar_cap = _silueta(img, cu_gat, dip_mm / dip_px)
    cap = cap.astype(bool)
    mono = _monocular(img)

    fata = ~np.isnan(mp_z)
    supr = fata & cap
    if supr.sum() < 500:
        raise FaraFata("Faţa şi silueta nu se suprapun destul.")
    a, b = np.polyfit(mono[supr], mp_z[supr], 1)
    baza = a * mono + b

    # Detaliul plasei: ce rămâne după scăderea propriei forme mari.
    k = 81
    mpf = np.where(fata, mp_z, 0.0)
    neted = cv2.GaussianBlur(mpf, (k, k), 0)
    pond = cv2.GaussianBlur(fata.astype(np.float64), (k, k), 0)
    neted = np.divide(neted, pond, out=np.zeros_like(neted), where=pond > 1e-6)
    detaliu = np.where(fata, mp_z - neted, 0.0)

    alfa = cv2.GaussianBlur(fata.astype(np.float64), (61, 61), 0)
    alfa = np.clip((alfa - 0.25) / 0.5, 0, 1)

    # Netezire uşoară: marginea segmentării are zimţi de un pixel. Se aplică
    # separat pe fiecare componentă, ca suma lor să rămână netedă oricât s-ar
    # amplifica detaliul.
    m = cap.astype(np.float64)
    mf = cv2.GaussianBlur(m, (9, 9), 0)
    def _neteste(v):
        vb = cv2.GaussianBlur(np.where(cap, v, 0.0), (9, 9), 0)
        return np.divide(vb, mf, out=np.zeros_like(vb), where=mf > 1e-6)
    baza, detaliu = _neteste(baza), _neteste(detaliu)

    mm_pe_px = dip_mm / dip_px
    z = np.where(cap, baza + DETALIU_IMPLICIT * alfa * detaliu, np.nan)
    xs = np.where(doar_cap.any(axis=0))[0]
    ys = np.where(doar_cap.any(axis=1))[0]
    lo, hi = np.percentile(z[cap], [0.5, 99.8])
    latime_cap_mm = float(np.ptp(xs) * mm_pe_px)
    _verifica(intors, inclinat, latime_cap_mm)

    return Reconstructie(
        baza=baza, detaliu=detaliu, alfa=alfa, cap=cap,
        intors=round(intors, 1), inclinat=round(inclinat, 1),
        mm_pe_px=mm_pe_px, dip_px=dip_px,
        latime_cap_mm=latime_cap_mm,
        inaltime_cap_mm=float(np.ptp(ys) * mm_pe_px),
        relief_mm=float((hi - lo) * mm_pe_px))
