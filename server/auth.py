"""Poarta: invitaţii pentru dispozitive, jeton separat pentru administrare."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets

from fastapi import Header, HTTPException, Request

from db import DB, acum


def _hash(s: str) -> str:
    return hashlib.sha256(s.strip().encode()).hexdigest()


def cod_nou() -> str:
    a = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"      # fără caractere confundabile
    return "-".join("".join(secrets.choice(a) for _ in range(4)) for _ in range(3))


def revendica(cod: str, eticheta: str | None) -> tuple[str, str]:
    r = DB.execute("SELECT * FROM invites WHERE code_hash=? AND revoked=0",
                   (_hash(cod),)).fetchone()
    if not r or r["used_at"]:
        raise HTTPException(403, "Cod nevalabil sau deja folosit.")
    if r["expires_at"] and r["expires_at"] < acum():
        raise HTTPException(403, "Codul a expirat.")
    dev = secrets.token_hex(8)
    jeton = secrets.token_urlsafe(32)
    DB.execute("INSERT INTO devices (id, token_hash, label, created_at) VALUES (?,?,?,?)",
               (dev, _hash(jeton), eticheta or r["label"] or "Dispozitiv", acum()))
    DB.execute("UPDATE invites SET used_at=?, device_id=? WHERE id=?",
               (acum(), dev, r["id"]))
    DB.commit()
    return dev, jeton


def dispozitiv(request: Request) -> dict:
    """Jetonul vine din antet sau din cookie -- a doua cale ca descărcarea unui
    DXF să meargă printr-un simplu link, fără JavaScript care să pună antete."""
    jeton = (request.headers.get("x-device-token")
             or request.cookies.get("faceslice_token") or "").strip()
    if not jeton:
        raise HTTPException(401, "Dispozitiv neînregistrat.")
    r = DB.execute("SELECT * FROM devices WHERE token_hash=? AND revoked=0",
                   (_hash(jeton),)).fetchone()
    if not r:
        raise HTTPException(401, "Dispozitiv neînregistrat.")
    DB.execute("UPDATE devices SET last_seen=? WHERE id=?", (acum(), r["id"]))
    DB.commit()
    return dict(r)


def doar_admin(x_admin_token: str = Header(default="")) -> None:
    """Închis dacă nu e configurat: un jeton lipsă înseamnă nu, nu oricine."""
    asteptat = (os.environ.get("ADMIN_TOKEN") or "").strip()
    if not asteptat or not hmac.compare_digest(x_admin_token.strip(), asteptat):
        raise HTTPException(403, "Interzis.")
