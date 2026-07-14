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

# Senales POSITIVAS de generacion por IA (no solo "c2pa.created" generico).
# c2pa.created esta en CUALQUIER manifest (sea IA o humano) -> NO basta.
# Se requiere una senal de herramienta generativa conocida o accion generativa.
SYNTHETIC_SIGNALS = (
    "generatedby",          # schema.org generatedBy con nombre de herramienta
    "softwareagent",        # c2pa.created con softwareAgent (herramienta, no humano)
    "trained_algorithmic",  # accion/assertion de medio algoritmico
    "c2pa.generated",       # accion generativa explicita
    "generative",           # softwareAgent generativo
)
# Senales POSITIVAS de origen humano / captura real.
HUMAN_SIGNALS = (
    "c2pa.digital_capture", # accion de captura (camara/microfono)
    "c2pa.captured",        # captura explicita
    "device",               # dispositivo de captura en claims
    "c2pa.edited",          # edicion humana
)


@dataclass
class Verdict:
    verdict: str  # trusted | contradiction | partial | unverifiable
    explanation: str


def _origin_claim(c2pa: C2paResult) -> Optional[str]:
    """Devuelve 'synthetic' | 'human' | 'indeterminate' | None (sin C2PA).

    REGLA DE SEGURIDAD (corregido tras auditoria de Claude):
    El default sin evidencia POSITIVA de origen es 'indeterminate' (-> partial),
    NUNCA 'synthetic'. Marcar 'synthetic' (que habilita el veredicto 'trusted',
    la afirmacion mas fuerte) exige senal positiva explicita de generacion por IA.
    'c2pa.created' solo NO basta: esta en practicamente cualquier manifest, sea
    IA o humano, y usarlo como prueba de sintetico invertia la logica del producto
    (trusted demasiado facil, contradiction casi inalcanzable).
    """
    if not c2pa.present:
        return None
    st = (c2pa.source_type or "").lower() if c2pa.source_type else ""
    if st in SYNTHETIC_TYPES:
        return "synthetic"
    if st in HUMAN_TYPES:
        return "human"
    # claims legibles (acciones/softwareAgent/generatedBy)
    text = " ".join(c2pa.claims).lower()
    has_synth = any(s in text for s in SYNTHETIC_SIGNALS)
    has_human = any(s in text for s in HUMAN_SIGNALS)
    # Solo senal IA positiva -> synthetic. Solo senal humana -> human.
    # Ambas, ninguna o ambiguo -> indeterminate (default seguro).
    if has_synth and not has_human:
        return "synthetic"
    if has_human and not has_synth:
        return "human"
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
