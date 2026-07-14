# Tasks — AudioTrust (fase 4 SDD)

**Fecha:** 2026-07-14
**Base:** SPEC.md + CONSTITUCION.md + KNOWN_ISSUES.md (spike cerrado, evidencia cruda)
**Gobernanza:** Hermes implementa en rama dedicada → Claude re-verifica en clone limpio →
Sil aprueba merge. NUNCA en main.

---

## T1 — Tabla exacta de "coherencia" para veredictos trusted/contradiction (resuelve duda de Sil)

La SPEC §4 dejó "coherencia" abierta. Se fija AQUÍ, antes de implementar, para no
dejarlo a criterio de Hermes en tiempo de código. Regla determinista:

| source_type C2PA leído            | watermark_prob | Veredicto  | Razón |
|-----------------------------------|----------------|------------|--------|
| ausente                            | < WM_THRESHOLD | unverifiable | no hay ninguna capa |
| ausente                            | >= WM_THRESHOLD| partial    | solo watermark |
| TRAINED_ALGORITHMIC_MEDIA / c2pa.created por IA / claim "generado por IA" | < WM_THRESHOLD | partial | solo C2PA (sintético declarado, sin watermark) |
| TRAINED_ALGORITHMIC_MEDIA / c2pa.created por IA / claim "generado por IA" | >= WM_THRESHOLD | **trusted** | C2PA dice sintético Y hay watermark → coherentes |
| DIGITAL_CAPTURE / HUMAN_EDITS / claim "origen humano/cámara" | < WM_THRESHOLD | partial | solo C2PA (humano declarado, sin watermark) |
| DIGITAL_CAPTURE / HUMAN_EDITS / claim "origen humano/cámara" | >= WM_THRESHOLD | **contradiction** | C2PA dice humano PERO hay watermark fuerte → Integrity Clash |

Donde `WM_THRESHOLD = 0.5` (conservador; datos del spike: clean<=0.005, watermarked>=0.85).
El claim de "origen" se lee del manifest C2PA: `c2pa.source_type` (`C2paDigitalSourceType`)
y/o assertions `c2pa.actions` (acción `c2pa.created` con `softwareAgent`/generative) y/o
`stds.schema-org.CreativeWork.generatedBy`. Si el manifest no trae source_type ni claim
de origen legible → se trata como "C2PA leído pero origen indeteminado" → veredicto
`partial` (no contradiction, no trusted) para no inventar.

→ Esta tabla es la LEY de `reconcile.py`. Hermes NO introduce reglas fuera de ella.

## T2 — Fuentes reales de fixtures firmados C2PA (resuelve duda de Sil sobre KI-1 Opción C)

Verificado por llamadas reales a GitHub API (no asumido):

1. **`c2patool`** (CLI oficial de contentauth/c2pa-rs): release `c2patool-v0.26.72`,
   binario Linux `x86_64-unknown-linux-gnu.tar.gz`. README confirma soporte de
   "audio, image or video files" y permite AÑADIR manifests C2PA.
   → USO: firmar nuestros propios WAV de prueba para generar fixtures de AUDIO firmados
     reales (venciendo KI-1: no usamos el binding Python con bug de certificado).
   URL: https://github.com/contentauth/c2patool/releases (proyecto separado de c2pa-rs; ver NOTA DE URL abajo)
2. **Fuentes ya firmados por la tool oficial** (referencia/cross-check de Reader):
   - `contentauth/c2pa-rs` → `sdk/tests/fixtures/` (incluye `BigBuckBunny_320x180.mp4`
     firmado) y `cli/tests/fixtures/` (`C.jpg`, `earth_apollo17.jpg`, `verify.jpeg`...).
   → USO: validar que nuestro `c2pa_layer.py` (Reader) lee los MISMOS manifests que la
     tool canónica (test de paridad), aunque sean imagen/video.

NOTA DE URL (verificada por Sil 2026-07-14): `c2patool` vive AHORA como proyecto
separado en `github.com/contentauth/c2patool` (no solo dentro de `c2pa-rs/cli`).
Las releases/binario Linux están en `github.com/contentauth/c2patool/releases`.
Al implementar, descargar de AHÍ, no de `c2pa-rs/releases`. Funcionalidad idéntica.

Plan de fixtures (implementación):
- Descargar `c2patool` Linux, firmar WAVs de prueba (con/sin watermark, con claim
  humano/sintético) → `tests/fixtures/*.wav` versionados por SHA256.
- Usar 1-2 fixtures de `c2pa-rs` (imagen/video) como test de paridad de Reader.
- Si `c2patool` no corre en este entorno (GLIBC/binario), fallback: pedir a Claude en
  re-verificación que confirme, o usar fixtures de imagen de c2pa-rs como únicos
  fixtures de paridad (el caso audio se cubre con watermark real + C2PA leído de
  nuestros WAV firmados por c2patool).

## T3 — Estructura del repo y módulos

Crear bajo rama dedicada `feature/audiotrust`:
```
audiotrust/audiotrust/{__init__,cli,c2pa_layer,watermark_layer,reconcile,models}.py
audiotrust/tests/{test_verify.py, fixtures/}
audiotrust/{pyproject.toml, requirements.txt, README.md}
```
- `c2pa_layer.py`: usa `c2pa.Reader`; captura `_C2paManifestNotFound` → `present=False`.
  Extrae `source_type`, acciones, claims.
- `watermark_layer.py`: `audioseal.AudioSeal.load_generator/detector` desde pesos
  cacheados; devuelve SOLO `detect_prob` (nunca el mensaje). Forma tensor `[1,1,T]`.
  Requiere `TORCH_COMPILE_DISABLE=1` (setear en wrapper o documentar).
- `reconcile.py`: implementa TABLA T1.
- `models.py`: cacheo de pesos vía `huggingface_hub.hf_hub_download` (facebook/audioseal).
- `cli.py`: `verify <file> [--json] [--explain] [--wm-threshold FLOAT]`.

## T4 — Implementar los 4 veredictos + tests reproducibles

- `trusted`: WAV firmado por c2patool con claim sintético + watermark fuerte.
- `partial`: WAV solo con watermark (sin C2PA) y WAV solo C2PA (sin watermark).
- `unverifiable`: WAV sin nada → no crashea.
- `contradiction`: WAV firmado por c2patool con claim HUMANO + watermark fuerte.
- Test de paridad Reader con fixture de c2pa-rs (imagen/video).
- CI: clone limpio, instala deps, corre tests.

## T5 — README profesional

Formato: título H1, badge licencia AGPL-3.0-or-later, descripción, features, install
(pip + venv + `TORCH_COMPILE_DISABLE=1`), usage, sección licencia con link a LICENSE.
Sin banners ni URLs internas. Año 2026, autor "Pedro Sordo Martínez".

## T6 — (Paralelo, Opción B) Investigar índice PyTorch

Bajo esfuerzo: probar si `download.pytorch.org/whl/cpu` falla por DNS/proxy/CDN.
No bloquea T3-T5. Si se resuelve, migrar a wheel CPU liviano.

---

## Orden de ejecución
T1 (tabla) → T2 (fixtures c2patool) → T3 (módulos) → T4 (veredictos+tests) → T5 (README)
→ T6 (paralelo). Al terminar: push a `feature/audiotrust`, abrir PR, esperar re-verificación
de Claude y aprobación de Sil.
