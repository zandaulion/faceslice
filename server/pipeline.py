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


@dataclass
class Reconstructie:
    z: np.ndarray            # adâncime, mai mare = mai aproape de privitor
    cap: np.ndarray          # masca siluetei
    mm_pe_px: float
    dip_px: float
    latime_cap_mm: float
    inaltime_cap_mm: float
    relief_mm: float

    def rezumat(self) -> dict:
        d = asdict(self)
        d.pop("z"); d.pop("cap")
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


class FaraFata(Exception):
    """Fotografia nu conţine o faţă utilizabilă."""


def _mp_image(bgr: np.ndarray) -> mp.Image:
    return mp.Image(image_format=mp.ImageFormat.SRGB,
                    data=cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))


def _plasa_faciala(img: np.ndarray) -> tuple[np.ndarray, float]:
    """Adâncimea feţei din plasă, plus distanţa dintre pupile în pixeli."""
    H, W = img.shape[:2]
    res = MODELE_INST.plasa.detect(_mp_image(img))
    if not res.face_landmarks:
        raise FaraFata("Nu am găsit o faţă în fotografie.")
    lm = res.face_landmarks[0]
    P = np.array([[p.x * W, p.y * H, p.z * W] for p in lm], np.float64)

    # 468 şi 473 sunt centrele irisurilor în plasa cu puncte rafinate.
    dip = float(np.hypot(*(P[468, :2] - P[473, :2]))) if len(P) > 473 else \
        float(np.hypot(*(P[33, :2] - P[263, :2])))

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
    return -z, dip           # semnul: mai mare = mai aproape


def _silueta(img: np.ndarray, cu_gat: bool = False) -> np.ndarray:
    """Capul: păr plus pielea feţei. Gâtul se taie -- un portret se termină la
    maxilar, altfel primele straturi ar fi numai umeri."""
    res = MODELE_INST.seg.segment(_mp_image(img))
    cat = np.squeeze(res.category_mask.numpy_view())
    clase = [1, 3] + ([2] if cu_gat else [])
    cap = np.isin(cat, clase).astype(np.uint8)
    cap = cv2.morphologyEx(cap, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(cap)
    if n > 1:
        cap = (lab == 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))).astype(np.uint8)
    return cv2.morphologyEx(cap, cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8))


def _monocular(img: np.ndarray) -> np.ndarray:
    H, W = img.shape[:2]
    x = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2RGB),
                   (INTRARE_ADANC, INTRARE_ADANC)).astype(np.float32) / 255.0
    x = (x - np.array([0.485, 0.456, 0.406])) / np.array([0.229, 0.224, 0.225])
    x = x.transpose(2, 0, 1)[None].astype(np.float32)
    d = MODELE_INST.adanc.run(None, {"pixel_values": x})[0][0]
    return cv2.resize(d, (W, H), interpolation=cv2.INTER_CUBIC).astype(np.float64)


def reconstruieste(bgr: np.ndarray, dip_mm: float = DIP_IMPLICIT_MM,
                   cu_gat: bool = False) -> Reconstructie:
    h, w = bgr.shape[:2]
    img = cv2.resize(bgr, (LAT_LUCRU, int(h * LAT_LUCRU / w)))
    H, W = img.shape[:2]

    mp_z, dip_px = _plasa_faciala(img)
    cap = _silueta(img, cu_gat).astype(bool)
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

    z = baza + alfa * detaliu
    zf = np.where(np.isnan(z), 0, z)
    m = cap.astype(np.float64)
    zf = cv2.GaussianBlur(zf, (9, 9), 0)
    mf = cv2.GaussianBlur(m, (9, 9), 0)
    z = np.where(cap, np.divide(zf, mf, out=np.zeros_like(zf), where=mf > 1e-6), np.nan)

    mm_pe_px = dip_mm / dip_px
    xs = np.where(cap.any(axis=0))[0]
    ys = np.where(cap.any(axis=1))[0]
    lo, hi = np.percentile(z[cap], [0.5, 99.8])
    return Reconstructie(
        z=z, cap=cap, mm_pe_px=mm_pe_px, dip_px=dip_px,
        latime_cap_mm=float(np.ptp(xs) * mm_pe_px),
        inaltime_cap_mm=float(np.ptp(ys) * mm_pe_px),
        relief_mm=float((hi - lo) * mm_pe_px))
