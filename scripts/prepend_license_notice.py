"""Prepend del aviso de copyright al LICENSE sin tocar el texto canonico de la FSF."""
import io

NOTICE = """AudioTrust
Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

See the full license text below.

================================================================================

"""

with io.open("LICENSE", "r", encoding="utf-8") as f:
    body = f.read()

with io.open("LICENSE", "w", encoding="utf-8") as f:
    f.write(NOTICE)
    f.write(body)

print("Aviso de copyright prepended a LICENSE")
