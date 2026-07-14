"""AudioTrust - paquete.

El import de `main` es PEREZOSO (lazy) a proposito: `cli` arrastra watermark_layer
-> torch/audioseal/soundfile, un stack pesado. Quien solo necesite `reconcile` o
`c2pa_layer.C2paResult` (dataclasses sin deps pesadas) NO debe cargar torch.
Ver hallazgo de auditoria de Claude (import pesado).
"""
from __future__ import annotations


def main(argv=None):
    """Entry point. Importa cli solo al ejecutar, no al importar el paquete."""
    from .cli import main as _main
    return _main(argv)


__all__ = ["main"]
