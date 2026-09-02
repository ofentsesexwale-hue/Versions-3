"""Install RapidOCR into this Python if an older venv was created without it."""
from __future__ import annotations

import subprocess
import sys


def missing():
    need = []
    try:
        import rapidocr_onnxruntime  # noqa: F401
    except Exception:
        need.append('rapidocr-onnxruntime>=1.4')
    try:
        import onnxruntime  # noqa: F401
    except Exception:
        need.append('onnxruntime>=1.16')
    return need


def main():
    pkgs = missing()
    if not pkgs:
        print('RapidOCR already installed')
        return 0
    print('Installing', ' '.join(pkgs))
    cmd = [sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check', *pkgs]
    return subprocess.call(cmd)


if __name__ == '__main__':
    raise SystemExit(main())
