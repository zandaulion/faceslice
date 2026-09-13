"""Poza din profil, folosită ca riglă pentru adâncime.

Dintr-o poză din faţă, adâncimea e dedusă; iar ce-o deduce nu ştie cu ce
obiectiv s-a fotografiat. La 26 mm ţinut aproape, vârful nasului e sensibil mai
aproape de senzor decât urechile, deci iese mărit -- „nasul de selfie". La 85 mm
de la trei metri, nu. Cele două poze sunt identice ca unghiuri şi diferite ca
proporţii, şi nimic dintr-o singură imagine nu le separă.

Din profil, acelaşi nas nu mai e dedus: e marginea siluetei, o lungime măsurată
în planul imaginii. De acolo iese un factor propriu omului şi aparatului cu care
a fost pozat, care înlocuieşte media pusă pe toată lumea.

Prima încercare potrivea cuantilele celor două profile. N-a mers, şi se vede de
ce: cuantilele redistribuie valori fără să le alinieze spaţial, deci potriveau
nasul cu fruntea dacă asta egaliza histogramele. Aici alinierea se face pe
înălţimea capului -- fruntea cu fruntea, nasul cu nasul -- iar potrivirea e o
dreaptă robustă, nu o redistribuire.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

import pipeline

# Fereastra pe care se potrivesc cele două profile, în unităţi de „creştet până
# la vârful nasului". Sub 0,45 e păr, a cărui margine ţine de coafură şi de vânt;
# peste 1,25 e bărbia, unde silueta frontală e tăiată la maxilar şi cea din
# profil nu. Între ele stau sprânceana, şaua nasului, vârful şi buzele.
FEREASTRA = (0.45, 1.25)

# Cât de decentrată trebuie să fie pielea feţei faţă de mijlocul siluetei ca
# poza să fie din lateral. Măsurat: un profil adevărat dă 0,11, o poză din trei
# sferturi 0,07, iar cele frontale 0,01. Pragul e jos dinadins -- nu mai refuză
# nimic, doar alege latura pe care e faţa.
DECENTRARE_MIN = 0.03

# Sub atât, cele două profile nu descriu acelaşi cap şi calibrarea nu se
# aplică. Nu e o respingere: lucrarea merge mai departe cu valoarea medie, şi
# se spune de ce.
POTRIVIRE_MIN = 0.30

# Factorul rămâne în limite omeneşti. Peste ele, mai degrabă s-a greşit poza
# decât are omul un nas de trei ori cât se credea.
FACTOR_LIMITE = (0.4, 4.0)


class ProfilNepotrivit(Exception):
    """Poza a doua nu e un profil din care se poate măsura."""


@dataclass
class Calibrare:
    factor: float            # cu cât se înmulţeşte detaliul facial
    potrivire: float         # cât de bine se suprapun formele, 0..1
    nas_masurat_mm: float    # proeminenţa nasului din profil
    nas_dedus_mm: float      # cât ieşea din poza frontală, nepotenţat
    folosita: bool = True    # dacă a doua poză a putut fi folosită
    motiv: str = ""          # şi, dacă nu, de ce

    def rezumat(self) -> dict:
        return {k: (round(v, 3) if isinstance(v, (int, float))
                    and not isinstance(v, bool) else v)
                for k, v in self.__dict__.items()}


def _margine(masca: np.ndarray, dreapta: bool, n: int = 240) -> np.ndarray:
    """Conturul unei laturi a siluetei, de la creştet la bărbie, în pixeli.

    Semnul e ales aşa încât mai mare să însemne mereu mai în faţă, indiferent
    încotro priveşte omul."""
    ys, xs = np.where(masca)
    u = np.unique(ys)
    m = np.array([(xs[ys == y].max() if dreapta else -xs[ys == y].min())
                  for y in u], np.float64)
    m = cv2.GaussianBlur(m.reshape(-1, 1), (1, 11), 0).ravel()
    return np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(m)), m)


def _latura_fetei(piele: np.ndarray, silueta: np.ndarray) -> bool | None:
    """Încotro priveşte omul, după unde stă pielea feţei.

    Prima variantă alegea latura după cât de zbuciumat e conturul, presupunând
    că ceafa e netedă şi faţa nu. Pe păr creţ sau lung presupunerea cade --
    părul e cel mai zbuciumat lucru din poză, şi ajungeam să măsurăm ceafa.
    Pielea feţei nu are ambiguitatea asta: e de o singură parte, oricâtă
    coafură ar fi în jur.

    Măsurat: profil 0,11 decentrare, trei sferturi 0,07, frontal 0,01."""
    if piele.sum() < 200 or silueta.sum() < 200:
        return None
    cx_p = float(np.where(piele)[1].mean())
    cx_t = float(np.where(silueta)[1].mean())
    lat = float(np.ptp(np.where(silueta.any(axis=0))[0])) or 1.0
    dev = (cx_p - cx_t) / lat
    if abs(dev) < DECENTRARE_MIN:
        return None
    return dev > 0


def _varful_nasului(c: np.ndarray) -> int:
    """Rândul pe care faţa iese cel mai în afară, căutat doar în treimea de sus.

    Mai jos stau bărbia şi umerii, iar pe o poză din profil umărul poate ieşi
    mai în faţă decât nasul fără ca asta să însemne ceva."""
    hi = int(0.62 * len(c))
    return int(np.argmax(c[:hi]))


def _proeminenta(c: np.ndarray, k: int) -> float:
    """Cât iese vârful peste obrazul din jurul lui, în unităţile lui c."""
    n = max(len(c) // 8, 8)
    jur = np.r_[c[max(0, k - n):max(0, k - n // 3)], c[k + n // 3:k + n]]
    return float(c[k] - np.median(jur)) if len(jur) else 0.0


def _normalizat(contur: np.ndarray, n: int = 240) -> tuple[np.ndarray, float]:
    """Conturul adus la o scară proprie: distanţa creştet-vârful nasului.

    Asta scoate din ecuaţie faptul că cele două poze au fiecare scara ei. E o
    lungime reală a omului, la fel de umflată de coafură în amândouă, deci se
    simplifică la împărţire -- şi nu are nevoie nici de bărbie, nici de gât,
    care pe un profil nu se pot separa de umăr."""
    k = _varful_nasului(contur)
    if k < 5:
        raise ProfilNepotrivit(
            "Nu găsesc vârful nasului în a doua poză. E nevoie de o poză din "
            "lateral, cu tot capul în cadru.")
    L = float(k)                       # creştet -> vârful nasului, în rânduri
    pana = min(int(1.45 * L), len(contur))
    c = np.interp(np.linspace(0, pana / L, n), np.arange(pana) / L, contur[:pana])
    return c / L, L


def masoara(bgr: np.ndarray) -> tuple[np.ndarray, float]:
    """Profilul adevărat al feţei: conturul normalizat al laturii cu faţa.

    Conturul se întoarce în pixeli ai imaginii de lucru; scara nu contează,
    fiindcă `_normalizat` împarte la o lungime a omului."""
    h, w = bgr.shape[:2]
    img = cv2.resize(bgr, (pipeline.LAT_LUCRU, int(h * pipeline.LAT_LUCRU / w)))
    res = pipeline.MODELE_INST.seg.segment(pipeline._mp_image(img))
    cat = np.squeeze(res.category_mask.numpy_view())

    # Silueta completă, nu cea a portretului: pe o poză din profil, segmentarea
    # pune tocmai nasul şi bărbia în clasa „corp", iar masca de portret le-ar
    # tăia -- exact părţile pentru care se face poza.
    cap = pipeline._curata(np.isin(cat, (1, 2, 3))).astype(bool)
    if cap.sum() < 5000:
        raise ProfilNepotrivit("Nu am găsit un cap în a doua fotografie.")

    dreapta = _latura_fetei(cat == 3, cap)
    if dreapta is None:
        raise ProfilNepotrivit(
            "În a doua poză faţa se vede din faţă, nu din lateral. E nevoie de "
            "o poză cu capul întors complet într-o parte.")
    return _normalizat(_margine(cap, dreapta))


def calibreaza(rec: "pipeline.Reconstructie", bgr_profil: np.ndarray) -> Calibrare:
    """Câte milimetri de nas sunt adevăraţi, faţă de câţi deduce poza frontală.

    Potrivirea e o dreaptă între cele două profile, pe fereastra unde amândouă
    înseamnă acelaşi lucru. Panta ei e factorul: de câte ori e relieful real mai
    adânc decât cel dedus. Intercepţia absoarbe faptul că cele două îşi măsoară
    adâncimea de la zerouri diferite."""
    masurat, _ = masoara(bgr_profil)
    dedus, L_frontal = _normalizat(_midline(rec))

    # Amândouă sunt acum în aceeaşi unitate fără nume -- „cât din distanţa
    # creştet-nas" -- deci se compară direct, oricât de diferite ar fi
    # aparatele care le-au produs. Asta e tot rostul normalizării: ea, nu o
    # scară comună în milimetri, care ar fi cerut bărbia, iar bărbia pe un
    # profil nu se poate despărţi de gât.
    pm = _proeminenta(masurat, _varful_nasului(masurat))
    pd = _proeminenta(dedus, _varful_nasului(dedus))
    if pd < 1e-6:
        raise ProfilNepotrivit("Poza din faţă nu dă niciun relief de calibrat.")
    factor = float(np.clip(pm / pd, *FACTOR_LIMITE))

    # Potrivirea se raportează, dar nu se foloseşte la factor. Formele chiar
    # diferă: profilul real are fruntea ieşită şi o şa la rădăcina nasului, iar
    # reconstrucţia le rată pe amândouă. O dreaptă trasă peste toată fereastra
    # ar fi trasă tocmai de nepotrivirea aia -- pe pozele de probă dădea 1,33
    # în loc de 1,91. Nasul e locul unde cele două chiar măsoară acelaşi lucru.
    lo, hi = (int(f / 1.45 * len(dedus)) for f in FEREASTRA)
    _, potrivire = _panta_robusta(dedus[lo:hi], masurat[lo:hi])

    mm = L_frontal * rec.mm_pe_px
    c = Calibrare(factor=factor, potrivire=potrivire,
                  nas_masurat_mm=pm * mm, nas_dedus_mm=pd * mm)

    # Dacă cele două profile nu descriu acelaşi cap, factorul e o cifră fără
    # acoperire. Nu se aplică, dar nici nu se opreşte lucrarea: poza frontală
    # ajunge, iar omul află de ce n-a ajutat a doua.
    if potrivire < POTRIVIRE_MIN:
        c.folosita = False
        c.motiv = ("Cele două poze nu se suprapun destul de bine ca să pot "
                   "măsura adâncimea. Verifică să fie acelaşi om, acelaşi "
                   "aparat şi capul întors complet în a doua.")
    elif factor in FACTOR_LIMITE:
        c.folosita = False
        c.motiv = ("Din a doua poză iese o adâncime în afara limitelor "
                   "omeneşti, deci n-am folosit-o.")
    return c


def _midline(rec: "pipeline.Reconstructie") -> np.ndarray:
    """Profilul dedus din poza frontală: pe fiecare rând, punctul cel mai în faţă.

    Nu coloana din mijloc, ci maximul rândului -- capul poate fi uşor rotit, iar
    creasta nasului nu cade neapărat pe mijlocul imaginii."""
    z = np.where(rec.cap, rec.combina(1.0), np.nan)
    ys = np.where(rec.cap.any(axis=1))[0]
    m = np.nanmax(z[ys.min():ys.max() + 1], axis=1)
    m = cv2.GaussianBlur(m.reshape(-1, 1), (1, 11), 0).ravel()
    return m


def _panta_robusta(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Panta dreptei y ≈ a·x + b, refăcută fără punctele care ies din rând."""
    bun = np.ones(len(x), bool)
    a = 1.0
    for _ in range(3):
        a, b = np.polyfit(x[bun], y[bun], 1)
        rest = y - (a * x + b)
        prag = 2.5 * (np.median(np.abs(rest - np.median(rest))) * 1.4826 + 1e-9)
        nou = np.abs(rest - np.median(rest)) < prag
        if nou.sum() < 0.5 * len(x) or (nou == bun).all():
            break
        bun = nou
    xc, yc = x[bun] - x[bun].mean(), y[bun] - y[bun].mean()
    num = float((xc * yc).sum())
    den = float(np.sqrt((xc ** 2).sum() * (yc ** 2).sum()))
    return float(a), (num / den if den > 1e-9 else 0.0)
