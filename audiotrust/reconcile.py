"""AudioTrust - logica de reconciliacion (tabla T1 de Tasks.md).

Veredicto determinista basado en source_type C2PA + detect_prob de watermark.
NO se anaden casos fuera de la tabla T1. El mensaje de AudioSeal NO interviene.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .c2pa_layer import C2paResult

WM_THRESHOLD = 0.5

# Source types que declaran origen SINTETICO (generado por IA)
SYNTHETIC_TYPES = {
    "c2pa.trained_algorithmic_media",
    "c2pa.data_driven_media",
    "c2pa.algorithmic_media",
}
# Source types que declaran origen HUMANO / captura real
HUMAN_TYPES = {
    "c2pa.digital_capture",
    "c2pa.human_edits",
    "c2pa.digital_creation",
}


@dataclass
class Verdict:
    verdict: str  # trusted | contradiction | partial | unverifiable
    explanation: str


def _origin_claim(c2pa: C2paResult) -> Optional[str]:
    """Devuelve 'synthetic' | 'human' | 'indeterminate' | None (sin C2PA)."""
    if not c2pa.present:
        return None
    st = (c2pa.source_type or "").lower() if c2pa.source_type else ""
    if st in SYNTHETIC_TYPES:
        return "synthetic"
    if st in HUMAN_TYPES:
        return "human"
    # claims legibles (acciones/softwareAgent/generatedBy)
    text = " ".join(c2pa.claims).lower()
    if "generatedby" in text or "softwareagent" in text or "c2pa.created" in text:
        # accion de creacion por software -> sintetico
        if any(k in text for k in ("human", "camera", "capture")):
            return "human"
        return "synthetic"
    return "indeterminate"


def reconcile(c2pa: C2paResult, detect_prob: float, wm_threshold: float = WM_THRESHOLD) -> Verdict:
    """Implementa literalmente la tabla T1 de Tasks.md.

    Tabla:
    | source_type              | wm>=thr | veredicto     |
    | ausente                  | no      | unverifiable  |
    | ausente                  | si      | partial       |
    | synthetic                | no      | partial       |
    | synthetic                | si      | trusted       |
    | human                    | no      | partial       |
    | human                    | si      | contradiction |
    | indeterminate (C2PA leido, origen nc) | * | partial  (no inventar)
    """
    has_wm = detect_prob >= wm_threshold
    origin = _origin_claim(c2pa)

    if origin is None:
        if has_wm:
            return Verdict("partial", "Solo watermark detectado; sin manifest C2PA.")
        return Verdict("unverifiable", "Sin manifest C2PA ni watermark detectado.")

    if origin == "synthetic":
        if has_wm:
            return Verdict("trusted", "C2PA declara origen sintetico y hay watermark fuerte: coherentes.")
        return Verdict("partial", "C2PA declara origen sintetico pero sin watermark detectado.")

    if origin == "human":
        if has_wm:
            return Verdict("contradiction", "C2PA declara origen humano PERO hay watermark fuerte (Integrity Clash).")
        return Verdict("partial", "C2PA declara origen humano y sin watermark detectado.")

    # indeterminate: C2PA leido pero origen no determinable -> no inventar
    if has_wm:
        return Verdict("partial", "C2PA leido (origen indeteminado) con watermark detectado.")
    return Verdict("partial", "C2PA leido (origen indeteminado) sin watermark detectado.")
