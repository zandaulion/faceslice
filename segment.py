"""Silueta capului, cu păr.

Plasa MediaPipe se opreşte la mijlocul frunţii -- e o mască, nu un cap. Pentru
un portret în straturi ne trebuie conturul adevărat: păr, urechi, linia gâtului.
Modelul multiclass dă chiar clasele de care avem nevoie, inclusiv una separată
pentru păr.
"""
import numpy as np
import cv2
import mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions

CLASE = {0: 'fundal', 1: 'păr', 2: 'piele corp', 3: 'piele faţă',
         4: 'haine', 5: 'altele'}
LAT = 900

opt = vision.ImageSegmenterOptions(
    base_options=BaseOptions(model_asset_path='models/selfie_multiclass.tflite'),
    running_mode=vision.RunningMode.IMAGE,
    output_category_mask=True)

img = cv2.imread('photos/02.jpg')
h, w = img.shape[:2]
img = cv2.resize(img, (LAT, int(h * LAT / w)))
H, W = img.shape[:2]

with vision.ImageSegmenter.create_from_options(opt) as seg:
    res = seg.segment(mp.Image(image_format=mp.ImageFormat.SRGB,
                               data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))
cat = np.squeeze(res.category_mask.numpy_view())
print(f'mască {cat.shape}, clase găsite:')
for c in np.unique(cat):
    n = (cat == c).sum()
    print(f'   {c} {CLASE.get(int(c), "?"):12} {n / cat.size * 100:5.1f}%')

# Capul = păr + pielea feţei. Gâtul şi umerii (piele corp) se taie: un portret
# se termină la maxilar, altfel primele straturi ar fi doar umeri.
cap = np.isin(cat, [1, 3]).astype(np.uint8)
cap = cv2.morphologyEx(cap, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
n, lab, stats, _ = cv2.connectedComponentsWithStats(cap)
if n > 1:
    cap = (lab == 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])).astype(np.uint8)
cap = cv2.morphologyEx(cap, cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8))

ys, xs = np.where(cap > 0)
print(f'\ncapul: {np.ptp(xs)} x {np.ptp(ys)} px, {cap.sum() / cap.size * 100:.1f}% din cadru')
np.save('cap.npy', cap)

vis = img.copy()
vis[cap > 0] = (0.55 * vis[cap > 0] + 0.45 * np.array([90, 200, 120])).astype(np.uint8)
cnts, _ = cv2.findContours(cap, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
cv2.drawContours(vis, cnts, -1, (40, 230, 90), 3)
cv2.imwrite('out_silueta.png', vis)
print('siluetă scrisă')
