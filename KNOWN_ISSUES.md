# KNOWN_ISSUES — AudioTrust

**Fecha:** 2026-07-14
**Origen:** Spike de viabilidad (fase 0 SDD), entorno WSL Python 3.12.3.

Este archivo documenta explícitamente los huecos y límites encontrados en el
spike, con la evidencia cruda, para que no se pierdan al pasar a la Spec.

---

## KI-1 — Firmar manifest C2PA desde cero falla en c2pa-python 0.36.0

**Severidad:** Media (NO bloquea el producto, pero bloquea la generación de fixtures firmados)
**Impacto en alcance:** AudioTrust VERIFICA audio ya firmado por la herramienta que lo
generó (TTS/API de audio). El firmado desde cero solo se necesita para crear FIXTURES
de test. El producto no firma en producción.

**Evidencia cruda (errores reales del spike):**

1. Primer intento (RSA + `es256`):
   ```
   c2pa.c2pa._C2paSignature: Signature: invalid signing credentials
   (invalid ES256 private key: public key error: unknown/unsupported algorithm OID: 1.2.840.10045.2.1)
   ```
   → `es256` requiere clave EC (curva elíptica), no RSA.

2. Tras cambiar a EC P-256 (`ec.generate_private_key(ec.SECP256R1())`):
   ```
   c2pa.c2pa._C2paSignature: Signature: the certificate is invalid
   ```

3. Añadiendo `BasicConstraints(ca=False)` + `KeyUsage(digital_signature=True)`:
   ```
   c2pa.c2pa._C2paSignature: Signature: the certificate is invalid
   ```

4. Probando `ps256` + RSA con `BasicConstraints(ca=True)`:
   ```
   C2paError Error signing file: Signature: the certificate was self-signed
   ```

5. Cadena de 2 niveles (Root CA propia + leaf firmado por ella):
   ```
   C2paError Error signing file: Signature: the certificate is invalid
   ```

**API confirmada (funciona para lectura, ver KI-2):**
- `c2pa.Builder(json)` → `Builder`
- `c2pa.C2paSignerInfo(alg: bytes, cert_pem: bytes, key_pem: bytes, ta_url: bytes)` → `C2paSignerInfo`
- `c2pa.Signer.from_info(signer_info)` → `Signer`  (NO `Signer(signer_info)`)
- `builder.sign_file(src, dst, signer)` → bytes
- `c2pa.C2paDigitalSourceType.TRAINED_ALGORITHMIC_MEDIA` existe (marcar audio de IA).

**Hipótesis del fallo (PENDIENTE de resolver, no confirmada):**
c2pa-python 0.36.0 parece exigir la cadena de certificados completa embebida en el
`C2paSignerInfo` (leaf + intermediate + root) y/o un `ta_url` apuntando al cert raíz,
y rechaza certs autofirmados. No se descifró la convención exacta en el tiempo del spike.

**Plan de resolución (fuera del spike inicial):**
- Opción A: generar fixtures firmados con el CLI oficial de c2pa (`c2pa` Rust tool /
  `c2pa-cli`) en lugar del binding Python.
- Opción B: estudiar el ejemplo de `c2pa-python` para la forma correcta de pasar la
  cadena de certs al `C2paSignerInfo`.
- Opción C: para tests de reconciliación, usar audios de muestra ya firmados por
  herramientas reales (p.ej. los del ecosistema C2PA) como fixtures externos.

**No se asume resuelto.** Hasta no tener un fixture firmado real, la rama de tests
que requiera C2PA firmado por nosotros queda condicional.

---

## KI-2 — Lectura/verificación C2PA CONFIRMADA funciona

**Severidad:** N/A (evidencia positiva)
- `Reader` sobre WAV sin manifest → `c2pa.c2pa._C2paManifestNotFound: no JUMBF data found`
  (confirma que distingue firmado de no firmado). ✓
- Instalación de `c2pa-python` 0.36.0 limpia en venv, sin bindings nativos frágiles. ✓
- La lectura de un manifest ya firmado es la funcionalidad crítica de AudioTrust y es
  viable. El bloqueo de KI-1 es solo para GENERAR firmas, no para LEERLAS.

---

## KI-3 — AudioSeal: VERIFICADO (ciclo completo, evidencia cruda)

**Severidad:** Alta — RESUELTA (2026-07-14)
**Veredicto:** La pata de watermark de AudioTrust es VIABLE. Se cerró el ciclo completo
con score real y control negativo, exactamente como exigió Sil.

