"""Feliază harta de adâncime în curbe de nivel, ca pe o hartă topografică.

Un relief frontal are o proprietate pe care un cap întreg feliat orizontal n-o
are: straturile se cuibăresc unul în altul. Fiecare nivel e o insulă în
interiorul celui de dedesubt, ca izohipsele pe un munte. Asta rezolvă dintr-o
lovitură alinierea -- fiecare placă se aşază pe cea dinainte -- şi elimină
problema insulelor plutitoare.
"""
import numpy as np
import cv2

z = np.load('depth.npy')
valid = ~np.isnan(z)
zv = z[valid]

print('distribuţia adâncimii (percentile):')
for p in (0, 1, 5, 25, 50, 75, 95, 99, 100):
    print(f'   {p:3d}%  {np.percentile(zv, p):6.1f} px')

# Marginile plasei se curbează înapoi şi trag intervalul; tăiem cozile ca
# relieful să nu fie dominat de câţiva pixeli de pe contur.
lo, hi = np.percentile(zv, [2, 99.5])
print(f'\ninterval de lucru: {lo:.1f} … {hi:.1f} px  ({hi - lo:.1f} px)')

# Scara: lăţimea feţei între tâmple e ~150 mm la un adult.
LATIME_FATA_MM = 150.0
xs = np.where(valid.any(axis=0))[0]
lat_px = xs.max() - xs.min()
mm_pe_px = LATIME_FATA_MM / lat_px
print(f'faţa: {lat_px} px → {LATIME_FATA_MM:.0f} mm   ({mm_pe_px:.3f} mm/px)')
print(f'relief real: {(hi - lo) * mm_pe_px:.1f} mm de la cel mai retras la nas')

for gros in (2, 3, 4, 5):
    n = int((hi - lo) * mm_pe_px / gros)
    print(f'   tablă de {gros} mm  →  {n:2d} straturi')
