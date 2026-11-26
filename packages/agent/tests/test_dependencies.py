"""The parts of aiida-mlip 0.3.0 that the MLIP tools can use load with the locked aiida-core.

aiida-mlip is held at 0.3.0 and its workgraph workflow does not import with aiida-core 2.9 (the comment on the pin in
packages/agent/pyproject.toml). This test fails if a new lock breaks its calculations or data types too.
"""

import os
import subprocess
import sys
from pathlib import Path

CALCULATIONS = ["mlip.sp", "mlip.opt", "mlip.md", "mlip.train", "mlip.descriptors"]
DATA = ["mlip.modeldata", "mlip.config"]

LOAD = f"""
from aiida.plugins import CalculationFactory, DataFactory
for name in {CALCULATIONS!r}:
    CalculationFactory(name)
for name in {DATA!r}:
    DataFactory(name)
"""


def test_the_aiida_mlip_calculations_and_data_types_load(tmp_path: Path) -> None:
    # Importing aiida creates a configuration folder; AIIDA_PATH keeps it out of the home folder.
    environment = {**os.environ, "AIIDA_PATH": str(tmp_path)}
    result = subprocess.run([sys.executable, "-c", LOAD], env=environment, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
