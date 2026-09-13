"""Un relief frontal, dintr-o singură fotografie.

Un portret în straturi privit din faţă nu cere un cap întreg: cere adâncimea
Z(x,y) pe partea văzută. Asta schimbă complet problema -- de la reconstrucţie
3D la o hartă de adâncime, exact ca o hartă topografică unde fiecare strat e o
curbă de nivel.

MediaPipe dă deja 478 de puncte cu z. Le triangulăm şi rasterizăm între ele,
apoi tăiem harta în trepte. Interpolarea e baricentrică, nu plată pe triunghi:
frunţile şi obrajii sunt triunghiuri mari, iar umplerea plată le-ar face
trepte false, care s-ar vedea ca terase în metal.
"""
import numpy as np
import cv2
import mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions

LAT = 900  # lăţimea la care lucrăm

opt = vision.FaceLandmarkerOptions(
    base_options=BaseOptions(model_asset_path='models/face_landmarker.task'),
    running_mode=vision.RunningMode.IMAGE, num_faces=1)

img = cv2.imread('photos/02.jpg')
h, w = img.shape[:2]
scale = LAT / w
img = cv2.resize(img, (LAT, int(h * scale)))
H, W = img.shape[:2]

with vision.FaceLandmarker.create_from_options(opt) as det:
    res = det.detect(mp.Image(image_format=mp.ImageFormat.SRGB,
                              data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))
lm = res.face_landmarks[0]
P = np.array([[p.x * W, p.y * H, p.z * W] for p in lm], np.float64)
print(f'puncte: {len(P)}')
print(f'faţa ocupă {np.ptp(P[:,0]):.0f} x {np.ptp(P[:,1]):.0f} px')
print(f'adâncimea brută: {np.ptp(P[:,2]):.1f} px (z-ul MediaPipe e la scara lui x)')

# Triangulaţie Delaunay. `scipy` întoarce direct indici în tabloul de intrare;
# prima încercare folosea cv2.Subdiv2D, care întoarce coordonate, iar căutarea
# înapoi prin rotunjire n-a potrivit niciun punct -- zero triunghiuri, tăcut.
from scipy.spatial import Delaunay
tris = Delaunay(P[:, :2]).simplices
print(f'triunghiuri: {len(tris)}')

# Rasterizare cu interpolare baricentrică.
depth = np.full((H, W), np.nan)
for a, b, c in tris:
    p0, p1, p2 = P[a], P[b], P[c]
    x0 = max(int(min(p0[0], p1[0], p2[0])), 0)
    x1 = min(int(max(p0[0], p1[0], p2[0])) + 1, W)
    y0 = max(int(min(p0[1], p1[1], p2[1])), 0)
    y1 = min(int(max(p0[1], p1[1], p2[1])) + 1, H)
    if x1 <= x0 or y1 <= y0:
        continue
    yy, xx = np.mgrid[y0:y1, x0:x1]
    d = ((p1[1] - p2[1]) * (p0[0] - p2[0]) + (p2[0] - p1[0]) * (p0[1] - p2[1]))
    if abs(d) < 1e-9:
        continue
    l0 = ((p1[1] - p2[1]) * (xx - p2[0]) + (p2[0] - p1[0]) * (yy - p2[1])) / d
    l1 = ((p2[1] - p0[1]) * (xx - p2[0]) + (p0[0] - p2[0]) * (yy - p2[1])) / d
    l2 = 1 - l0 - l1
    inside = (l0 >= 0) & (l1 >= 0) & (l2 >= 0)
    z = l0 * p0[2] + l1 * p1[2] + l2 * p2[2]
    sub_d = depth[y0:y1, x0:x1]
    sub_d[inside] = z[inside]

valid = ~np.isnan(depth)
print(f'suprafaţă acoperită: {valid.sum() / (H * W) * 100:.1f}% din imagine')

# În MediaPipe, z creşte spre cameră negativ; îl întoarcem ca "mai mare = mai
# aproape de privitor", cum e la o hartă de nivel.
z = -depth
z = z - np.nanmin(z)
np.save('depth.npy', np.where(valid, z, np.nan))
print(f'relief: {np.nanmax(z):.1f} px de la cel mai retras la vârful nasului')

vis = np.zeros((H, W, 3), np.uint8)
norm = np.where(valid, z / np.nanmax(z), 0)
vis[..., 0] = (norm * 255).astype(np.uint8)
vis[..., 1] = (norm * 255).astype(np.uint8)
vis[..., 2] = (norm * 255).astype(np.uint8)
vis[~valid] = (30, 20, 20)
cv2.imwrite('out_depth.png', vis)
print('hartă de adâncime scrisă')
