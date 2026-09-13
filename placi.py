"""Cum arată plăcile propriu-zise, pentru două moduri de feliere."""
import numpy as np
import cv2
from felii import solid, taie, rasterizeaza

z = np.load('final.npy')
cap = ~np.isnan(z)
MM = 150.0 / np.ptp(np.where(cap.any(axis=0))[0])
vox, s = solid(z, cap)
MM_L = MM / s
pas = 3.0 / MM_L

def foaie(incl, rot, sari, nume, n_arata=10):
    placi, _, _ = taie(vox, incl, rot, pas, sari)
    sel = np.linspace(0, len(placi) - 1, min(n_arata, len(placi))).astype(int)
    imgs = []
    for i in sel:
        _, uu, vv = placi[i]
        im = rasterizeaza(uu, vv, uu.min(), vv.min())
        cn, _ = cv2.findContours(im, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cn = [c for c in cn if cv2.contourArea(c) > 20]
        col = np.full((im.shape[0], im.shape[1], 3), 250, np.uint8)
        cv2.drawContours(col, cn, -1, (210, 200, 188), -1)
        cv2.drawContours(col, cn, -1, (95, 80, 65), 2)
        imgs.append((col, i))
    HH = max(i.shape[0] for i, _ in imgs) + 46
    WW = sum(i.shape[1] + 16 for i, _ in imgs) + 16
    foaie = np.full((HH, WW, 3), 252, np.uint8)
    x = 16
    for im, i in imgs:
        foaie[38:38 + im.shape[0], x:x + im.shape[1]] = im
        cv2.putText(foaie, f'{i + 1}', (x + 4, 26), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, (120, 120, 120), 1)
        x += im.shape[1] + 16
    cv2.putText(foaie, nume, (16, HH - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (40, 40, 40), 2)
    return foaie

a = foaie(90, 0, 1, 'felii orizontale — 10 din 76 placi')
b = foaie(0, 0, 2, 'topografic cu goluri — 10 placi')
W = max(a.shape[1], b.shape[1])
a = cv2.copyMakeBorder(a, 0, 0, 0, W - a.shape[1], cv2.BORDER_CONSTANT, value=(252, 252, 252))
b = cv2.copyMakeBorder(b, 0, 0, 0, W - b.shape[1], cv2.BORDER_CONSTANT, value=(252, 252, 252))
cv2.imwrite('out_placi.png', np.vstack([a, b]))
print('plăci desenate')
