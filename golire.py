"""Fiecare placă e un inel, nu un disc.

Dintr-o placă se vede doar banda dintre conturul ei şi conturul celei de
deasupra -- restul e acoperit. Materialul din mijloc nu se vede niciodată, nu
susţine nimic şi se plăteşte la kilogram. Îl scoatem, lăsând o margine de
lipire pe care se sprijină placa următoare.

Nu e o aproximare: geometria vizibilă rămâne identică.
"""
import numpy as np
import cv2

MARGINE_MM = 12.0
GROSIME = 3.0
MIN_INEL_MM = 2.0

z = np.load('final.npy')
cap = ~np.isnan(z)
MM = 150.0 / np.ptp(np.where(cap.any(axis=0))[0])
pas = GROSIME / MM
niv = np.arange(0, np.nanmax(z), pas)
zf = np.where(cap, z, -1e9)

masti = []
for n in niv:
    m = (zf >= n).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    masti.append(m)

placi = []
i = 0
while i < len(masti):
    j = i + 1
    while j < len(masti):
        inel = masti[i].astype(bool) & ~masti[j].astype(bool)
        if inel.sum():
            d = cv2.distanceTransform(inel.astype(np.uint8), cv2.DIST_L2, 5)
            if 2 * d.max() * MM >= MIN_INEL_MM:
                break
        j += 1
    placi.append((masti[i], j - i))
    i = j

k_er = int(MARGINE_MM / MM) | 1
ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_er, k_er))

plin = gol = 0
print('placă  ×  arie plină  arie inel  economie')
for k, (m, rep) in enumerate(placi):
    if k + 1 < len(placi):
        interior = cv2.erode(placi[k + 1][0], ker)
        inel = (m.astype(bool) & ~interior.astype(bool)).astype(np.uint8)
    else:
        inel = m  # vârful rămâne plin, e mic oricum
    a_p = m.sum() * MM ** 2 / 100
    a_i = inel.sum() * MM ** 2 / 100
    plin += a_p * rep
    gol += a_i * rep
    print(f'  {k:2d}  ×{rep:<2d}  {a_p:8.1f}  {a_i:8.1f}   {100*(1-a_i/a_p):4.0f}%')

print(f'\nplin : {plin/100:5.2f} dm²   inele: {gol/100:5.2f} dm²   '
      f'economie {100*(1-gol/plin):.0f}%')
for nume, dens in [('oţel', 7.85), ('alamă', 8.5), ('aluminiu', 2.7)]:
    print(f'   {nume:9} {plin*GROSIME/10*dens/1000:5.2f} kg  →  '
          f'{gol*GROSIME/10*dens/1000:5.2f} kg')
