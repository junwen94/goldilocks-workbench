"""Processes and a monitor for S2, loaded by the daemon's workers from PYTHONPATH (see s2_env.environment).

Imports AiiDA: only run under a run's AIIDA_PATH.
"""

import time
from pathlib import Path
from typing import Any

from aiida.engine import WorkChain

# aiida-core 2.9.4 reads a monitor's version from its top-level module's __version__ and fails at job creation
# (KeyError: 'plugin' in CalcJob._setup_version_info) if there is none, though its version helper treats the plugin
# version as optional. S2 found this; the module holding the monitor must therefore define __version__.
__version__ = "0.0.0"


class Boom(WorkChain):
    """A work chain whose only step raises, so the process ends excepted."""

    @classmethod
    def define(cls, spec: Any) -> None:
        super().define(spec)
        spec.outline(cls.boom)

    def boom(self) -> None:
        raise RuntimeError("a deliberate failure, for S2's excepted state")


def observe(node: Any, transport: Any, log: str = "", **kwargs: Any) -> None:
    """An observe-only CalcJob monitor: it records that it was called and returns None, so it takes no action."""
    if log:
        with Path(log).open("a") as stream:
            stream.write(f"{time.time():.3f} {node.pk}\n")
    return None


def add_builder(
    x: int,
    y: int,
    code: str = "bash",
    sleep: int = 0,
    disable_cache: bool = False,
    monitors: dict[str, dict[str, Any]] | None = None,
) -> Any:
    """A core.arithmetic.add job on presto's localhost: x + y by the named code, after `sleep` seconds."""
    import aiida.orm
    from aiida.plugins import CalculationFactory

    orm: Any = aiida.orm  # AiiDA's own types are loose (untyped constructors); spike code treats them as Any
    factory: Any = CalculationFactory("core.arithmetic.add")
    builder: Any = factory.get_builder()
    builder.code = orm.load_code(f"{code}@localhost")
    builder.x, builder.y = orm.Int(x), orm.Int(y)
    if sleep:
        builder.metadata.options.sleep = sleep
    if disable_cache:
        builder.metadata.disable_cache = True
    if monitors:
        builder.monitors = {name: orm.Dict(value) for name, value in monitors.items()}
    return builder


def fresh_reads() -> None:
    """Ends the current read transaction, so reads see what the daemon committed (as aiida's control.py does)."""
    from aiida.manage import get_manager

    storage = get_manager().get_profile_storage()
    if hasattr(storage, "get_session"):
        storage.get_session().commit()