**Reproducibilidad (3 corridas, 2 entornos distintos):**
```
CORRIDA 1 (spike_at, spike):        WATERMARKED 0.924 / CLEAN 0.0009
CORRIDA 2 (spike_at, repeticion):   WATERMARKED 0.936 / CLEAN 0.0009
CORRIDA 3 (spike_at2, venv LIMPIO): WATERMARKED 0.859 / CLEAN 0.0047
  msg watermarked decod (corrida 3): [1 0 1 0 1 0 1 0 ...]  (head coincide, resto no)
```
→ `detect_prob` es ESTABLE y reproducible en 3 corridas / 2 venvs: watermarked
  ~0.86–0.94, clean ~0.001–0.005. Separación de ~2 órdenes de magnitud, consistente.
→ El MENSAJE decodificado es INCONSISTENTE entre corridas (corrida 1 coincidió head,
  corridas 2 y 3 NO). CONCLUSIÓN OBLIGATORIA: **AudioTrust NO debe depender del
  mensaje recuperado para ninguna funcionalidad** (ni siquiera como "bonus de
  trazabilidad"). Solo usar `detect_prob` (P(audio watermarked)) como señal.

**Verificación independiente C2PA (KI-4):** en venv limpio `spike_at2` (sin HF):
c2pa-python instala; `Reader`/`Builder` existen; `TRAINED_ALGORITHMIC_MEDIA`=12;
`Reader` sobre WAV sin manifest → `ManifestNotFound`. Coincide con KI-1/KI-2.
NOTA: el índice CPU de PyTorch (`download.pytorch.org/whl/cpu`) NO es alcanzable aquí
(`ConnectionResetError`); torch se instaló por PyPI (build CUDA cu130) y funciona con
`TORCH_COMPILE_DISABLE=1`. Ver decisión A/B pendiente en KI-4 para la Spec.

**Hallazgos técnicos del spike (para la Spec, no inventados):**
1. `audioseal` 0.2.0 NO expone `get_generator`/`get_detector`. API real:
   `audioseal.AudioSeal.load_generator(ruta_o_card, nbits=16, device=...)` y
   `audioseal.AudioSeal.load_detector(...)`.
2. Cargar desde HF con `path="facebook/audioseal"` FALLA: 404 + exige token HF.
   Solución usada en spike: descargar pesos con `huggingface_hub.hf_hub_download`
   (repo PÚBLICO, sin token) y cargar desde el `.pth` local:
   - `generator_base.pth` (58 MB), `detector_base.pth` (34 MB), `audioseal_encodec_32khz.th` (453 MB).
3. `load_generator` exige `nbits` (ej. 16) o lanza MissingMandatoryValue.
4. torch se instaló como **2.13.0+cu130** (build CUDA) en entorno CPU-only. Causa
   crash en `torch.compile`/dynamo del codec (IndexError en LSTM permute).
   Solución: `TORCH_COMPILE_DISABLE=1 TORCHDYNAMO_DISABLE=1` al ejecutar.
   → EN LA SPEC: fijar `torch` a build CPU (`torch==2.x+cpu` vía index de CPU, o
   `pip install torch --index-url https://download.pytorch.org/whl/cpu`) para no
   arrastrar ~1 GB de CUDA innecesario y evitar el crash.
5. Forma de tensor: `detect_watermark(x)` espera internamente `[batch, channels, time]`
   (=`[1,1,T]` mono). El docstring dice "batch x frames" pero el SEANet interno
   necesita la dim de canal. Usar `[1,1,T]`.
6. `detect_watermark` devuelve `(detect_prob, message)`: detect_prob = P(audio watermarked);
   message = tensor `batch x nbits` (prob de cada bit). **IMPORTANTE:** el mensaje es
   INCONSISTENTE entre corridas (ver reproducibilidad arriba) → Solo usar `detect_prob`.
7. REGLA DE DISEÑO (de KI-3): el veredicto de watermark de AudioTrust = `detect_prob`
   vs umbral. El mensaje decodificado NO se usa para nada en la lógica de reconciliación.

---

## Regla de este archivo
Cualquier "confirmado" aquí lleva evidencia cruda (comando/error/output). Cualquier
"pendiente" se marca como tal y NO se mueve a la Constitución como hecho hasta cerrarse.

---

## KI-4 — Verificación C2PA independiente (venv limpio, sin HF)

**Fecha:** 2026-07-14 · **Entorno:** `/tmp/spike_at2` (venv nuevo, distinto al spike original)
**Hecho por:** Hermes, a petición de Sil (auditoría independiente, punto #2)
**Alcance:** SOLO lo que el auditor podía hacer (instalación + API + lectura sintética,
sin HF porque los pesos de AudioSeal no se reproducen aquí).

**Evidencia cruda:**
```
c2pa version: <function version...> | sdk_version: <function sdk_version...>
Reader?: True
Builder?: True
C2paDigitalSourceType.TRAINED_ALGORITHMIC_MEDIA: 12
Reader SIN manifest -> _C2paManifestNotFound : ManifestNotFound: no JUMBF data found
```
→ Confirma en venv limpio: c2pa-python instala; API `Reader`/`Builder` existe;
`TRAINED_ALGORITHMIC_MEDIA` es enum válido (12); `Reader` sobre WAV sin manifest
lanza `ManifestNotFound` (distingue firmado/no firmado). Coincide con KI-1/KI-2.

**Nota de integridad:** El `--index-url https://download.pytorch.org/whl/cpu` en el
comando original FALLÓ para los paquetes PyPI (`c2pa-python` no se encontró) porque
`--index-url` REEMPLAZA PyPI en vez de añadirlo. Corrección aplicada: torch por el
índice pytorch en comando separado; el resto por PyPI normal. Documentado para no
repetir el error en la Spec (ver sección de instalación del repo).

**Pata AudioSeal en venv limpio:** pendiente de que termine la instalación de torch
en background. NOTA DE RED (2026-07-14): `pip install torch --index-url
https://download.pytorch.org/whl/cpu` FALLÓ en este entorno con
`ConnectionResetError(104, 'Conexión reinicializada por la máquina remota')` y
"No matching distribution found for torch". El índice CPU de PyTorch NO es alcanzable
de forma fiable aquí. Alternativa en curso: instalar torch por PyPI normal (build
CUDA `cu130`, igual que el spike original) en `spike_at2`, que ya demostró funcionar
con `TORCH_COMPILE_DISABLE=1`.

**DECISIÓN TOMADA (2026-07-14, camino intermedio):** Opción A ahora + Opción B en
paralelo (no excluyentes).
- (A) Se adopta: build CUDA `cu130` vía PyPI normal, funciona en CPU-only con
  `TORCH_COMPILE_DISABLE=1 TORCHDYNAMO_DISABLE=1`. Variable REQUERIDA en despliegue.
  Costo: ~1 GB CUDA no usado.
- (B) Tarea de bajo esfuerzo en paralelo: investigar fallo del índice PyTorch
  (DNS/proxy/cert/CDN) para usar wheel CPU liviano a futuro. No bloquea Spec.
Documentado también en Constitución §6.

---

## KI-5 — c2patool 0.9.12 firma JPG pero NO WAV/PNG en este entorno (limitación de formato, no bug del binario)

**Severidad:** Alta para T4 (fixtures de AUDIO firmados)
**Fecha:** 2026-07-14 · **Estado:** BLOQUEADO para audio (diagnóstico completo hecho; decisión de Sil pendiente)

**Diagnóstico aislado (paso barato, ejemplo oficial exacto):**
Se reprodujo el error con el comando EXACTO del README de `contentauth/c2patool`
(asset primero, luego `-m`, luego `-o`), sin variación nuestra:
```
$ c2patool sample/image.jpg -m sample/test.json -o signed_image.jpg   => FUNCIONA (firma JPG)
$ c2patool tests/fixtures/synth.wav -m scripts/manifest_synthetic.json -o tests/fixtures/synth_signed.wav
   => Error: glob patterns only allowed when using "fragment" command   (NO firma WAV)
$ c2patool tests/fixtures/test_img.png ...                               => idem (NO firma PNG)
```
→ El binario NO está roto: firma JPG correctamente (manifest válido, claim_generator
  "TestApp c2patool/0.9.12 c2pa-rs/0.37.0"). El error de "glob" es el MENSAJE CONFUSO
  de la build cuando el formato de asset NO es de los aceptados para embebido (JPG/sí,
  WAV/PNG/no). NO es un error de orden de flags (la imagen funcionó con el mismo orden).
CONCLUSIÓN: **esta build 0.9.12 embebe en imágenes (JPG) pero NO en audio (WAV) ni PNG
en este entorno.** La afirmación "c2patool soporta audio" es cierta para la herramienta
en general, pero ESTA BUILD no lo hace aquí.

**bug #2 destapado y CONFIRMADO (strings de source_type):** se leyó con `c2patool`
el fixture que ÉL MISMO firmó (`signed_image.jpg`, manifest `sample/test.json`):
assertions = `stds.schema-org.CreativeWork`, `c2pa.actions` con `action: "c2pa.opened"`,
`my.assertion`. **NO hay `source_type` explícito** (ni `trained_algorithmic_media`).
También del fixture real de c2pa-rs (`C.jpg`): `c2pa.actions` con `c2pa.created` /
`c2pa.drawing`, sin source_type.
→ Los `SYNTHETIC_TYPES`/`HUMAN_TYPES` con strings `c2pa.trained_algorithmic_media` del
  README de C2PA NUNCA coincidirán con una firma real por defecto, porque el
  source_type no se incluye salvo que el manifest lo declare explícitamente.
→ `reconcile.py` YA se apoya en `c2pa.created` / `generatedBy` en los claims (no solo
  source_type) → es la vía que funciona con firmas reales. Se mantiene así. Para que
  `trusted`/`contradiction` se disparen con fixture REAL, el manifest debe declarar
  origen explícitamente (action `c2pa.created` + `generatedBy`, o assertion de
  digitalSourceType), lo cual c2patool permite pero no viene por defecto.

**Impacto en KI-1 (Opción C):** los fixtures de AUDIO firmados NO se pueden generar con
c2patool 0.9.12 aquí (no acepta WAV). El binding Python de c2pa tiene el bug de
certificado (KI-1) y queda PROHIBIDO como fallback silencioso (exigencia de Sil).
Por tanto `trusted`/`contradiction` no tienen fixture de AUDIO firmado real hoy.

**Decisiones pendientes (Sil elige antes de cerrar T4):**
- (A) Aceptar que no hay fixture de audio firmado; testear `trusted`/`contradiction`
  con manifest MOCK (ya implementado en test_verify.py). KI-1 queda abierto para audio.
- (B) Probar otra versión de c2patool (más nueva/vieja) que sí embeba WAV (especulativo).
- (Y) Generar fixtures de audio firmados con el binding Python ACEPTANDO el bug KI-1
  (solo TESTS internos, documentado, NO silencioso). Contrario a preferencia previa.

Lo documentado prevalece sobre "c2patool resuelve KI-1": en ESTE entorno, con ESTA
build, el embebido de audio no está soportado. El binario en sí funciona (firma JPG).

---

## KI-6 — Bug de logica en `_origin_claim` (reconciliacion invertida) — CORREGIDO

**Severidad:** Crítica (afectaba el veredicto central del producto)
**Fecha:** 2026-07-14 · **Estado:** CORREGIDO (hallado por auditoria de Claude en clone limpio)

**Hallazgo de Claude (independiente, verificado):** `_origin_claim` clasificaba como
`"synthetic"` cualquier claim con `c2pa.created` genérico (presente en CUALQUIER
manifest, sea IA o humano), salvo que el nombre del agente contuviera literalmente
"human"/"camera"/"capture". Con un agente humano realista ("Zoom H4n", "Voice Memos")
el origen caía en `"synthetic"`; si `detect_prob` daba alto, el veredicto era
`trusted` EN VEZ de `contradiction`. Eso invertía el propósito: `trusted` demasiado
fácil, `contradiction` (Integrity Clash, corazón del producto) casi inalcanzable.

**Corrección aplicada en `reconcile.py`:**
- Default sin evidencia POSITIVA de origen = `"indeterminate"` (-> `partial`), NUNCA
  `"synthetic"`.
- `"synthetic"` solo con señal positiva explícita de generación por IA
  (`SYNTHETIC_SIGNALS`: generatedby / softwareagent / trained_algorithmic /
  c2pa.generated / generative). `c2pa.created` solo NO basta.
- `"human"` solo con señal positiva explícita de captura (`HUMAN_SIGNALS`:
  c2pa.digital_capture / c2pa.captured / device / c2pa.edited).
- Ambas/ninguna/ambigua -> `"indeterminate"` (default seguro).
Así `trusted` exige evidencia de IA y `contradiction` es alcanzable cuando el C2PA
declara captura humana y hay watermark.

**Tests:** `test_verify.py` añade `test_origin_heuristic` que cubre los casos
("Zoom H4n" -> indeterminate->partial; "TestTTS" generatedBy -> synthetic; captura
-> human). Verificado en clone limpio por Claude.


