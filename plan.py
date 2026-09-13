"""Planul de tăiere: contopeşte aşchiile, numără plăcile.

La marginea siluetei suprafaţa capului e aproape paralelă cu privirea, deci
nivelurile se înghesuie: primele şapte inele au sub un milimetru lăţime. Nu se
pot tăia şi nu se pot lipi -- şi nici n-ar trebui. Unde conturul nu se schimbă
între niveluri, nu e nevoie de plăci diferite: e nevoie de aceeaşi placă,
repetată. Aşa dispar aşchiile fără să se piardă nimic din formă.
"""
import numpy as np
import cv2

MIN_INEL_MM = 2.0
GROSIME = 3.0

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

# Contopim de la exterior spre interior: cât timp inelul dintre două niveluri
# e mai îngust decât pragul, e aceeaşi placă tăiată de mai multe ori.
placi = []
i = 0
while i < len(masti):
    j = i + 1
    while j < len(masti):
        inel = masti[i].astype(bool) & ~masti[j].astype(bool)
        if inel.sum() == 0:
            j += 1
            continue
        d = cv2.distanceTransform(inel.astype(np.uint8), cv2.DIST_L2, 5)
        if 2 * d.max() * MM >= MIN_INEL_MM:
            break
        j += 1
    placi.append((masti[i], j - i))
    i = j

print(f'{len(niv)} niveluri  →  {len(placi)} contururi distincte, '
      f'{sum(r for _, r in placi)} plăci în total\n')
print('placă  repetări  arie(cm²)  bucăţi  grosime(mm)')
total_cm2 = 0
for k, (m, rep) in enumerate(placi):
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = [c for c in cnts if cv2.contourArea(c) > 300]
    arie = m.sum() * MM ** 2 / 100
    total_cm2 += arie * rep
    print(f'  {k:2d}      ×{rep:<2d}    {arie:8.1f}    {len(cnts):3d}      {rep * GROSIME:5.1f}')

print(f'\ntablă necesară: {total_cm2 / 100:.2f} dm²  '
      f'({total_cm2 * GROSIME / 10:.0f} cm³)')
for nume, dens in [('oţel', 7.85), ('alamă', 8.5), ('aluminiu', 2.7)]:
    print(f'   {nume:9} {total_cm2 * GROSIME / 10 * dens / 1000:5.2f} kg')

H, W = z.shape
vis = np.full((H, W, 3), 248, np.uint8)
for k, (m, rep) in enumerate(placi):
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = [c for c in cnts if cv2.contourArea(c) > 300]
    f = k / max(len(placi) - 1, 1)
    cv2.drawContours(vis, cnts, -1,
                     (int(198 - 78 * f), int(210 - 48 * f), int(170 + 74 * f)), -1)
    cv2.drawContours(vis, cnts, -1, (100, 85, 70), 2)
ys, xs = np.where(cap)
m_ = 30
cv2.imwrite('out_plan.png', vis[max(ys.min()-m_,0):ys.max()+m_, max(xs.min()-m_,0):xs.max()+m_])
print('plan scris')
