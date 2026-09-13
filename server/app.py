"""Faceslice — de la o fotografie la plăcile de tăiat.

Fluxul are două costuri foarte diferite, şi de aceea şi două etape. Modelele
grele rulează o singură dată, la încărcarea fotografiei, şi rezultatul lor --
harta de adâncime -- rămâne pe disc. Felierea, care se schimbă la fiecare
mişcare de cursor, lucrează după aceea doar pe tabloul salvat. Aşa reglajele
răspund sub o secundă fără să reîncarce nimic.
"""
from __future__ import annotations

import io
import json
import os
import re
import secrets
import shutil
import zipfile
from datetime import datetime, timedelta, timezone

import cv2
import numpy as np
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from auth import cod_nou, dispozitiv, doar_admin, revendica
from db import DB, acum, dosar_job
import dxf as dxfmod
import pipeline
import profil
import render
from slicer import Reglaje, Solid

app = FastAPI(title="Faceslice", docs_url=None, redoc_url=None)
WEB = os.environ.get("WEB_DIR", "web")
MAX_FOTO = 25 * 1024 * 1024


# ---------------------------------------------------------------- acces

@app.get("/api/health")
def health():
    return {"ok": True, "acum": acum()}


@app.post("/api/invites/redeem")
async def revendicare(request: Request):
    d = await request.json()
    dev, jeton = revendica(str(d.get("code", "")), d.get("label"))
    r = JSONResponse({"device_id": dev, "token": jeton})
    # Cookie pe lângă răspuns: descărcarea DXF-ului merge atunci dintr-un link
    # obişnuit, fără cod care să adauge antete.
    r.set_cookie("faceslice_token", jeton, max_age=3600 * 24 * 3650,
                 httponly=True, samesite="lax",
                 secure=os.environ.get("COOKIE_SECURE", "1") == "1")
    return r


@app.get("/api/me")
def eu(dev: dict = Depends(dispozitiv)):
    return {"id": dev["id"], "label": dev["label"]}


# ---------------------------------------------------------------- lucrări

