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

## In English

Faceslice turns one frontal portrait into a layered relief and cutting geometry.
The interface and main guide are in Romanian. It is an experimental fabrication
tool: verify physical dimensions and cutting constraints before manufacturing.
The browser uploads a selected portrait to your own server for CPU processing;
keep that server and its stored jobs private. [Project overview](https://zandaulion.com/faceslice.html).

## Rulare

Ai nevoie de Podman, Python 3, `curl` și `openssl`. Imaginea instalează Python
3.13 și dependențele aplicației; Python-ul gazdei descarcă doar modelele.
Descarcă [arhiva v0.1.0](https://github.com/zandaulion/faceslice/releases/tag/v0.1.0)
și verifică fișierul `SHA256SUMS` din release, sau clonează codul sursă.
Rulează comenzile din rădăcina proiectului. Descarcă modelele **înainte** de build.

Modelele nu sunt în arhivă sau depozit — aproximativ 114 MB de fișiere terțe.
Scriptul le descarcă de la sursele indicate în
[notificările pentru terți](THIRD_PARTY_NOTICES.md), verifică SHA-256 pentru
fiecare și le așază în `models/`. Dacă sursa schimbă un model, verificarea se
oprește înainte de build:

```bash
python3 scripts/download-models.py
```

Pornește un exemplar local cu un volum separat pentru date:

```bash
podman build -t faceslice:local -f deploy/Containerfile .
export ADMIN_TOKEN="$(openssl rand -hex 32)"
podman run --rm --name faceslice-demo \
  -p 127.0.0.1:8000:8000 -v faceslice-demo-data:/data \
  -e ADMIN_TOKEN -e PUBLIC_BASE_URL=http://127.0.0.1:8000 \
  -e COOKIE_SECURE=0 -d faceslice:local
curl --fail http://127.0.0.1:8000/api/health
curl --fail http://127.0.0.1:8000/api/admin/invites \
  -H "X-Admin-Token: $ADMIN_TOKEN" -H 'Content-Type: application/json' \
  --data '{"label":"Demo device"}'
```

Deschide câmpul `url` întors de ultima comandă și folosește codul invitației.
După activare, poți încărca [portretul de test complet sintetic](examples/synthetic-portrait.png)
pentru a verifica reconstrucția, previzualizarea și exportul DXF fără datele
unei persoane reale. Imaginea este un exemplu de test, nu o garanție că o
fotografie sau o piesă tăiată va avea dimensiuni corecte.
`COOKIE_SECURE=0` este numai pentru proba HTTP pe loopback. În producție folosește
HTTPS, cookie-ul securizat implicit și un secret păstrat într-un fișier privat.
Nu expune API-ul de administrare pe ruta publică.

`podman stop faceslice-demo` oprește proba; volumul păstrează baza de date și
fișierele de lucru. Pentru backup, oprește containerul și copiază întregul volum
într-un loc privat. Nu publica fotografii sau rezultate provenite de la persoane.

`./deploy.sh` reconstruiește imaginea și repornește un serviciu systemd **deja
instalat**; nu este program de instalare. Configurează unitatea pe gazda ta pornind
de la aceeași imagine, variabile și volum ca în exemplul de mai sus.

Totul rulează pe procesor: reconstrucția și felierea depind de calculator și imagine.

## Ce nu face

- Nu măsoară: scara vine dintr-un număr introdus de om, nu din fotografie.
- Nu vede ce nu apare din faţă — cefele şi scobiturile ascunse lipsesc, fiindcă
  obiectul e un relief, nu un cap întreg.
- Nu ştie kerful maşinii tale. Valoarea implicită e o presupunere; întreabă
  atelierul înainte de tăiere.


## Support and contributions

Use this repository’s Issues for reproducible bugs and focused feature requests. Include the version, relevant runtime/browser, expected behavior and a minimal synthetic example. Remove credentials, personal records, device identifiers and deployment-specific values before sharing logs or screenshots.

Use synthetic artwork when reporting geometry problems. Original Faceslice code
and documentation are [GPL-3.0-or-later](LICENSE). Downloaded models and Python
packages retain their own upstream terms; see [third-party notices](THIRD_PARTY_NOTICES.md).

Keep changes focused and update the affected documentation. Security-sensitive reports should follow [SECURITY.md](SECURITY.md).
