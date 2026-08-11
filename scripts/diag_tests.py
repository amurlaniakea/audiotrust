"""Diagnostico local de los dos fallos de test (no -c inline).

Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
SPDX-License-Identifier: AGPL-3.0-or-later
"""
import os, sys, numpy as np, soundfile as sf, torch, audioseal
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from audiotrust import models as mdl

SR = 16000
DUR = 5.0
gen_pth, det_pth, _ = mdl.paths()
print("pesos:", os.path.basename(gen_pth), os.path.basename(det_pth))
gen = audioseal.AudioSeal.load_generator(gen_pth, nbits=16, device=torch.device("cpu"))
det = audioseal.AudioSeal.load_detector(det_pth, nbits=16, device=torch.device("cpu"))

# WAV limpio
t = np.linspace(0, DUR, int(SR*DUR), endpoint=False)
wav = (0.2*np.sin(2*np.pi*440*t)).astype(np.float32)
sf.write("/tmp/diag_clean.wav", wav, SR)
sf.write("/tmp/diag_wm.wav", wav, SR)  # reescribimos abajo con watermark

# marca
msg = torch.tensor([1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0], dtype=torch.float32).unsqueeze(0).to(torch.device("cpu"))
wav_t = torch.from_numpy(wav).float().unsqueeze(0).unsqueeze(0).to(torch.device("cpu"))
wm_t = gen.get_watermark(wav_t, sample_rate=SR, message=msg)
sf.write("/tmp/diag_wm.wav", wm_t.detach().cpu().numpy()[0,0], SR)

for name, p in [("clean", "/tmp/diag_clean.wav"), ("wm", "/tmp/diag_wm.wav")]:
    w, sr = sf.read(p, dtype="float32")
    if w.ndim > 1:
        w = w.mean(axis=1)
    print(f"\n=== {name}: sr={sr} len={len(w)} ===")
    print("signature detect_watermark:", __import__("inspect").signature(det.detect_watermark))
    try:
        prob, msg_dec = det.detect_watermark(torch.from_numpy(w).float().unsqueeze(0).unsqueeze(0), sample_rate=SR)
        print("  prob (kwarg)=", float(prob.detach().cpu().numpy()[0]))
    except Exception as e:
        print("  KWARG FALLO:", type(e).__name__, e)
    try:
        prob, msg_dec = det.detect_watermark(torch.from_numpy(w).float().unsqueeze(0).unsqueeze(0), SR)
        print("  prob (posicional)=", float(prob.detach().cpu().numpy()[0]))
    except Exception as e:
        print("  POSICIONAL FALLO:", type(e).__name__, e)
