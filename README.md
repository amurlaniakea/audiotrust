# AudioTrust

Verificador local de **reconciliación de confianza** para audio generado por IA.

AudioTrust lee las dos marcas de confianza de un audio sintético y emite un veredicto
auditable sobre si coinciden, se contradicen o faltan:

- **Provenance C2PA** — el certificado digital embebido en el archivo (su "DNI").
- **Watermark AudioSeal** — código inaudible oculto en el sonido.

## Features

- Lee el manifest C2PA de un archivo de audio (WAV/MP3/FLAC).
- Detecta la presencia de watermark AudioSeal y devuelve `detect_prob`.
- Reconcilia ambas capas → veredicto `trusted` / `contradiction` / `partial` / `unverifiable`.
- 100% local: sin llamadas de red en tiempo de ejecución.
- Read-only: no modifica el audio analizado.
- No reentrena modelos: usa pesos públicos y criptografía.

## Install

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
# Los pesos de AudioSeal se descargan en la primera ejecucion (repo publico facebook/audioseal).
```

> **Importante (torch en CPU):** en este entorno `torch` se instala como build CUDA.
> Antes de ejecutar, exporta:
> ```bash
> export TORCH_COMPILE_DISABLE=1
> export TORCHDYNAMO_DISABLE=1
> ```
> Sin estas variables el codec de AudioSeal crashea en `torch.compile`/dynamo.

## Usage

```bash
audiotrust verify ruta/al/audio.wav
audiotrust verify ruta/al/audio.wav --json
audiotrust verify ruta/al/audio.wav --explain --wm-threshold 0.5
```

Salida JSON:
```json
{
  "file": "audio.wav",
  "verdict": "trusted",
  "c2pa": {"present": true, "source_type": "c2pa.trained_algorithmic_media", "claims": ["action=c2pa.created by TestTTS"]},
  "watermark": {"present": true, "detect_prob": 0.92},
  "explanation": "C2PA declara origen sintetico y hay watermark fuerte: coherentes."
}
```

## Veredictos

| C2PA | watermark | Veredicto |
|------|-----------|-----------|
| ausente | ausente | `unverifiable` |
| ausente | presente | `partial` |
| origen sintético | presente | `trusted` |
| origen humano | presente | `contradiction` (Integrity Clash) |
| leído (origen indeteminado) | * | `partial` |

## License

AGPL-3.0-or-later — Pedro Sordo Martínez (amurlaniakea@gmail.com).
