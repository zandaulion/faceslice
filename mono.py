"""Adâncime monoculară pentru tot capul, inclusiv păr şi craniu.

Plasa facială e exactă dar acoperă doar masca. Modelul ăsta dă o adâncime
relativă pentru fiecare pixel din imagine -- inclusiv părul, urechile şi
creştetul, care lipseau cu totul. E mai puţin precis ca structură, dar acoperă
exact ce nu acoperea celălalt.
"""
import time
import numpy as np
import cv2
import onnxruntime as ort

LAT = 900
IN = 518  # multiplu de 14, cum cere modelul

img = cv2.imread('photos/02.jpg')
h, w = img.shape[:2]
img = cv2.resize(img, (LAT, int(h * LAT / w)))
H, W = img.shape[:2]

x = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2RGB), (IN, IN)).astype(np.float32) / 255.0
x = (x - np.array([0.485, 0.456, 0.406])) / np.array([0.229, 0.224, 0.225])
x = x.transpose(2, 0, 1)[None].astype(np.float32)

s = ort.InferenceSession('models/depth.onnx', providers=['CPUExecutionProvider'])
t0 = time.time()
d = s.run(None, {'pixel_values': x})[0][0]
print(f'inferenţă: {time.time() - t0:.1f} s pe procesor  →  {d.shape}')

d = cv2.resize(d, (W, H), interpolation=cv2.INTER_CUBIC)
np.save('mono.npy', d)

cap = np.load('cap.npy').astype(bool)
dc = d[cap]
print(f'în siluetă: {dc.min():.1f} … {dc.max():.1f}  (mai mare = mai aproape)')
print(f'contrast cap vs fundal: cap {np.median(dc):.1f}  fundal {np.median(d[~cap]):.1f}')

vis = ((d - d.min()) / np.ptp(d) * 255).astype(np.uint8)
vis = cv2.applyColorMap(vis, cv2.COLORMAP_TURBO)
vis[~cap] = (vis[~cap] * 0.25).astype(np.uint8)
cv2.imwrite('out_mono.png', vis)
print('adâncime monoculară scrisă')
