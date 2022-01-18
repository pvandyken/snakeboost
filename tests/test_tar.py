from __future__ import absolute_import

import subprocess as sp
import tarfile
from pathlib import Path

from snakeboost import tar


def test_output(tmp_path: Path):
    sp.run(
        tar.Tar(tmp_path, outputs=[str(tmp_path / "venv.tar.gz")])(
            f"virtualenv {tmp_path/'venv.tar.gz'}"
        ).format(),
        shell=True,
        capture_output=True,
    )
    with tarfile.open(tmp_path / "venv.tar.gz", "r:gz") as tf:
        assert len(tf.getmembers()) == 706
