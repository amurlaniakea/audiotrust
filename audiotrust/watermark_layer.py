"""AudioTrust - capa watermark AudioSeal.

Detecta la presencia de watermark inaudible y devuelve UNICAMENTE detect_prob
(P(audio watermarked)). REGLA KI-3: el mensaje decodificado es INCONSISTENTE entre
corridas y NO se usa para nada en la logica de reconciliacion. Esta capa no lo expone.
"""
from __future__ import annotations

import os
import tempfile

import numpy as np
import soundfile as sf
import torch

from . import models

NBITS = 16
SAMPLE_RATE = 16000

# Requerido en CPU-only con build CUDA: si falta, el codec crashea en torch dynamo.
os.environ.setdefault("TORCH_COMPILE_DISABLE", "1")
os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")

_generator = None
_detector = None


def _load():
    global _generator, _detector
    if _generator is None or _detector is None:
        gen_pth, det_pth, _ = models.paths()
        # API real verificada en spike (KI-3): audioseal.AudioSeal.load_generator/detector
        import audioseal
        _generator = audioseal.AudioSeal.load_generator(gen_pth, nbits=NBITS, device=torch.device("cpu"))
        _detector = audioseal.AudioSeal.load_detector(det_pth, nbits=NBITS, device=torch.device("cpu"))


def detect_prob(path: str) -> float:
    """Devuelve P(audio watermarked) en [0,1].

    Solo detect_prob. El mensaje decodificado NO se calcula ni se devuelve.
    El modelo AudioSeal base espera 16 kHz; si el archivo viene a otra tasa se
    resamplea linealmente a 16 kHz antes de detectar (pasar otra tasa al detector
    lo descalibraria). Lanza RuntimeError si el audio no se puede leer.
    """
    _load()
    wav, sr = sf.read(path, dtype="float32", always_2d=False)
    # A mono si es estereo
    if wav.ndim > 1:
        wav = wav.mean(axis=1)
    # Resampleo a 16 kHz si hace falta (AudioSeal base es 16 kHz)
    if sr != SAMPLE_RATE:
        n = int(round(len(wav) * SAMPLE_RATE / sr))
        if n > 0:
            x_old = np.linspace(0, 1, len(wav), endpoint=False)
            x_new = np.linspace(0, 1, n, endpoint=False)
            wav = np.interp(x_new, x_old, wav).astype(np.float32)
    # AudioSeal espera [batch, channels, time] = [1, 1, T]
    wav = np.ascontiguousarray(wav)
    tensor = torch.from_numpy(wav).float().unsqueeze(0).unsqueeze(0).to(torch.device("cpu"))  # [1,1,T]
    with torch.no_grad():
        prob, _message = _detector.detect_watermark(tensor, sample_rate=SAMPLE_RATE)
    return float(prob.detach().cpu().numpy()[0])
