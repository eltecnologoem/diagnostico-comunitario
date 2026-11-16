#!/usr/bin/env python3
"""Envia solamente el JSON compartible por SMTP, previa opcion --email en el colector.

No lee .env mediante shell ni almacena adjuntos privados en disco.
Python 3 stdlib; STARTTLS estricto o SMTP sobre TLS, sin fallback a texto claro.
"""
import argparse
import email.utils
import importlib.util
import json
import os
import re
import smtplib
import stat
import sys
import ssl
from email.message import EmailMessage
from pathlib import Path

KEYS = {"SMTP_HOST", "SMTP_PORT", "SMTP_SECURITY", "SMTP_USER",
        "SMTP_PASSWORD", "MAIL_FROM", "MAIL_TO"}
REQUIRED = KEYS
VALUE_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,253}$")
EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_\x60{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}$")
MAX_PRIVATE_BYTES = 2 * 1024 * 1024


def read_env(path):
    # O_NOFOLLOW evita enlaces simbólicos sobre el archivo de configuración.
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise ValueError("El .env debe ser un archivo normal")
        if stat.S_IMODE(st.st_mode) & 0o077:
            raise ValueError("El .env contiene credenciales: aplicar chmod 600")
        if st.st_size > 16384:
            raise ValueError("El .env es demasiado grande")
        with os.fdopen(fd, "r", encoding="utf-8") as f:
            fd = -1
            raw = f.read(16385)
    finally:
        if fd >= 0:
            os.close(fd)
    if len(raw) > 16384:
        raise ValueError("El .env es demasiado grande")
    data = {}
    for lineno, line in enumerate(raw.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Formato .env inválido en línea {lineno}")
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in KEYS or key in data:
            raise ValueError(f"Clave desconocida o duplicada en .env (línea {lineno})")
        value = value.strip()
        if len(value) > 2048 or "\x00" in value:
            raise ValueError(f"Valor .env inválido en línea {lineno}")
        # No interpretar escapes, variables, comandos ni sintaxis de shell.
        # Comillas exteriores opcionales, literales dentro del valor.
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        data[key] = value
    if set(data) != REQUIRED:
        raise ValueError("Faltan o sobran claves de configuración SMTP")
    return data


def validated_address(s):
    if not s or len(s) > 254 or not EMAIL_RE.fullmatch(s) or ".." in s:
        raise ValueError("Dirección de correo inválida")
    return s


def validated_config(data):
    host = data["SMTP_HOST"]
    if not VALUE_RE.fullmatch(host) or host.startswith("-"):
        raise ValueError("SMTP_HOST inválido")
    try:
        port = int(data["SMTP_PORT"])
    except (TypeError, ValueError):
        raise ValueError("SMTP_PORT inválido") from None
    if not 1 <= port <= 65535:
        raise ValueError("SMTP_PORT fuera de rango")
    mode = data["SMTP_SECURITY"].lower()
    if mode not in ("ssl", "starttls"):
        raise ValueError("SMTP_SECURITY debe ser ssl o starttls")
    if not data["SMTP_USER"] or not data["SMTP_PASSWORD"]:
        raise ValueError("SMTP_USER y SMTP_PASSWORD son obligatorios")
    sender = validated_address(data["MAIL_FROM"])
    recipient = validated_address(data["MAIL_TO"])
    if any("\r" in x or "\n" in x for x in data.values()):
        raise ValueError("Configuración SMTP contiene caracteres no permitidos")
    return host, port, mode, sender, recipient


def build_message(report_path, sender, recipient):
    spec = importlib.util.spec_from_file_location("serverdiag_export_share",
        Path(__file__).with_name("export-share.py"))
    if spec is None or spec.loader is None:
        raise ValueError("No se encontró export-share.py")
    exporter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(exporter)
    p = Path(report_path)
    st = p.stat()
    if not p.is_file() or st.st_size > MAX_PRIVATE_BYTES:
        raise ValueError("El diagnóstico local no es un archivo válido")
    with p.open("r", encoding="utf-8") as f:
        original = json.load(f, object_pairs_hook=exporter.reject_duplicate_pairs,
                             parse_constant=exporter.reject_nonfinite)
    share = exporter.build_share(original)
    payload = json.dumps(share, ensure_ascii=True, indent=2, allow_nan=False).encode("utf-8") + b"\n"
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = "Diagnostico Comunitario - reporte compartible"
    msg.set_content("Se adjunta exclusivamente el JSON compartible, sin identificadores operativos. "
                    "El informe privado permanece almacenado localmente.\n")
    msg.add_attachment(payload, maintype="application", subtype="json",
                       filename="diagnostico-compartible.json")
    return msg


def send(config_path, report_path):
    data = read_env(config_path)
    host, port, mode, sender, recipient = validated_config(data)
    msg = build_message(report_path, sender, recipient)
    context = ssl.create_default_context()
    if mode == "ssl":
        with smtplib.SMTP_SSL(host=host, port=port, timeout=20, context=context) as smtp:
            smtp.login(data["SMTP_USER"], data["SMTP_PASSWORD"])
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host=host, port=port, timeout=20) as smtp:
            smtp.ehlo()
            if not smtp.has_extn("starttls"):
                raise ValueError("El servidor SMTP no ofrece STARTTLS: envío cancelado")
            smtp.starttls(context=context)
            smtp.ehlo()
            smtp.login(data["SMTP_USER"], data["SMTP_PASSWORD"])
            smtp.send_message(msg)
    print("Correo enviado con reporte compartible (el original no salió del servidor).")


def main():
    parser = argparse.ArgumentParser(description="Envía únicamente informe sanitizado por SMTP opt-in")
    parser.add_argument("--env", default=".env", help="Archivo .env privado (chmod 600)")
    parser.add_argument("private_json", help="JSON privado que permanece en disco")
    args = parser.parse_args()
    try:
        send(args.env, args.private_json)
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError, smtplib.SMTPException) as exc:
        # No mostrar str(exc): algunas librerías SMTP pueden incluir información del servidor.
        print("No se pudo enviar el correo. Revisa conexión/TLS/configuración; "
              "el reporte privado permanece local.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
