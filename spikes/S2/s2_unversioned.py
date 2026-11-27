"""A monitor in a module without __version__, to show that aiida-core 2.9.4 refuses it at job creation (S2).

The same observe-only function as s2_processes.observe; registered as the entry point s2.observe_unversioned.
"""

from typing import Any


def observe(node: Any, transport: Any, **kwargs: Any) -> None:
    return None
