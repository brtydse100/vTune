"""Compatibility alias for the former :mod:`vtune` package."""

from __future__ import annotations

import vllm_optimizer as _canonical
from vllm_optimizer import Orchestrator, RunOutcome, __version__

# Keep legacy submodule imports working for one deprecation cycle.
__path__ = _canonical.__path__

__all__ = ["Orchestrator", "RunOutcome"]
