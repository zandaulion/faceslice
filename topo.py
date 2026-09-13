"""Desenează relieful ca o hartă topografică: exact ce ar ieşi din tăiere."""
import numpy as np
import cv2

z = np.load('depth.npy')
valid = ~np.isnan(z)
lo, hi = np.percentile(z[valid], [2, 99.5])
pas = 3.0 / 0.375
niveluri = np.arange(lo, hi, pas)
H, W = z.shape
zf = np.where(valid, z, -1e9)

# Decupăm la faţă, ca preview-ul să nu fie jumătate fundal.
ys, xs = np.where(valid)
m = 40
y0, y1 = max(ys.min() - m, 0), min(ys.max() + m, H)
x0, x1 = max(xs.min() - m, 0), min(xs.max() + m, W)

umplut = np.full((H, W, 3), 245, np.uint8)
linii = np.full((H, W, 3), 255, np.uint8)

for i, nivel in enumerate(niveluri):
    masca = (zf >= nivel).astype(np.uint8)
    masca = cv2.morphologyEx(masca, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    masca = cv2.morphologyEx(masca, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    cnts, _ = cv2.findContours(masca, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = [c for c in cnts if cv2.contourArea(c) > 200]

    t = i / max(len(niveluri) - 1, 1)
    # Paletă de hartă: retras spre verde-albăstrui, ieşit în afară spre teracotă.
    col = (int(190 - 70 * t), int(205 - 40 * t), int(175 + 70 * t))
    cv2.drawContours(umplut, cnts, -1, col, -1)
    cv2.drawContours(umplut, cnts, -1, (110, 95, 80), 1)
    cv2.drawContours(linii, cnts, -1, (90, 75, 60), 1)

cv2.imwrite('out_topo.png', np.hstack([umplut[y0:y1, x0:x1], linii[y0:y1, x0:x1]]))
print(f'{len(niveluri)} niveluri desenate')
