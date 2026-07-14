"""AudioTrust - CLI.

Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
SPDX-License-Identifier: AGPL-3.0-or-later

Uso:
  audiotrust verify <archivo_audio> [--json] [--explain] [--wm-threshold FLOAT]
"""
from __future__ import annotations

import argparse
import json
import sys

from .c2pa_layer import read_c2pa
from .watermark_layer import detect_prob
from .reconcile import reconcile, WM_THRESHOLD


def _build_result(path: str, wm_threshold: float, explain: bool) -> dict:
    c2pa = read_c2pa(path)
    try:
        wm = detect_prob(path)
    except Exception as exc:
        wm = None
        wm_error = str(exc)
    else:
        wm_error = None

    if wm is None:
        # No se pudo leer audio/watermark -> no se puede reconciliar
        verdict = "unverifiable"
        explanation = f"No se pudo analizar el audio: {wm_error}"
        return {
            "file": path,
            "verdict": verdict,
            "c2pa": {"present": c2pa.present, "source_type": c2pa.source_type, "claims": c2pa.claims},
            "watermark": {"present": False, "detect_prob": None, "error": wm_error},
            "explanation": explanation,
        }

    v = reconcile(c2pa, wm, wm_threshold)
    return {
        "file": path,
        "verdict": v.verdict,
        "c2pa": {"present": c2pa.present, "source_type": c2pa.source_type, "claims": c2pa.claims},
        "watermark": {"present": True, "detect_prob": round(wm, 6)},
        "explanation": v.explanation if (explain or v.verdict in ("trusted", "contradiction")) else "",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="audiotrust", description="Verificador de reconciliacion de confianza para audio sintetico (C2PA + watermark AudioSeal).")
    parser.add_argument("file", help="Archivo de audio a verificar (WAV/MP3/FLAC).")
    parser.add_argument("--json", action="store_true", help="Salida JSON.")
    parser.add_argument("--explain", action="store_true", help="Explicacion detallada del veredicto.")
    parser.add_argument("--wm-threshold", type=float, default=WM_THRESHOLD, help=f"Umbral de detect_prob (defecto {WM_THRESHOLD}).")
    args = parser.parse_args(argv)

    result = _build_result(args.file, args.wm_threshold, args.explain)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Archivo : {result['file']}")
        print(f"Veredicto: {result['verdict']}")
        print(f"C2PA    : presente={result['c2pa']['present']} source_type={result['c2pa']['source_type']}")
        if result['c2pa']['claims']:
            print(f"  claims : {', '.join(result['c2pa']['claims'])}")
        wm = result['watermark']
        if wm['present']:
            print(f"Watermark: detect_prob={wm['detect_prob']}")
        else:
            print(f"Watermark: NO disponible ({wm.get('error','')})")
        if result['explanation']:
            print(f"Explicacion: {result['explanation']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
