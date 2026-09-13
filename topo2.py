"""Felierea capului întreg, şi verdictul de cuibărire."""
import numpy as np
import cv2

z = np.load('fuzionat.npy')
cap = ~np.isnan(z)
zv = z[cap]

MM_PE_PX = 150.0 / np.ptp(np.where(cap.any(axis=0))[0])
GROSIME = 3.0
lo, hi = np.percentile(zv, [0.5, 99.8])
print(f'relief brut: {(hi - lo) * MM_PE_PX:.0f} mm')

# Comprimare de basorelief: un cap privit din faţă are ~110 mm de la nas la
# planul urechilor, dar un portret pe perete nu trebuie să iasă atât. Sculptorii
# comprimă adâncimea şi păstrează relieful; aici o facem cu un exponent, ca
# treptele din zona feţei să nu se piardă când se strânge totul.
TINTA_MM = 60.0
t = np.clip((z - lo) / (hi - lo), 0, 1)
t = t ** 0.75
znou = t * (TINTA_MM / MM_PE_PX)
znou[~cap] = np.nan
pas = GROSIME / MM_PE_PX
niveluri = np.arange(0, TINTA_MM / MM_PE_PX, pas)
print(f'comprimat la {TINTA_MM:.0f} mm  →  {len(niveluri)} straturi de {GROSIME} mm\n')

H, W = z.shape
zf = np.where(cap, znou, -1e9)
umplut = np.full((H, W, 3), 248, np.uint8)
linii = np.full((H, W, 3), 255, np.uint8)

prev = None
nec = 0
bucati = []
for i, niv in enumerate(niveluri):
    m = (zf >= niv).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = [c for c in cnts if cv2.contourArea(c) > 300]
    bucati.append(len(cnts))
    if prev is not None:
        afara = int((m.astype(bool) & ~prev.astype(bool)).sum())
        if afara >= 30:
            nec += 1
    prev = m
    f = i / max(len(niveluri) - 1, 1)
    cv2.drawContours(umplut, cnts, -1,
                     (int(195 - 75 * f), int(208 - 45 * f), int(172 + 72 * f)), -1)
    cv2.drawContours(umplut, cnts, -1, (105, 90, 75), 1)
    cv2.drawContours(linii, cnts, -1, (85, 70, 55), 1)

print(f'straturi necuibărite: {nec} din {len(niveluri) - 1}')
print(f'bucăţi pe strat: {bucati}')

ys, xs = np.where(cap)
m_ = 30
sl = (slice(max(ys.min() - m_, 0), min(ys.max() + m_, H)),
      slice(max(xs.min() - m_, 0), min(xs.max() + m_, W)))
cv2.imwrite('out_topo_cap.png', np.hstack([umplut[sl], linii[sl]]))
np.save('final.npy', znou)
print('previzualizare scrisă')
