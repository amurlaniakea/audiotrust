# SPEC — AudioTrust

**Proyecto:** AudioTrust
**Autor:** Pedro Sordo Martínez (amurlaniakea@gmail.com)
**Licencia:** AGPL-3.0-or-later
**Fecha:** 2026-07-14
**Estado:** SPEC (fase 2 de SDD). Basada en CONSTITUCION.md + KNOWN_ISSUES.md (spike cerrado).
**Gobernanza:** Hermes implementa → Claude re-verifica en clone limpio → Sil aprueba merge.
  Entrega en rama dedicada (nunca main).

---

## 1. Visión (una frase)

Un verificador local que lee las DOS marcas de confianza de un audio generado por IA
(C2PA + watermark AudioSeal) y emite un veredicto auditable de si coinciden, se
contradicen o faltan.

## 2. Requisitos funcionales

| ID | Requisito | Evidencia del spike |
|----|-----------|---------------------|
| FR-1 | Leer el manifest C2PA de un archivo de audio y extraer su contenido (source_type, acciones, claims). | Reader opera sobre WAV; `ManifestNotFound` en ausencia (KI-2). |
| FR-2 | Detectar la presencia de watermark AudioSeal y devolver `detect_prob` (P(audio watermarked)). | 3 corridas: WATERMARKED>=0.85 / CLEAN<=0.005 (KI-3). |
| FR-3 | Reconciliar ambas capas y emitir veredicto: `trusted` / `contradiction` / `partial` / `unverifiable`. | Lógica de reconciliación (ver §4). |
| FR-4 | CLI `audiotrust verify <file> [--json]` con salida legible y JSON. | Nuevo. |
| FR-5 | Devolver `unverifiable` (no crashear) si no se puede leer ninguna capa. | Reader lanza excepción controlada → mapear a `unverifiable`. |
| FR-6 | Modo `—explain` que detalla qué se vio de cada capa (trazabilidad). | Nuevo (sin usar el mensaje de AudioSeal). |

## 3. Requisitos no funcionales

- **Local-only:** sin llamadas de red en tiempo de ejecución (los pesos se cachean localmente).
- **Read-only:** el audio de entrada no se modifica.
- **Sin reentrenar:** solo pesos públicos + criptografía.
- **Sin depender del mensaje de AudioSeal:** el veredicto usa SOLO `detect_prob` (regla KI-3).
- **Reproducible:** tests con fixtures versionados por hash.

## 4. Lógica de reconciliación (el núcleo)

Entradas:
- `c2pa` ∈ {ausente, leído} con `source_type` y claims.
- `watermark_prob` ∈ [0,1]; umbral `WM_THRESHOLD` (p.ej. 0.5, derivado de los datos:
  clean<=0.005, watermarked>=0.85 → margen enorme; 0.5 es conservador).

Veredicto:
```
si c2pa == ausente y watermark_prob < WM_THRESHOLD:  unverifiable
si c2pa == ausente y watermark_prob >= WM_THRESHOLD:  partial   (solo watermark)
si c2pa == leído  y watermark_prob < WM_THRESHOLD:   partial   (solo C2PA)
si c2pa == leído  y watermark_prob >= WM_THRESHOLD:
    si los claims de C2PA son coherentes con origen sintético (source_type
       TRAINED_ALGORITHMIC_MEDIA / c2pa.created por IA):  trusted
    si C2PA afirma origen HUMANO pero hay watermark fuerte:  contradiction   (Integrity Clash)
```

La detección de origen (sintético/humano) se hace por los **claims de acciones del
manifest** (`c2pa.actions` con `action: "c2pa.created"` + `softwareAgent`/`generatedBy`),
NO por el campo `source_type`. Motivo (KI-5, verificado con firmas reales de c2patool
0.9.12 y fixtures de c2pa-rs): las firmas reales C2PA **no incluyen `source_type`
explícito por defecto**; el string `c2pa.trained_algorithmic_media` del README de C2PA
casi nunca aparece en manifests reales. `reconcile.py` se apoya en los claims de
acciones, que sí están presentes. Queda PROHIBIDO reintroducir dependencia de
`source_type` como vía primaria.

