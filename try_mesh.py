"""Prima sondă: scoate MediaPipe o plasă 3D din fotografiile astea?

Nu construim nimic încă. Întrebarea e dacă găseşte faţa în fiecare cadru, şi
cât din cap acoperă -- ştiind că avem şi profile, şi un unghi de dedesubt,
care sunt cazuri grele pentru un detector antrenat mai ales pe portrete.
"""
import glob
import numpy as np
import cv2
import mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions

opt = vision.FaceLandmarkerOptions(
    base_options=BaseOptions(model_asset_path='models/face_landmarker.task'),
    running_mode=vision.RunningMode.IMAGE,
    num_faces=1,
    min_face_detection_confidence=0.25,
    output_facial_transformation_matrixes=True)

with vision.FaceLandmarker.create_from_options(opt) as det:
    for f in sorted(glob.glob('photos/*.jpg')):
        img = cv2.imread(f)
        h, w = img.shape[:2]
        small = cv2.resize(img, (w // 4, h // 4))
        mpimg = mp.Image(image_format=mp.ImageFormat.SRGB,
                         data=cv2.cvtColor(small, cv2.COLOR_BGR2RGB))
        res = det.detect(mpimg)
        if not res.face_landmarks:
            print(f'{f}  — nicio faţă găsită')
            continue
        pts = np.array([[p.x, p.y, p.z] for p in res.face_landmarks[0]])
        lat = np.ptp(pts[:, 0]) * (w // 4)
        inalt = np.ptp(pts[:, 1]) * (h // 4)
        print(f'{f}  {len(pts)} puncte  |  faţa ocupă {lat:.0f}x{inalt:.0f} px'
              f'  |  întindere în adâncime {np.ptp(pts[:, 2]):.3f}')
