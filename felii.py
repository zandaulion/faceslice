"""Feliere sub orice unghi, cu sărire peste straturi.

Până acum felierea era un prag pe adâncime: straturi paralele cu faţa. Asta e
un caz particular. În general, un strat e zona dintre două plane paralele, iar
planele pot sta oricum -- de aceea relieful se transformă întâi într-un solid,
şi abia apoi se taie.

Solidul: în spatele fiecărui punct de pe suprafaţă e material, până la un spate
plat. Adică exact obiectul care se agaţă pe perete.

Două unghiuri descriu direcţia de tăiere:
  înclinare  0° = plane paralele cu faţa (topografic)
            90° = plane orizontale (felii de sus în jos)
  rotire     90° = plane verticale (felii de la stânga la dreapta)
"""
import numpy as np
import cv2


def solid(z, cap, lat_lucru=360):
    """Relieful, ca grilă de voxeli. Spatele e plat."""
    H, W = z.shape
    s = lat_lucru / W
    zs = cv2.resize(np.nan_to_num(z), (int(W * s), int(H * s)), interpolation=cv2.INTER_AREA)
    cs = cv2.resize(cap.astype(np.uint8), (int(W * s), int(H * s)), interpolation=cv2.INTER_NEAREST) > 0
    zs = np.where(cs, zs * s, 0.0)
    D = int(np.ceil(zs.max())) + 1
    h, w = zs.shape
    W3 = np.arange(D)[None, None, :]
    vox = (W3 <= zs[:, :, None]) & cs[:, :, None]
    return vox, s


def taie(vox, inclinare=0.0, rotire=0.0, pas_px=8.0, sari=1):
    """Taie solidul cu plane perpendiculare pe direcţia dată.

    `sari` > 1 lasă goluri: se păstrează un strat din `sari`, iar între ele
    rămâne aer. Plăcile nu se mai ating, deci teancul nu se mai susţine singur
    -- are nevoie de distanţiere sau de tije.
    """
    a, b = np.radians(inclinare), np.radians(rotire)
    n = np.array([np.sin(b) * np.cos(a), np.sin(a), np.cos(b) * np.cos(a)])
    n /= np.linalg.norm(n)
    # Bază ortonormală în planul de tăiere.
    tmp = np.array([0.0, 0.0, 1.0]) if abs(n[1]) > 0.9 else np.array([0.0, 1.0, 0.0])
    u = np.cross(tmp, n); u /= np.linalg.norm(u)
    v = np.cross(n, u)

    idx = np.argwhere(vox).astype(np.float32)     # (y, x, w)
    P = np.stack([idx[:, 1], idx[:, 0], idx[:, 2]], 1)   # (x, y, w)
    h = P @ n
    U, V = P @ u, P @ v

    niv = np.arange(h.min(), h.max(), pas_px)
    placi = []
    for k in range(0, len(niv), sari):
        lo = niv[k]
        sel = (h >= lo) & (h < lo + pas_px)
        if sel.sum() < 50:
            continue
        placi.append((lo, U[sel], V[sel]))
    return placi, (u, v, n), niv


def rasterizeaza(uu, vv, u0, v0, marja=6):
    """Norul de puncte al unei plăci, ca imagine binară."""
    ui = np.round(uu - u0).astype(int) + marja
    vi = np.round(vv - v0).astype(int) + marja
    img = np.zeros((vi.max() + marja + 1, ui.max() + marja + 1), np.uint8)
    img[vi, ui] = 255
    img = cv2.morphologyEx(img, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    return img


if __name__ == '__main__':
    z = np.load('final.npy')
    cap = ~np.isnan(z)
    MM = 150.0 / np.ptp(np.where(cap.any(axis=0))[0])
    vox, s = solid(z, cap)
    print(f'solid: {vox.shape}  ({vox.sum()/1e6:.1f}M voxeli plini)')
    MM_L = MM / s   # mm pe voxel la rezoluţia de lucru
    pas = 3.0 / MM_L
    print(f'{MM_L:.2f} mm/voxel, pas de {pas:.1f} voxeli = 3 mm\n')

    for incl, rot, sari, nume in [
            (0, 0, 1, 'topografic (ca până acum)'),
            (0, 0, 2, 'topografic, strat-gol'),
            (90, 0, 1, 'felii orizontale'),
            (0, 90, 1, 'felii verticale'),
            (30, 0, 1, 'înclinat 30°')]:
        placi, _, niv = taie(vox, incl, rot, pas, sari)
        arii = []
        for _, uu, vv in placi:
            img = rasterizeaza(uu, vv, uu.min(), vv.min())
            arii.append((img > 0).sum() * MM_L ** 2 / 100)
        print(f'{nume:28} {len(placi):3d} plăci   '
              f'arie {min(arii):5.0f}–{max(arii):5.0f} cm²   total {sum(arii)/100:5.2f} dm²')