## 5. Interfaz (CLI)

```
audiotrust verify <archivo_audio> [--json] [--explain] [--wm-threshold FLOAT]
```
Salida JSON:
```json
{
  "file": "<ruta>",
  "verdict": "trusted|contradiction|partial|unverifiable",
  "c2pa": {"present": true, "source_type": "c2pa.trained_algorithmic_media", "claims": [...]},
  "watermark": {"present": true, "detect_prob": 0.92},
  "explanation": "..."
}
```

## 6. Dependencias (fijadas, del spike)

- `c2pa-python==0.36.0` — lectura/manifest.
- `audioseal==0.2.0` — watermark.
- `torch` — build CUDA `cu130` vía PyPI (índice CPU de PyTorch no alcanzable aquí).
  **REQUIERE** `TORCH_COMPILE_DISABLE=1 TORCHDYNAMO_DISABLE=1` en ejecución (si falta,
  crash en dynamo). Decisión A adoptada; B en paralelo (ver Constitución §6 / KI-4).
- `huggingface_hub` — descarga de pesos (`facebook/audioseal`, repo público).
- `soundfile`, `numpy` — I/O.
- Pesos cacheados localmente: `generator_base.pth`, `detector_base.pth`,
  `audioseal_encodec_32khz.th`.

## 7. Estructura del repo (propuesta)

```
audiotrust/
  audiotrust/
    __init__.py
    cli.py            # argparse: verify
    c2pa_layer.py     # lectura manifest (Reader, manejo ManifestNotFound)
    watermark_layer.py# carga AudioSeal, detect_prob (SOLO detect_prob)
    reconcile.py      # lógica FR-3 / §4
    models.py         # cacheo de pesos (hf_hub_download al iniciar)
  tests/
    fixtures/         # audios firmados reales (Opción C, KI-1) versionados por hash
    test_verify.py    # trusted / partial / unverifiable / contradiction
  CONSTITUCION.md
  KNOWN_ISSUES.md
  SPEC.md
  README.md          # formato profesional, licencia AGPL-3.0-or-later
  pyproject.toml
  requirements.txt
```

## 8. Fixtures (KI-1, Opción C)

Los tests de reconciliación usan audios YA FIRMADOS por herramientas reales del
ecosistema C2PA (no firmamos nosotros: c2pa-python 0.36.0 tiene el bug de certificado
KI-1). Se versionan por hash SHA256 en `tests/fixtures/` (el contenido no se edita).
Falta: obtener/ubicar estos fixtures reales (tarea de implementación).

## 9. Criterios de aceptación (DoD)

1. `audiotrust verify <wav_con_watermark_y_c2pa>` → `trusted` (fixture real).
2. `audiotrust verify <wav_con_watermark_sin_c2pa>` → `partial`.
3. `audiotrust verify <wav_sin_nada>` → `unverifiable` (no crashea).
4. `audiotrust verify <wav_con_contradiccion>` → `contradiction` (fixture con C2PA
   humano + watermark fuerte; requiere fixture real o mock de manifest).
5. Tests reproducibles en CI (clone limpio) con los 3 veredictos.
6. README con licencia AGPL-3.0-or-later, sin banners ni URLs internas.
7. `TORCH_COMPILE_DISABLE=1` documentado en README y en el wrapper de ejecución.

## 10. Riesgos / deuda conocida

- KI-1: firma C2PA desde cero no resuelta → fixtures externos (Opción C).
- KI-3: mensaje de AudioSeal inconsistente → NO usarlo (solo detect_prob).
- Índice CPU PyTorch caído → torch CUDA + env var requerida (Opción A; B paralelo).
- `contradiction` depende de poder leer un claim de origen en C2PA que contradiga el
  watermark; si los fixtures reales no traen ese claim, el caso contradiction puede
  quedar como test con manifest mock (no bloquea los otros 3 veredictos).

## 11. Fuera de alcance (esta fase)

- Generar audio sintético propio.
- Firmar manifests C2PA en producción.
- Detector de deepfake por clasificador.
- Recuperar/usar el mensaje de AudioSeal.
