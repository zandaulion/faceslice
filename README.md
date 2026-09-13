# Faceslice

De la o fotografie frontală la plăcile de tăiat pentru un portret în straturi —
un relief ca o hartă topografică, din tablă, lipit manual strat peste strat.

## Cum funcţionează

Trei modele, fiecare pentru ce ştie mai bine. Niciunul singur nu dă un cap:

| | dă | nu dă |
|---|---|---|
| segmentare | silueta cu păr, urechi, linia maxilarului | nimic despre adâncime |
| adâncime monoculară | craniu, păr, forma mare | aplatizează faţa |
| plasă facială | nas, orbite, buze | se opreşte la mijlocul frunţii |

Forma mare vine de la monocular, detaliul facial de la plasă — şi anume doar
diferenţa faţă de propria variantă netezită, ca să se împrumute relieful
nasului fără să se importe şi eventuala eroare de formă generală.

Relieful devine apoi un solid cu spatele plat, iar solidul se taie cu plane
paralele. Unghiul planelor e liber: frontal dă curbe de nivel cuibărite,
orizontal dă felii de profil.

## De ce o singură fotografie

Un relief frontal nu cere un cap întreg, ci adâncimea `Z(x,y)` pe partea văzută.
Asta scoate cu totul fotogrametria din drum — şi, mai important, scoate cerinţa
ca cineva să înveţe o aplicaţie de scanare. Un selfie e de ajuns.

Singura măsurătoare necesară e distanţa dintre pupile, în milimetri, fără de
care obiectul iese corect ca formă şi arbitrar ca mărime.

## Ce rezolvă felierea frontală

Straturile se cuibăresc: fiecare e conţinut în cel de dedesubt, ca izohipsele
pe un munte. Teancul se aliniază singur, iar pe fiecare placă e gravat conturul
plăcii următoare — aşezi placa următoare exact pe linia desenată.

La celelalte unghiuri cuibărirea se pierde şi conturul gravat devine
obligatoriu, nu comod.

## Cifre, pe un cap de 137 mm lăţime

```
relief brut       ~110 mm de la nas la planul urechilor
comprimat          60 mm  →  20 plăci de 3 mm, 15 contururi distincte
golit              80% mai puţin material; ce e acoperit nu se vede
                   10 kg oţel plin  →  1,9 kg inele
```

## Rulare

```bash
./deploy.sh                    # construieşte imaginea şi reporneşte serviciul
```

Modelele nu sunt în depozit — 114 MB de greutăţi care nu sunt codul nostru.
Se aşază în `models/`:

```bash
mkdir -p models
curl -L -o models/face_landmarker.task \
  https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task
curl -L -o models/selfie_multiclass.tflite \
  https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_multiclass_256x256/float32/latest/selfie_multiclass_256x256.tflite
curl -L -o models/depth.onnx \
  https://huggingface.co/onnx-community/depth-anything-v2-small/resolve/main/onnx/model.onnx
```

Totul rulează pe procesor: reconstrucţia ia ~2,5 s, o feliere sub o secundă.

## Ce nu face

- Nu măsoară: scara vine dintr-un număr introdus de om, nu din fotografie.
- Nu vede ce nu apare din faţă — cefele şi scobiturile ascunse lipsesc, fiindcă
  obiectul e un relief, nu un cap întreg.
- Nu ştie kerful maşinii tale. Valoarea implicită e o presupunere; întreabă
  atelierul înainte de tăiere.
