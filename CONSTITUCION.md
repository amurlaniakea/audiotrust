# Constitución — AudioTrust

**Proyecto:** AudioTrust
**Autor:** Pedro Sordo Martínez (amurlaniakea@gmail.com)
**Licencia:** AGPL-3.0-or-later
**Fecha:** 2026-07-14
**Estado:** Constitución (fase 0 de SDD). Pendiente de spike de AudioSeal y de firma C2PA.

---

## 1. Propósito

AudioTrust es una herramienta local (CLI + librería) que **reconcilia las dos
marcas de confianza** de un audio generado por IA:

- **Provenance C2PA:** certificado digital embebido (el "DNI" del archivo).
- **Watermark inaudible:** código oculto en el sonido (AudioSeal).

Su trabajo es **comparar ambas y emitir un veredicto auditable** sobre si
coinciden, se contradicen o faltan. NO entrena ningún detector; reutiliza
herramientas OSS existentes.

## 2. Principios innegociables

- **100% local.** Nada sale del equipo del usuario. Sin llamadas de red.
- **Read-only sobre el audio ajeno.** AudioTrust lee y emite veredicto; no
  modifica el archivo salvo que se le pida explícitamente escribir un informe.
- **Sin reentrenar modelos.** Solo usa pesos públicos (AudioSeal) y firmas
  criptográficas (c2pa-python).
- **Veredicto auditable.** Salida JSON con trazabilidad (qué se vio, qué faltó).
- **Sin fabricación.** Si una capa no se puede leer, el veredicto lo dice
  explícitamente (`unverifiable`), no asume.
- **REGLA DE WATERMARK (de KI-3):** el veredicto de watermark se basa EXCLUSIVAMENTE
  en `detect_prob` (P(audio watermarked) de AudioSeal). El mensaje decodificado es
  INCONSISTENTE entre corridas (ver KNOWN_ISSUES.md KI-3, 2 corridas documentadas) y
  NO se usa para ninguna funcionalidad, ni siquiera trazabilidad. Quien implemente
  no debe introducir dependencia del mensaje recuperado.

## 3. Alcance (IN / OUT)

**IN:**
- Leer manifest C2PA de un archivo de audio (WAV/MP3/FLAC).
- Detectar watermark AudioSeal y su localización.
- Reconciliar: coincidencia / contradicción / parcial / no verificable.
- CLI `audiotrust verify <file>` con salida JSON + texto.
- Fixtures de prueba firmados+watermarkados.

**OUT (esta fase):**
- Generar audio sintético propio (lo hace la herramienta de TTS del usuario).
- Firmar manifests C2PA desde cero en producción (el audio ya viene firmado
  por quien lo genera; AudioTrust verifica). El firmado solo se usa para
  generar FIXTURES de test, y requiere resolver la receta de cert del binding.
- Detección de deepfake por clasificador (otro nicho; no es esta capa).

## 4. Veredictos del sistema

| Veredicto | Significado |
|-----------|-------------|
| `trusted` | Hay C2PA válido Y watermark presente, y ambos coinciden (mismo claim de origen). |
| `contradiction` | C2PA y watermark se contradicen (Integrity Clash). |
| `partial` | Solo una de las dos capas está presente. |
| `unverifiable` | No se pudo leer ninguna capa (formato no soportado, corrupto, sin soporte). |

## 5. Evidencia del spike (2026-07-14) — lo que YA está confirmado

**PATA C2PA (lectura/verificación) — CONFIRMADA:**
- `c2pa-python` 0.36.0 instala limpio en venv (sin bindings nativos frágiles).
- API `Reader`/`Builder`/`Signer`/`C2paDigitalSourceType` opera sobre **audio WAV**.
- `Reader` sobre WAV sin manifest → `ManifestNotFound` (distingue firmado/no firmado). ✓
- `C2paDigitalSourceType.TRAINED_ALGORITHMIC_MEDIA` existe (marcar audio de IA). ✓
- Lectura de manifest ya firmado = funcionalidad crítica de AudioTrust = viable.
- **HUECO (KI-1):** firmar manifest desde cero falla ("certificate is invalid" /
  "self-signed") en c2pa-python 0.36.0. NO bloquea: AudioTrust VERIFICA audio ya
  firmado por quien lo generó; el firmado solo sirve para fixtures y se resuelve
  aparte (ver KNOWN_ISSUES.md). API de firma confirmada: `C2paSignerInfo(bytes, cert, key, ta_url)`
  + `Signer.from_info(...)`.

**PATA AudioSeal (watermark) — VERIFICADA (ciclo completo, evidencia cruda):**
```
detect_prob WATERMARKED: 0.924   detect_prob CLEAN: 0.0009
msg watermarked decod: [1 0 1 0 1 0 1 0] == original
```
El detector distingue watermarked de limpio y recupera el mensaje. API real:
`AudioSeal.load_generator(ruta_pth, nbits=16, device)`, `detect_watermark` →
`(detect_prob, message)`. Ver KNOWN_ISSUES.md KI-3 para todos los detalles
(torche CUDA crash → `TORCH_COMPILE_DISABLE=1`, forma `[1,1,T]`, descarga de pesos
desde HF sin token, nbits obligatorio).

## 6. Dependencias (fijadas tras spike)

- `c2pa-python==0.36.0` (lectura/manifest) — CONFIRMADO instala y lee.
- `audioseal==0.2.0` + `torch` (watermark) — VERIFICADO ciclo completo (3 corridas,
  2 venvs; detect_prob WATERMARKED>=0.85 / CLEAN<=0.005).
- **Decisión torch (2026-07-14): Opción A.** El índice CPU de PyTorch
  (`download.pytorch.org/whl/cpu`) NO es alcanzable en este entorno
  (ConnectionResetError). Se usa el build CUDA `cu130` vía PyPI normal, que funciona
  en CPU-only con `TORCH_COMPILE_DISABLE=1 TORCHDYNAMO_DISABLE=1`. Variable de entorno
  REQUERIDA en cualquier despliegue (Docker/CI): si se olvida, el codec crashea en
  dynamo (IndexError en LSTM permute). Costo: ~1 GB de CUDA no usado.
- **Tarea paralela (Opción B, bajo esfuerzo, NO bloquea):** investigar por qué falla
  el índice PyTorch (DNS/proxy/cert/CDN) para poder usar el wheel CPU liviano a futuro.
  No es mutuamente excluyente con A.
- `huggingface_hub` — para descargar pesos de `facebook/audioseal` (repo público).
- `soundfile` + `numpy` (I/O audio) — CONFIRMADO instala.
- Pesos: `generator_base.pth` (58MB), `detector_base.pth` (34MB),
  `audioseal_encodec_32khz.th` (453MB) — descargados localmente en el spike.

## 7. Criterios de aceptación (Definition of Done)

1. `audiotrust verify <wav_firmado>` devuelve JSON con veredicto `trusted`/`partial`.
2. Un fixture con C2PA y watermark que se contradicen devuelve `contradiction`.
3. Un WAV sin nada devuelve `unverifiable` (no crashea).
4. Tests reproducibles con fixtures en el repo.
5. README conlicencia AGPL-3.0-or-later y formato profesional (ver regla de Sil).

## 8. Gobernanza

- Flujo: Hermes implementa → Claude re-verifica en clone limpio → Sil aprueba merge.
- Entrega en rama dedicada (nunca main).
- Sin banners ni URLs internas en README.
