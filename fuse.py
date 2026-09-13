"""Combină cele două surse de adâncime după ce ştie fiecare mai bine.

Adâncimea monoculară dă forma mare a capului -- craniu, păr, urechi -- dar
aplatizează faţa: nasul aproape nu se vede. Plasa MediaPipe dă exact invers:
relief facial puternic, dar se opreşte la mijlocul frunţii.

Deci: forma mare de la monocular, detaliul de la plasă. Detaliul se ia ca
diferenţă faţă de propria variantă netezită -- aşa se împrumută doar relieful
nasului şi al orbitelor, nu şi eventuala eroare de formă generală a plasei.
"""
import numpy as np
import cv2

mono = np.load('mono.npy').astype(np.float64)
mp_z = np.load('depth.npy')
cap = np.load('cap.npy').astype(bool)
fata = ~np.isnan(mp_z)
H, W = mono.shape

# Monocularul e de tip disparitate: mare = aproape. La fel am orientat şi mp_z.
supr = fata & cap
a, b = np.polyfit(mono[supr], mp_z[supr], 1)
r = np.corrcoef(mono[supr], mp_z[supr])[0, 1]
print(f'potrivire pe suprapunere ({supr.sum()} px):  mp ≈ {a:.1f}·mono + {b:.1f}   r={r:.3f}')

baza = a * mono + b

# Detaliul plasei: ce rămâne după ce scoatem forma mare.
mpf = np.where(fata, mp_z, 0.0)
k = 81
neted = cv2.GaussianBlur(mpf, (k, k), 0)
pond = cv2.GaussianBlur(fata.astype(np.float64), (k, k), 0)
neted = np.divide(neted, pond, out=np.zeros_like(neted), where=pond > 1e-6)
detaliu = np.where(fata, mp_z - neted, 0.0)
print(f'detaliu facial: ±{np.abs(detaliu[fata]).max():.1f} px')

# Îmbinare moale la marginea măştii, ca să nu apară o treaptă în metal acolo.
alfa = cv2.GaussianBlur(fata.astype(np.float64), (61, 61), 0)
alfa = np.clip((alfa - 0.25) / 0.5, 0, 1)

z = baza + alfa * detaliu
z = np.where(cap, z, np.nan)

# Netezire uşoară: marginea segmentării are zimţi de un pixel.
zf = np.where(np.isnan(z), 0, z)
m = (~np.isnan(z)).astype(np.float64)
zf = cv2.GaussianBlur(zf, (9, 9), 0)
mf = cv2.GaussianBlur(m, (9, 9), 0)
z = np.where(cap, np.divide(zf, mf, out=np.zeros_like(zf), where=mf > 1e-6), np.nan)

np.save('fuzionat.npy', z)
zv = z[cap]
print(f'relief final: {np.ptp(zv):.1f} px  |  acoperă {cap.sum() / (H * W) * 100:.1f}% din cadru')

norm = np.zeros_like(z)
norm[cap] = (zv - zv.min()) / np.ptp(zv)
vis = cv2.applyColorMap((np.nan_to_num(norm) * 255).astype(np.uint8), cv2.COLORMAP_TURBO)
vis[~cap] = (28, 22, 18)
cv2.imwrite('out_fuzionat.png', vis)
print('adâncime fuzionată scrisă')
