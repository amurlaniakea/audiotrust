"""Genera WAVs de prueba para fixtures de AudioTrust (sin watermark todavia).
Se firman luego con c2patool (KI-1, Opción C) para producir los fixtures C2PA.
"""
import numpy as np
import soundfile as sf
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fixtures")
os.makedirs(OUT, exist_ok=True)

SR = 16000
DUR = 3.0
t = np.linspace(0, DUR, int(SR * DUR), endpoint=False)
wav = (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)

# Mismo audio base para todos; la diferencia es el manifest C2PA que les pondra
# c2patool (sintetico vs humano vs ninguno).
for name in ["synth.wav", "human.wav", "clean.wav"]:
    sf.write(os.path.join(OUT, name), wav, SR)
    print("escrito", name, os.path.getsize(os.path.join(OUT, name)), "bytes")

# Un WAV a 44.1kHz para probar el resampleo de watermark_layer
t2 = np.linspace(0, DUR, int(44100 * DUR), endpoint=False)
wav44 = (0.2 * np.sin(2 * np.pi * 440 * t2)).astype(np.float32)
sf.write(os.path.join(OUT, "synth_44k.wav"), wav44, 44100)
print("escrito synth_44k.wav", os.path.getsize(os.path.join(OUT, "synth_44k.wav")), "bytes")
