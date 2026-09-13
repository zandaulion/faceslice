"""Extrage conturile de nivel şi verifică proprietatea care face proiectul uşor.

Întrebarea nu e dacă ies contururi -- ies mereu. E dacă fiecare nivel e conţinut
în cel de dedesubt. Dacă da, plăcile se aşază una peste alta ca un munte şi
alinierea e aproape gratuită. Dacă nu, avem insule care plutesc şi trebuie
prinse cumva.
"""
import numpy as np
import cv2

z = np.load('depth.npy')
valid = ~np.isnan(z)
lo, hi = np.percentile(z[valid], [2, 99.5])

GROSIME_MM = 3.0
MM_PE_PX = 0.375
pas = GROSIME_MM / MM_PE_PX
niveluri = np.arange(lo, hi, pas)
print(f'{len(niveluri)} straturi, pas de {pas:.1f} px = {GROSIME_MM} mm\n')

H, W = z.shape
zf = np.where(valid, z, -1e9)

straturi = []
for i, nivel in enumerate(niveluri):
    masca = (zf >= nivel).astype(np.uint8)
    # Netezire uşoară: marginea unei tăieturi în metal nu trebuie să urmeze
    # zimţii de la rasterizare.
    masca = cv2.morphologyEx(masca, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    masca = cv2.morphologyEx(masca, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    cnts, _ = cv2.findContours(masca, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = [c for c in cnts if cv2.contourArea(c) > 200]
    straturi.append((nivel, masca, cnts))

print('strat   arie(mm²)  bucăţi  cuibărit în cel dinainte')
prev = None
nec = 0
for i, (nivel, masca, cnts) in enumerate(straturi):
    arie = masca.sum() * MM_PE_PX ** 2
    if prev is None:
        stare = '—'
    else:
        # Cuibărit = fiecare pixel al stratului e şi în cel dinainte.
        afara = int((masca.astype(bool) & ~prev.astype(bool)).sum())
        stare = 'da' if afara < 30 else f'NU ({afara} px pe dinafară)'
        if afara >= 30:
            nec += 1
    print(f'  {i:2d}   {arie:8.0f}   {len(cnts):3d}     {stare}')
    prev = masca

print(f'\nstraturi necuibărite: {nec} din {len(straturi) - 1}')
np.save('niveluri.npy', niveluri)
