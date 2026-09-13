"""Arată unde cad planele de tăiere, peste profilul capului.

Un unghi de feliere e greu de judecat dintr-un număr. Peste profilul văzut din
lateral se vede imediat ce taie şi ce lasă întreg.
"""
import numpy as np
import cv2
from felii import solid, taie, rasterizeaza

z = np.load('final.npy')
cap = ~np.isnan(z)
MM = 150.0 / np.ptp(np.where(cap.any(axis=0))[0])
vox, s = solid(z, cap)
MM_L = MM / s
pas = 3.0 / MM_L
h, w, D = vox.shape

# Profilul: secţiune verticală prin mijlocul feţei, văzută din stânga.
xs = np.where(vox.any(axis=(0, 2)))[0]
xc = int(np.median(xs))
prof = vox[:, xc, :]                      # (y, w)
ys_ = np.where(vox.any(axis=(1, 2)))[0]
yc = int(np.median(ys_))

CFG = [(0, 0, 1, 'topografic'), (0, 0, 2, 'topografic, strat-gol'),
       (90, 0, 1, 'orizontal'), (0, 90, 1, 'vertical'), (30, 0, 1, 'înclinat 30°')]

SC = 2
PH, PW = h * SC, D * SC
panouri = []
for incl, rot, sari, nume in CFG:
    im = np.full((PH, PW + 240, 3), 250, np.uint8)
    # Profilul, cu nasul spre dreapta.
    p = cv2.resize(prof.astype(np.uint8) * 255, (PW, PH), interpolation=cv2.INTER_NEAREST)
    im[:, :PW][p > 0] = (215, 205, 195)
    cnts, _ = cv2.findContours((p > 0).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(im[:, :PW], cnts, -1, (120, 105, 90), 2)

    a, b = np.radians(incl), np.radians(rot)
    n = np.array([np.sin(b) * np.cos(a), np.sin(a), np.cos(b) * np.cos(a)])
    # Vederea se alege după direcţia de tăiere: planele verticale nu apar ca
    # linii într-un profil lateral, fiindcă sunt perpendiculare pe el. Prima
    # versiune le desena oricum şi ieşea o împărţire la zero.
    lateral = abs(n[0]) <= abs(n[1]) or abs(n[2]) > abs(n[0])
    if lateral:
        na, nb, felie = n[1], n[2], prof
        et = 'profil lateral'
    else:
        na, nb, felie = n[0], n[2], vox[yc]
        et = 'vedere de sus'

    p = cv2.resize(felie.astype(np.uint8) * 255, (PW, PH), interpolation=cv2.INTER_NEAREST)
    im[:, :PW] = 250
    im[:, :PW][p > 0] = (215, 205, 195)
    cnts, _ = cv2.findContours((p > 0).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(im[:, :PW], cnts, -1, (120, 105, 90), 2)

    placi, _, niv = taie(vox, incl, rot, pas, sari)
    nn = np.hypot(na, nb) or 1.0
    for k in range(0, len(niv), sari):
        d = niv[k]
        # Punct pe dreapta + direcţie, fără nicio împărţire la o componentă.
        ax, by = na * d / nn**2, nb * d / nn**2
        dx, dy = -nb / nn, na / nn
        p1 = (int((by - dy * 3000) * SC), int((ax - dx * 3000) * SC))
        p2 = (int((by + dy * 3000) * SC), int((ax + dx * 3000) * SC))
        cv2.line(im[:, :PW], p1, p2, (70, 130, 220), 1, cv2.LINE_AA)

    cv2.putText(im, nume, (PW + 12, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (40, 40, 40), 2)
    cv2.putText(im, f'{len(placi)} placi', (PW + 12, 66), cv2.FONT_HERSHEY_SIMPLEX,
                0.55, (110, 110, 110), 1)
    cv2.putText(im, et, (PW + 12, 94), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (110, 110, 110), 1)
    if sari > 1:
        cv2.putText(im, 'cu goluri', (PW + 12, 122), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, (70, 130, 220), 1)
    panouri.append(im)

cv2.imwrite('out_unghiuri.png', np.hstack(panouri))
print('schemă scrisă:', np.hstack(panouri).shape)
