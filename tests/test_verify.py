"""Tests de AudioTrust.

Cobertura verificable en este entorno (ver KNOWN_ISSUES.md KI-5):
- partial: WAV watermarkado por AudioSeal (real) SIN C2PA -> partial.      [END-TO-END real]
- unverifiable: WAV limpio sin nada -> unverifiable (no crashea).           [END-TO-END real]
- trusted / contradiction: se cubren con un manifest C2PA MOCK inyectado en memoria
  (C2paResult construido directamente, NO pasa por c2pa_layer.read_c2pa).
  AVISO: estos dos tests son UNITARIOS de reconcile.py, NO de integración
  end-to-end. NO ejercitan el parser real del JSON del manifest porque no hay fixture
  de AUDIO firmado real disponible (c2patool 0.9.12 no acepta WAV en este entorno;
  ver KI-5). No deben confundirse con "ya probamos lectura+reconciliación con audio
  sintético real". El binding Python de c2pa queda PROHIBIDO como fallback (KI-1).

NO se usa el binding Python de c2pa para firmar (prohibido como fallback silencioso).
"""
import os
import tempfile

import numpy as np
import soundfile as sf
import torch
import audioseal

from audiotrust.c2pa_layer import C2paResult
from audiotrust.reconcile import reconcile, WM_THRESHOLD

SR = 16000
DUR = 5.0


def _make_wav(watermark: bool, path: str):
    rng = np.random.RandomState(42)
    wav = (0.2 * rng.randn(int(SR * DUR))).astype(np.float32)
    if watermark:
        from audiotrust import models as mdl
        gen_pth, _, _ = mdl.paths()
        gen = audioseal.AudioSeal.load_generator(gen_pth, nbits=16, device=torch.device("cpu"))
        msg = torch.tensor([1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0],
                           dtype=torch.float32).unsqueeze(0).to(torch.device("cpu"))
        wav_t = torch.from_numpy(wav).float().unsqueeze(0).unsqueeze(0).to(torch.device("cpu"))
        wm_t = gen.get_watermark(wav_t, sample_rate=SR, message=msg)
        wav = wm_t.detach().cpu().numpy()[0, 0]
    sf.write(path, wav, SR)


def test_unverifiable(tmp_path):
    p = str(tmp_path / "clean.wav")
    _make_wav(watermark=False, path=p)
    from audiotrust.c2pa_layer import read_c2pa
    from audiotrust.watermark_layer import detect_prob
    c2pa = read_c2pa(p)
    prob = detect_prob(p)
    v = reconcile(c2pa, prob, WM_THRESHOLD)
    assert v.verdict == "unverifiable", v.verdict


def test_partial_watermark_only(tmp_path):
    p = str(tmp_path / "wm.wav")
    _make_wav(watermark=True, path=p)
    from audiotrust.c2pa_layer import read_c2pa
    from audiotrust.watermark_layer import detect_prob
    c2pa = read_c2pa(p)  # sin C2PA -> present=False
    prob = detect_prob(p)
    assert prob >= WM_THRESHOLD, f"esperado watermark fuerte, got {prob}"
    v = reconcile(c2pa, prob, WM_THRESHOLD)
    assert v.verdict == "partial", v.verdict


def test_trusted_with_mock_c2pa():
    # Manifest MOCK: origen sintetico declarado (c2pa.created + generatedBy)
    c2pa = C2paResult(
        present=True,
        source_type="c2pa.trained_algorithmic_media",
        claims=["action=c2pa.created by TestTTS", "generatedBy=TestTTS"],
    )
    v = reconcile(c2pa, detect_prob=0.92, wm_threshold=WM_THRESHOLD)
    assert v.verdict == "trusted", v.verdict


def test_contradiction_with_mock_c2pa():
    # Manifest MOCK: origen humano declarado PERO watermark fuerte -> Integrity Clash
    c2pa = C2paResult(
        present=True,
        source_type="c2pa.digital_capture",
        claims=["action=c2pa.created by HumanRecorder"],
    )
    v = reconcile(c2pa, detect_prob=0.92, wm_threshold=WM_THRESHOLD)
    assert v.verdict == "contradiction", v.verdict


def test_watermark_layer_never_returns_message():
    # Garantiza que watermark_layer solo expone detect_prob (regla KI-3).
    import audiotrust.watermark_layer as wl
    assert "detect_prob" in dir(wl)
    # El modulo no expone funcion que devuelva el mensaje decodificado
    assert not any("message" in n and "detect" not in n for n in dir(wl))