def _citeste_foto(date: bytes) -> np.ndarray:
    arr = np.frombuffer(date, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(400, "Fişierul nu e o imagine pe care s-o pot citi.")
    h, w = img.shape[:2]
    if min(h, w) < 400:
        raise HTTPException(400, "Fotografia e prea mică; am nevoie de cel puţin 400 px.")
    return img


@app.post("/api/jobs")
async def lucrare_noua(foto: UploadFile = File(...),
                       profil_foto: UploadFile | None = File(None),
                       dip_mm: float = Form(pipeline.DIP_IMPLICIT_MM),
                       oglindit: bool = Form(False),
                       cu_gat: bool = Form(True),
                       dev: dict = Depends(dispozitiv)):
    date = await foto.read()
    if len(date) > MAX_FOTO:
        raise HTTPException(413, "Fotografie prea mare.")
    img = _citeste_foto(date)
    if oglindit:
        # Camera frontală întoarce imaginea. Netratat, portretul iese în oglindă
        # -- ceea ce se vede abia după tăiere, când nu mai e nimic de făcut.
        img = cv2.flip(img, 1)

    try:
        rec = pipeline.reconstruieste(img, dip_mm=dip_mm, cu_gat=cu_gat)
    except (pipeline.FaraFata, pipeline.PozaNepotrivita) as e:
        raise HTTPException(422, str(e))

    # A doua poză, dacă există: din ea se măsoară cât de adânc e relieful
    # omului acestuia, fotografiat cu aparatul acesta. Fără ea rămâne media.
    calibrare = None
    if profil_foto is not None:
        date_p = await profil_foto.read()
        if date_p:
            if len(date_p) > MAX_FOTO:
                raise HTTPException(413, "A doua fotografie e prea mare.")
            # A doua poză nu poate opri lucrarea. Prima ajunge; asta doar
            # ridică precizia, iar când nu poate, se spune şi se merge mai
            # departe. Un refuz aici ar fi însemnat să pierzi şi reconstrucţia
            # deja făcută, din cauza unei poze opţionale.
            try:
                calibrare = profil.calibreaza(rec, _citeste_foto(date_p))
            except profil.ProfilNepotrivit as e:
                calibrare = profil.Calibrare(1.0, 0.0, 0.0, 0.0,
                                             folosita=False, motiv=str(e))

    jid = secrets.token_hex(8)
    d = dosar_job(jid)
    cv2.imwrite(os.path.join(d, "foto.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 88])
    np.savez_compressed(os.path.join(d, "relief.npz"),
                        baza=rec.baza.astype(np.float32),
                        detaliu=rec.detaliu.astype(np.float32),
                        alfa=rec.alfa.astype(np.float32),
                        cap=rec.cap, mm_pe_px=rec.mm_pe_px)
    rez = rec.rezumat()
    reusit = bool(calibrare and calibrare.folosita)
    rez["detaliu"] = calibrare.factor if reusit else pipeline.DETALIU_IMPLICIT
    rez["calibrat"] = reusit
    rez["cu_gat"] = cu_gat
    if calibrare:
        rez["calibrare"] = calibrare.rezumat()
        if not reusit:
            rez["calibrare_motiv"] = calibrare.motiv
    DB.execute("INSERT INTO jobs (id, device_id, created_at, nume, rezumat, reglaje)"
               " VALUES (?,?,?,?,?,?)",
               (jid, dev["id"], acum(), foto.filename or "portret",
                json.dumps(rez), json.dumps({})))
    DB.commit()
    return {"id": jid, "rezumat": rez}


@app.get("/api/jobs")
def lucrari(dev: dict = Depends(dispozitiv)):
    rows = DB.execute("SELECT id, created_at, nume, rezumat, reglaje FROM jobs"
                      " WHERE device_id=? ORDER BY created_at DESC LIMIT 200",
                      (dev["id"],)).fetchall()
    return [{"id": r["id"], "creat": r["created_at"], "nume": r["nume"],
             "rezumat": json.loads(r["rezumat"] or "{}"),
             "reglaje": json.loads(r["reglaje"] or "{}")} for r in rows]


@app.post("/api/jobs/{jid}/nume")
async def redenumeste(jid: str, request: Request, dev: dict = Depends(dispozitiv)):
    nume = ((await _corp(request)).get("nume") or "").strip()[:80] or None
    cur = DB.execute("UPDATE jobs SET nume=? WHERE id=? AND device_id=?",
                     (nume, jid, dev["id"]))
    if not cur.rowcount:
        raise HTTPException(404, "Lucrarea nu există.")
    DB.commit()
    return {"id": jid, "nume": nume}


@app.post("/api/jobs/{jid}/duplica")
def duplica(jid: str, dev: dict = Depends(dispozitiv)):
    """O variantă porneşte de la acelaşi relief, nu de la aceeaşi fotografie.

    Reconstrucţia e partea scumpă -- două secunde şi jumătate -- şi n-are de ce
    fi refăcută ca să încerci altă grosime de tablă. Se copiază fişierele şi se
    porneşte de la reglajele lucrării de la care s-a plecat, ca varianta nouă
    să fie punctul în care ai rămas, nu o pagină goală."""
    r = DB.execute("SELECT * FROM jobs WHERE id=? AND device_id=?",
                   (jid, dev["id"])).fetchone()
    if not r:
        raise HTTPException(404, "Lucrarea nu există.")
    nou = secrets.token_hex(8)
    shutil.copytree(dosar_job(jid), dosar_job(nou), dirs_exist_ok=True)
    DB.execute("INSERT INTO jobs (id, device_id, created_at, nume, rezumat, reglaje)"
               " VALUES (?,?,?,?,?,?)",
               (nou, dev["id"], acum(), _nume_variantei(r["nume"]),
                r["rezumat"], r["reglaje"]))
    DB.commit()
    return {"id": nou}


def _nume_variantei(nume: str | None) -> str:
    """„Ion" -> „Ion (2)"; „Ion (2)" -> „Ion (3)".

    Numerotarea continuă în loc să adauge încă un „(copie)" peste altul, ca a
    cincea încercare să nu se cheme „Ion (copie) (copie) (copie) (copie)"."""
    baza = (nume or "portret").strip()
    m = re.match(r"^(.*?)\s*\((\d+)\)$", baza)
    if m:
        return f"{m.group(1)} ({int(m.group(2)) + 1})"
    return f"{baza} (2)"


def _detaliu_lucrarii(r) -> float:
    """Amplificarea proprie lucrării: cea măsurată din profil, altfel media."""
    try:
        return float(json.loads(r["rezumat"] or "{}").get(
            "detaliu", pipeline.DETALIU_IMPLICIT))
    except (TypeError, ValueError):
        return pipeline.DETALIU_IMPLICIT


def _incarca(jid: str, dev: dict, detaliu_x: float | None = None):
    """Adâncimea, recompusă cu amplificarea cerută.

    Componentele stau separat pe disc tocmai ca amestecul să fie un reglaj:
    schimbarea lui costă o adunare, nu o reconstrucţie de două secunde."""
    r = DB.execute("SELECT * FROM jobs WHERE id=? AND device_id=?",
                   (jid, dev["id"])).fetchone()
    if not r:
        raise HTTPException(404, "Lucrarea nu există.")
    if detaliu_x is None:
        detaliu_x = _detaliu_lucrarii(r)
    f = np.load(os.path.join(dosar_job(jid), "relief.npz"))
    cap = f["cap"]
    z = f["baza"].astype(np.float64) + detaliu_x * f["alfa"] * f["detaliu"]
    z[~cap] = np.nan
    return r, z, cap, float(f["mm_pe_px"])


@app.get("/api/jobs/{jid}/foto")
def foto_lucrare(jid: str, dev: dict = Depends(dispozitiv)):
    _incarca(jid, dev)
    return FileResponse(os.path.join(dosar_job(jid), "foto.jpg"), media_type="image/jpeg")


def _reglaje(d: dict) -> Reglaje:
    r = Reglaje()
    for k, v in (d or {}).items():
        if hasattr(r, k) and v is not None:
            setattr(r, k, type(getattr(r, k))(v))
    r.sari = max(1, min(int(r.sari), 6))
    r.grosime_mm = float(np.clip(r.grosime_mm, 0.5, 20))
    r.adancime_mm = float(np.clip(r.adancime_mm, 10, 300))
    r.inclinare = float(np.clip(r.inclinare, -90, 90))
    r.rotire = float(np.clip(r.rotire, -90, 90))
    return r


def _trepte_nas(solid: Solid, reg) -> dict:
    """Pe câte plăci se întinde nasul, în obiectul final.

    E cifra care spune dacă portretul va fi citibil, şi singura care leagă
    grosimea tablei de ce se vede: sub vreo patru trepte nasul iese blocat.
    Altfel se află abia după tăiere, când nu mai e nimic de făcut.

    Se măsoară pe relieful deja comprimat la adâncimea cerută, nu pe
    reconstrucţie: între ele stau comprimarea şi curba, iar amândouă schimbă
    exact cifra asta."""
    try:
        zc = solid._comprimat(reg) * solid.mm          # în milimetri
    except Exception:
        return {}
    val = np.where(np.isnan(zc), -np.inf, zc)
    linii = np.nanmax(np.where(np.isnan(zc), np.nan, zc), axis=1)
    bun = ~np.isnan(linii)
    if bun.sum() < 40:
        return {}
    prof = linii[bun]
    lo, hi = int(0.35 * len(prof)), int(0.85 * len(prof))
    if hi - lo < 20:
        return {}
    k = int(np.argmax(prof[lo:hi])) + lo
    n = max(len(prof) // 12, 6)
    jur = np.r_[prof[max(0, k - n):max(0, k - n // 3)], prof[k + n // 3:k + n]]
    if not len(jur):
        return {}
    nas_mm = float(prof[k] - np.median(jur))
    treapta = reg.grosime_mm * max(reg.sari, 1)
    if nas_mm <= 0 or treapta <= 0:
        return {}
    return {"nas_mm": round(nas_mm, 1),
            "trepte_nas": round(nas_mm / treapta, 1)}


@app.post("/api/jobs/{jid}/previzualizare")
async def previzualizare(jid: str, request: Request, dev: dict = Depends(dispozitiv)):
    d = await request.json()
    cerut = d.pop("detaliu", None)
    detaliu_x = None if cerut is None else float(np.clip(float(cerut), 0.0, 5.0))
    reg = _reglaje(d)
    _, z, cap, mm = _incarca(jid, dev, detaliu_x)
    solid = Solid(z, cap, mm)
    placi, info = solid.felieaza(reg)
    if not placi:
        raise HTTPException(422, "Reglajele nu produc nicio placă.")
    info |= _trepte_nas(solid, reg)

    DB.execute("UPDATE jobs SET reglaje=? WHERE id=?",
               (json.dumps(reg.__dict__ | {"detaliu": detaliu_x}), jid))
    DB.commit()

    import base64
    return {
        "info": info | {
            "arie_pe_placa_cm2": [round(p.arie_cm2, 1) for p in placi],
            "repetari": [p.repetari for p in placi],
            "bucati": [p.bucati for p in placi],
            "greutate_kg": {
                n: round(info["arie_dm2"] * 100 * reg.grosime_mm / 10 * d / 1000, 2)
                for n, d in (("oţel", 7.85), ("alamă", 8.5), ("aluminiu", 2.7))},
        },
        "asamblat": base64.b64encode(render.asamblat(placi)).decode(),
        "plane": base64.b64encode(render.plane(z, cap, reg, mm)).decode(),
    }


@app.get("/api/jobs/{jid}/dxf")
def descarca(jid: str, request: Request, coala_w: float = 1000, coala_h: float = 500,
             dev: dict = Depends(dispozitiv)):
    salvate = json.loads(r0["reglaje"] or "{}") if (r0 := DB.execute(
        "SELECT reglaje FROM jobs WHERE id=? AND device_id=?",
        (jid, dev["id"])).fetchone()) else {}
    detaliu_x = salvate.pop("detaliu", None)
    r, z, cap, mm = _incarca(jid, dev, detaliu_x)
    reg = _reglaje(salvate)
    placi, info = Solid(z, cap, mm).felieaza(reg)
    coala = dxfmod.Coala(latime_mm=coala_w, inaltime_mm=coala_h)
    fisiere = dxfmod.exporta(placi, coala)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z_:
        for nume, cont in fisiere:
            z_.writestr(nume, cont)
        z_.writestr("montaj.txt", _ghid(placi, info, reg, json.loads(r["rezumat"] or "{}")))
    buf.seek(0)
    return Response(buf.read(), media_type="application/zip",
                    headers={"Content-Disposition":
                             f'attachment; filename="faceslice-{jid}.zip"'})


def _ghid(placi, info, reg: Reglaje, rez: dict) -> str:
    l = [
        "FACESLICE — ghid de montaj",
        "=" * 46, "",
        f"Plăci de tăiat : {info['placi']} ({info['contururi']} contururi distincte)",
        f"Material       : tablă de {reg.grosime_mm} mm",
        f"Tablă necesară : {info['arie_dm2']} dm²",
        f"Teanc           : {info['inaltime_teanc_mm']} mm înălţime",
        f"Cap             : {rez.get('latime_cap_mm', '?')} x "
        f"{rez.get('inaltime_cap_mm', '?')} mm",
        "",
        "STRATURI",
        "-" * 46,
    ]
    for p in placi:
        l.append(f"  {p.indice + 1:2d}  ×{p.repetari}  {p.arie_cm2:7.1f} cm²  "
                 f"{p.bucati} bucată/bucăţi")
    l += ["", "MONTAJ", "-" * 46,
          "Se începe cu placa 1, cea mai mare, şi se urcă spre ultima.",
          "",
          "Pe fiecare placă e gravat conturul plăcii următoare. Aceea e",
          "alinierea: aşezi placa următoare exact pe linia desenată. Fără",
          "reper, un teanc de zeci de plăci iese strâmb, iar găurile cu tije",
          "n-au unde să încapă în inelele subţiri de la vârf.",
          ""]
    if reg.sari > 1:
        l += ["ATENŢIE — straturi cu goluri",
              f"Între plăci rămâne aer de {reg.grosime_mm * (reg.sari - 1)} mm.",
              "Plăcile nu se mai ating, deci teancul NU se susţine singur:",
              "are nevoie de distanţiere sau de tije prin toate plăcile.", ""]
    if reg.inclinare or reg.rotire:
        l += ["ATENŢIE — feliere înclinată",
              "Plăcile nu se mai cuibăresc una în alta, deci nu se aşază",
              "singure. Ordinea gravată şi conturul de reper devin esenţiale.", ""]
    l += [f"Kerf compensat : {reg.kerf_mm} mm (conturul e umflat cu jumătate)",
          "Verifică valoarea cu atelierul înainte de tăiere — laser, jet de",
          "apă şi freză mănâncă altfel.", ""]
    return "\n".join(l)


@app.delete("/api/jobs/{jid}")
def sterge(jid: str, dev: dict = Depends(dispozitiv)):
    _incarca(jid, dev)
    shutil.rmtree(dosar_job(jid), ignore_errors=True)
    DB.execute("DELETE FROM jobs WHERE id=? AND device_id=?", (jid, dev["id"]))
    DB.commit()
    return {"ok": True}


# ---------------------------------------------------------------- administrare

async def _corp(request: Request) -> dict:
    """Corpul JSON, sau gol. Consola trimite uneori DELETE fără corp."""
    try:
        d = await request.json()
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}

@app.get("/api/admin/devices", dependencies=[Depends(doar_admin)])
def a_dispozitive():
    # Învelişul contează: consola citeşte `.devices`, ca la toate celelalte
    # aplicaţii. Întorcând lista goală-goluţă, ea primea `undefined` şi cădea
    # cu „Cannot read properties of undefined" -- iar aplicaţia apărea ca şi
    # cum n-ar răspunde, deşi răspundea 200.
    return {"devices": [dict(r) for r in DB.execute(
        "SELECT id, label, created_at, last_seen, revoked FROM devices"
        " ORDER BY created_at DESC")]}


@app.post("/api/admin/devices/{did}/revoke", dependencies=[Depends(doar_admin)])
async def a_revoca(did: str, request: Request):
    """Comutator, nu drum fără întoarcere.

    Consola trimite starea dorită, fiindcă butonul ei se apasă în ambele
    sensuri. Ignorând-o, un telefon revocat din greşeală rămânea revocat."""
    d = await _corp(request)
    revocat = 1 if d.get("revoked", True) else 0
    DB.execute("UPDATE devices SET revoked=? WHERE id=?", (revocat, did)); DB.commit()
    return {"id": did, "revoked": bool(revocat), "success": True}


@app.post("/api/admin/devices/{did}/label", dependencies=[Depends(doar_admin)])
async def a_eticheta(did: str, request: Request):
    eticheta = (await _corp(request)).get("label") or None
    DB.execute("UPDATE devices SET label=? WHERE id=?", (eticheta, did)); DB.commit()
    return {"id": did, "label": eticheta, "success": True}


@app.delete("/api/admin/devices/{did}", dependencies=[Depends(doar_admin)])
def a_sterge_dispozitiv(did: str):
    """Şterge dispozitivul şi tot ce a lăsat în urmă.

    Lucrările sunt fişiere pe disc, nu doar rânduri: şterse doar din bază, ar
    rămâne acolo pentru totdeauna, cu fotografia omului în ele."""
    for r in DB.execute("SELECT id FROM jobs WHERE device_id=?", (did,)).fetchall():
        shutil.rmtree(dosar_job(r["id"]), ignore_errors=True)
    DB.execute("DELETE FROM jobs WHERE device_id=?", (did,))
    DB.execute("DELETE FROM devices WHERE id=?", (did,))
    DB.commit()
    return {"deleted": did, "success": True}


@app.get("/api/admin/invites", dependencies=[Depends(doar_admin)])
def a_invitatii():
    return {"invites": [dict(r) for r in DB.execute(
        "SELECT id, code, label, url, created_at, expires_at, used_at, revoked"
        " FROM invites ORDER BY created_at DESC")]}


@app.post("/api/admin/invites", dependencies=[Depends(doar_admin)])
async def a_invitatie(request: Request):
    d = await request.json()
    cod = cod_nou()
    iid = secrets.token_hex(8)
    zile = int(d.get("days", 14))
    exp = (datetime.now(timezone.utc) + timedelta(days=zile)).isoformat(timespec="seconds")
    baza = (os.environ.get("PUBLIC_BASE_URL") or "").rstrip("/")
    import hashlib
    DB.execute("INSERT INTO invites (id, code_hash, code, label, url, created_at,"
               " expires_at) VALUES (?,?,?,?,?,?,?)",
               (iid, hashlib.sha256(cod.encode()).hexdigest(), cod,
                d.get("label"), f"{baza}/?code={cod}" if baza else None, acum(), exp))
    DB.commit()
    return {"id": iid, "code": cod, "url": f"{baza}/?code={cod}" if baza else None,
            "expires_at": exp, "expires_in_days": zile}


@app.post("/api/admin/invites/{iid}/revoke", dependencies=[Depends(doar_admin)])
def a_revoca_inv(iid: str):
    DB.execute("UPDATE invites SET revoked=1 WHERE id=?", (iid,)); DB.commit()
    return {"ok": True}


app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
