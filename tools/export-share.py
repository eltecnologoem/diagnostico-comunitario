#!/usr/bin/env python3
"""Exportador local allowlist; Python 3 stdlib, sin conexiones salientes."""
import argparse
import datetime
import json
import math
import secrets
import os
import re
import sys
from pathlib import Path

MAX_BYTES = 2 * 1024 * 1024
UTC_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
ALLOWED_TOP = frozenset(("schema_version", "report_type", "run_id", "collected_at", "source", "metrics", "checks", "findings", "privacy"))
ALLOWED_FINDINGS = {"disk_root_high": ("warning", "disk.root.used_percent", "percent", 90)}


def reject_duplicate_pairs(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError(f"Campo JSON repetido: {k}")
        result[k] = v
    return result


def reject_nonfinite(token):
    raise ValueError(f"Número inválido: {token}")


def strict_number(value, name, *, maximum=None, integral=False):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Tipo incorrecto en {name}")
    if integral and (not isinstance(value, int) or value < 0):
        raise ValueError(f"Entero inválido en {name}")
    if (isinstance(value, float) and not math.isfinite(value)) or value < 0 or (maximum is not None and value > maximum):
        raise ValueError(f"Valor fuera de rango en {name}")
    return value


def checked_boolean(value, name):
    if value is not None and not isinstance(value, bool):
        raise ValueError(f"Booleano inválido en {name}")
    return value


def build_share(original):
    if not isinstance(original, dict) or set(original) != ALLOWED_TOP:
        raise ValueError("Esquema privado desconocido o campos adicionales")
    if original["schema_version"] != "1.0" or original["report_type"] != "private":
        raise ValueError("Versión o tipo de diagnóstico no compatible")
    private = original["privacy"]
    if not isinstance(private, dict) or set(private) != {
        "contains_operational_identifiers", "contains_raw_logs", "contains_environment_variables", "sensitive_sharing_enabled"
    }:
        raise ValueError("Privacidad inválida")
    if private["sensitive_sharing_enabled"] is not False or private["contains_raw_logs"] is not False or private["contains_environment_variables"] is not False:
        raise ValueError("El informe contiene o permite datos sensibles; exportación compartible denegada")
    timestamp = original["collected_at"]
    if not isinstance(timestamp, str) or not UTC_PATTERN.fullmatch(timestamp):
        raise ValueError("Fecha UTC inválida")
    try:
        datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ValueError("Fecha UTC imposible") from exc
    metrics = original["metrics"]
    if not isinstance(metrics, dict) or set(metrics) != {"system", "memory", "disk_root", "database", "processes"}:
        raise ValueError("Métricas privadas inválidas")
    system, memory, disk, db = (metrics[k] for k in ("system", "memory", "disk_root", "database"))
    expected_keys = {
        "system": (system, {"uptime_seconds", "cpu_cores", "load_1m"}),
        "memory": (memory, {"total_bytes", "available_bytes", "swap_total_bytes", "swap_free_bytes"}),
        "disk_root": (disk, {"total_bytes", "used_bytes", "available_bytes", "used_percent"}),
        "database": (db, {"mysql_client_available", "mariadb_client_available", "mysql_process_count", "tcp_3306_listening", "embedded_mysql_present"}),
        "processes": (metrics["processes"], {"sshd_process_count"}),
    }
    for name, (value, keys) in expected_keys.items():
        if not isinstance(value, dict) or set(value) != keys:
            raise ValueError(f"Campos no esperados en {name}")
    summary = {
        "uptime_seconds": strict_number(system["uptime_seconds"], "uptime_seconds", integral=True),
        "cpu_cores": strict_number(system["cpu_cores"], "cpu_cores", maximum=4096, integral=True),
        "load_1m": strict_number(system["load_1m"], "load_1m", maximum=100000),
        "memory_total_bytes": strict_number(memory["total_bytes"], "memory_total_bytes", integral=True),
        "memory_available_bytes": strict_number(memory["available_bytes"], "memory_available_bytes", integral=True),
        "disk_root_used_percent": strict_number(disk["used_percent"], "disk_root_used_percent", maximum=100, integral=True),
        "mysql_process_count": strict_number(db["mysql_process_count"], "mysql_process_count", integral=True),
        "tcp_3306_listening": checked_boolean(db["tcp_3306_listening"], "tcp_3306_listening"),
    }
    # Nada del objeto 'source' se incorpora al JSON compartible; ni siquiera un identificador estable.
    sanitized_findings = []
    findings = original["findings"]
    if not isinstance(findings, list) or len(findings) > 100:
        raise ValueError("Hallazgos inválidos")
    for finding in findings:
        if not isinstance(finding, dict) or set(finding) != {"code", "severity", "metric", "value", "unit", "threshold"}:
            raise ValueError("Hallazgo no compatible con política")
        code = finding["code"]
        if not isinstance(code, str) or code not in ALLOWED_FINDINGS:
            raise ValueError("Código de hallazgo no permitido")
        sev, metric, unit, threshold = ALLOWED_FINDINGS[code]
        if (finding["severity"], finding["metric"], finding["unit"], finding["threshold"]) != (sev, metric, unit, threshold):
            raise ValueError("Hallazgo alterado")
        value = strict_number(finding["value"], "finding.value", maximum=100, integral=True)
        if value is None:
            raise ValueError("Hallazgo sin valor")
        sanitized_findings.append({"code": code, "severity": sev, "metric": metric, "value": value, "unit": unit, "threshold": threshold})

    return {
        "schema_version": "1.0", "report_type": "share", "collected_at": timestamp,
        "summary": summary, "findings": sanitized_findings,
        "omissions": {"hostnames": True, "addresses": True, "raw_logs": True,
                      "paths": True, "environment": True, "stable_identifiers": True},
    }


def main():
    parser = argparse.ArgumentParser(description="Crea un JSON compartible sin datos de identidad ni evidencia cruda")
    parser.add_argument("private_json", type=Path)
    parser.add_argument("--output", type=Path, help="Ruta nueva del reporte compartible")
    args = parser.parse_args()
    try:
        if args.private_json.stat().st_size > MAX_BYTES:
            raise ValueError("Informe privado demasiado grande")
        with args.private_json.open("r", encoding="utf-8") as handle:
            original = json.load(handle, object_pairs_hook=reject_duplicate_pairs, parse_constant=reject_nonfinite)
        share = build_share(original)
        target = args.output or args.private_json.with_name("diagnostico-compartible-" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4) + ".json")
        if target.resolve() == args.private_json.resolve():
            raise ValueError("El destino no puede ser igual al archivo privado")
        os.umask(0o077)
        with target.open("x", encoding="utf-8") as handle:
            json.dump(share, handle, ensure_ascii=True, indent=2, allow_nan=False)
            handle.write("\n")
        print(f"Reporte compartible: {target}")
    except (OSError, ValueError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
