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

# Cât de asimetrică trebuie să fie silueta ca să fie un profil. O faţă din faţă
# are ambele laturi la fel de netede; una din profil are ceafa netedă şi
# cealaltă latură cu nas, buze şi bărbie. Raportul dintre cele două curburi
# desparte cele două cazuri fără să aibă nevoie de puncte faciale -- care
# oricum nu se detectează pe un profil adevărat.
ASIMETRIE_MIN = 1.6

# Cât trebuie să iasă nasul din adâncimea capului ca poza să fie un profil.
# Anatomic, vreo 22 mm dintr-un cap de 195 -- adică 0,11. Măsurat pe poze: un
# profil adevărat dă 0,14, iar o poză din faţă, una din trei sferturi şi una
# cu creştetul dau 0,02, 0,07 şi 0,007. Pragul separă cazurile cu marjă.
#
# Asimetria singură nu ajunge: creştetul fotografiat de sus a ieşit 9,1, cel
# mai asimetric din tot lotul, fiindcă o latură era tăiată de cadru.
NAS_MIN_RELATIV = 0.09

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

    def rezumat(self) -> dict:
        return {k: round(v, 3) for k, v in self.__dict__.items()}


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


def _fata_si_asimetrie(masca: np.ndarray) -> tuple[np.ndarray, float]:
    """Latura cu relief e faţa; ceafa e netedă.

    Ambele curburi se împart la aceeaşi adâncime a capului. Împărţită fiecare
    la propria cursă, o ceafă aproape dreaptă ar ieşi infinit de zbuciumată --
    exact latura greşită."""
    laturi = {d: _margine(masca, d) for d in (True, False)}
    adanc = max(np.ptp(c) for c in laturi.values())
    if adanc < 1e-6:
        raise ProfilNepotrivit("Silueta din a doua poză e plată.")
    scor = {d: float(np.abs(np.diff(c, 2)).sum() / adanc) for d, c in laturi.items()}
    d = max(scor, key=scor.get)
    slab = min(scor.values())
    return laturi[d], (scor[d] / slab if slab > 1e-9 else np.inf)


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
    """Profilul adevărat al feţei: contur normalizat plus înălţimea capului.

    Conturul se întoarce în pixeli ai imaginii de lucru; scara în milimetri
    vine de la poza frontală, care are distanţa dintre pupile."""
    h, w = bgr.shape[:2]
    img = cv2.resize(bgr, (pipeline.LAT_LUCRU, int(h * pipeline.LAT_LUCRU / w)))
    # Silueta completă, nu cea a portretului: pe o poză din profil, segmentarea
    # pune tocmai nasul şi bărbia în clasa „corp", iar masca de portret le-ar
    # tăia -- exact părţile pentru care se face poza.
    cap = pipeline._silueta_bruta(img).astype(bool)
    if cap.sum() < 5000:
        raise ProfilNepotrivit("Nu am găsit un cap în a doua fotografie.")

    contur, _ = _fata_si_asimetrie(cap)
    k = _varful_nasului(contur)
    relativ = _proeminenta(contur, k) / max(float(np.ptp(contur)), 1e-9)
    if relativ < NAS_MIN_RELATIV:
        raise ProfilNepotrivit(
            "A doua poză nu pare făcută din profil -- nu se vede linia nasului. "
            "E nevoie de o poză din lateral, cu capul întors complet şi faţa "
            "descoperită.")
    return _normalizat(contur)


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
    return Calibrare(factor=factor, potrivire=potrivire,
                     nas_masurat_mm=pm * mm, nas_dedus_mm=pd * mm)


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
