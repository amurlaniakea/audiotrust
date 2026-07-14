"""AudioTrust - capa C2PA (lectura de manifest).

Lee el manifest C2PA embebido en un archivo de audio y extrae el source_type y los
claims de origen. NO firma (ver KNOWN_ISSUES.md KI-1: firma resuelta con c2patool
en la generacion de fixtures). Usa c2pa-python 0.36.0 (Reader).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import c2pa


@dataclass
class C2paResult:
    present: bool
    source_type: Optional[str] = None
    claims: list[str] = None  # descripciones legibles de acciones/assertions
    raw: Optional[str] = None  # JSON del manifest (para --explain)

    def __post_init__(self):
        if self.claims is None:
            self.claims = []


def read_c2pa(path: str) -> C2paResult:
    """Lee el manifest C2PA de `path`.

    Devuelve present=False si no hay manifest (ManifestNotFound) u otro error de
    lectura. NUNCA lanza: un archivo sin manifest es un caso valido (partial/unverifiable).
    """
    try:
        reader = c2pa.Reader(path)
    except c2pa.C2paError:
        # ManifestNotFound u otro error de parseo -> no hay manifest leible
        return C2paResult(present=False)
    except Exception:
        return C2paResult(present=False)

    try:
        manifest_json = reader.json()
    except Exception:
        return C2paResult(present=False)

    source_type = _extract_source_type(manifest_json)
    claims = _extract_claims(manifest_json)
    return C2paResult(present=True, source_type=source_type, claims=claims, raw=manifest_json)


def _extract_source_type(manifest_json: str) -> Optional[str]:
    """Extrae c2pa.source_type del manifest (si esta presente)."""
    try:
        import json
        data = json.loads(manifest_json)
    except Exception:
        return None
    # El manifest puede tener assertions de tipo source_type embebidas.
    # Buscamos de forma defensiva en las estructuras conocidas.
    candidates = []

    def walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if "source_type" in str(k).lower():
                    candidates.append(v)
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)
    for c in candidates:
        if isinstance(c, str):
            return c
        if isinstance(c, dict) and "type" in c:
            return c["type"]
    return None


def _extract_claims(manifest_json: str) -> list[str]:
    """Extrae descripciones legibles de acciones/assertions para --explain."""
    try:
        import json
        data = json.loads(manifest_json)
    except Exception:
        return []
    claims: list[str] = []

    def walk(obj):
        if isinstance(obj, dict):
            # Acciones c2pa.actions
            if "actions" in obj and isinstance(obj["actions"], list):
                for a in obj["actions"]:
                    if isinstance(a, dict):
                        act = a.get("action")
                        agent = a.get("softwareAgent") or a.get("actor")
                        if act:
                            claims.append(f"action={act}" + (f" by {agent}" if agent else ""))
            # generatedBy (schema.org)
            gen = obj.get("generatedBy") or obj.get("generator")
            if isinstance(gen, dict) and gen.get("name"):
                claims.append(f"generatedBy={gen.get('name')}")
            walk({k: v for k, v in obj.items() if k not in ("actions",)})
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)
    # dedupe preservando orden
    seen = set()
    out = []
    for c in claims:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out
