"""Font files: Segoe UI on Windows, DejaVu Sans elsewhere (CI), so the PDFs build on any machine."""
import os

_C = {False: [r"C:\Windows\Fonts\segoeui.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/Library/Fonts/Arial Unicode.ttf"],
      True: [r"C:\Windows\Fonts\segoeuib.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/Library/Fonts/Arial Unicode.ttf"]}


def path(bold=False):
    return next((p for p in _C[bold] if os.path.exists(p)), _C[bold][0])
