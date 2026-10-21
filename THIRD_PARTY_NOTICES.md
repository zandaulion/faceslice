# Model and dependency notices

The Faceslice source release does not contain pretrained model weights or Python
packages. Run `python3 scripts/download-models.py` to fetch the three public
model files from their upstream hosts. The downloader verifies their SHA-256
digests before placing them in `models/`.

| Local file | Upstream | Notes |
| --- | --- | --- |
| `face_landmarker.task` | [Google MediaPipe Face Landmarker](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker) | Public task model hosted by Google. |
| `selfie_multiclass.tflite` | [Google MediaPipe Image Segmenter](https://developers.google.com/edge/mediapipe/solutions/vision/image_segmenter) | Public segmentation model hosted by Google. |
| `depth.onnx` | [onnx-community Depth Anything V2 Small](https://huggingface.co/onnx-community/depth-anything-v2-small) | ONNX export of the Small model; model card declares Apache-2.0. |

The Google MediaPipe source library is Apache-2.0. This notice does not assign
that license to the two Google-hosted model assets; check the applicable upstream
terms before redistributing their bytes. The downloader gets them from Google
for the user's own installation. Python dependencies are installed from
`requirements.txt` and retain their own upstream licenses.

Faceslice's original source and documentation are GPL-3.0-or-later; see
`LICENSE`. Existing copies distributed before this license change retain the
terms under which they were received.
