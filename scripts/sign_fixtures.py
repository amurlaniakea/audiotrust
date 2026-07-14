"""Firma los WAVs base con c2patool (KI-1, Opción C) para producir fixtures C2PA reales.

NO usa el binding Python de c2pa (tiene el bug de certificado KI-1). Usa el binario
oficial contentauth/c2patool (releases en github.com/contentauth/c2patool).
"""
import os
import subprocess
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
C2PATOOL = os.path.join(ROOT, "tools", "c2patool", "c2patool")
FIX = os.path.join(ROOT, "tests", "fixtures")


def run(cmd):
    print("+", " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("STDERR:", r.stderr)
        raise SystemExit(f"c2patool fallo ({r.returncode})")
    return r.stdout


def main():
    if not os.path.exists(C2PATOOL):
        raise SystemExit(f"No encontre c2patool en {C2PATOOL}")
    # Fixture sintetico: synth.wav + manifest_synthetic.json -> synth_signed.wav
    run([C2PATOOL, os.path.join(FIX, "synth.wav"),
         "-m", os.path.join(HERE, "manifest_synthetic.json"),
         "-o", os.path.join(FIX, "synth_signed.wav")])
    # Fixture humano: human.wav + manifest_human.json -> human_signed.wav
    run([C2PATOOL, os.path.join(FIX, "human.wav"),
         "-m", os.path.join(HERE, "manifest_human.json"),
         "-o", os.path.join(FIX, "human_signed.wav")])
    print("Fixtures firmados generados en", FIX)


if __name__ == "__main__":
    main()
