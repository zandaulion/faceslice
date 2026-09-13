"""Desenează punctele peste fotografie, ca să se vadă ce acoperă şi ce nu."""
import glob
import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions

opt = vision.FaceLandmarkerOptions(
    base_options=BaseOptions(model_asset_path='models/face_landmarker.task'),
    running_mode=vision.RunningMode.IMAGE, num_faces=1,
    min_face_detection_confidence=0.25)

with vision.FaceLandmarker.create_from_options(opt) as det:
    for f in sorted(glob.glob('photos/[0-9][0-9].jpg')):
        img = cv2.imread(f)
        h, w = img.shape[:2]
        small = cv2.resize(img, (w // 6, h // 6))
        sh, sw = small.shape[:2]
        res = det.detect(mp.Image(image_format=mp.ImageFormat.SRGB,
                                  data=cv2.cvtColor(small, cv2.COLOR_BGR2RGB)))
        if not res.face_landmarks:
            cv2.putText(small, 'nicio fata', (20, 60), cv2.FONT_HERSHEY_SIMPLEX,
                        1.2, (0, 0, 255), 3)
        else:
            pts = np.array([[p.x * sw, p.y * sh] for p in res.face_landmarks[0]], np.int32)
            for x, y in pts:
                cv2.circle(small, (x, y), 1, (0, 255, 0), -1)
            x0, y0, bw, bh = cv2.boundingRect(pts)
            cv2.rectangle(small, (x0, y0), (x0 + bw, y0 + bh), (255, 200, 0), 2)
        cv2.imwrite(f.replace('.jpg', '_puncte.jpg'), small)
print('suprapuneri scrise')
