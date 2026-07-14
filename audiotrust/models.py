"""AudioTrust - cacheo local de pesos de AudioSeal.

Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
SPDX-License-Identifier: AGPL-3.0-or-later

Descarga los pesos de facebook/audioseal (repo PUBLICO, sin token HF) la primera
vez y los cachea localmente. En ejecucion NO hay llamadas de red: se usa la copia
local. Ver KNOWN_ISSUES.md KI-3 (hallazgos del spike).
"""
from __future__ import annotations

import os

MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
GENERATOR_PTH = os.path.join(MODELS_DIR, "generator_base.pth")
DETECTOR_PTH = os.path.join(MODELS_DIR, "detector_base.pth")
CODEC_PTH = os.path.join(MODELS_DIR, "audioseal_encodec_32khz.th")

REPO_ID = "facebook/audioseal"
FILES = {
    GENERATOR_PTH: "generator_base.pth",
    DETECTOR_PTH: "detector_base.pth",
    CODEC_PTH: "audioseal_encodec_32khz.th",
}


def ensure_models() -> None:
    """Descarga los pesos si no estan cacheados localmente.

    Lanza RuntimeError si la descarga falla (p.ej. sin red). En ese caso el usuario
    debe ubicar los pesos manualmente en models/.
    """
    missing = [dst for dst in FILES if not os.path.exists(dst)]
    if not missing:
        return
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "huggingface_hub no instalado y faltan pesos en models/. Instala o "
            "ubica los pesos manualmente."
        ) from exc
    os.makedirs(MODELS_DIR, exist_ok=True)
    for dst, fname in FILES.items():
        if not os.path.exists(dst):
            hf_hub_download(repo_id=REPO_ID, filename=fname, local_dir=MODELS_DIR)


def paths() -> tuple[str, str, str]:
    """Devuelve (generator_pth, detector_pth, codec_pth) cacheados.

    Llama ensure_models() primero si hiciera falta; pero en produccion los pesos
    ya deben estar presentes (descarga hecha en instalacion/setup).
    """
    ensure_models()
    return GENERATOR_PTH, DETECTOR_PTH, CODEC_PTH
