"""Reusable HuggingFace model download & cache utility.

Every ``WorkloadRunner`` that depends on a HuggingFace model should call
``ensure_model_available()`` before first inference.  The function is
idempotent — if the model is already in the local HF cache it returns
instantly; otherwise it triggers a one-time download.

Cache location
--------------
Controlled by the ``HF_HOME`` environment variable (set in
docker-compose.yml).  Falls back to ``~/.cache/huggingface`` — the
default used by the ``transformers`` and ``huggingface_hub`` libraries.

Thread safety
-------------
``snapshot_download`` is safe to call concurrently from multiple Celery
worker threads; the ``huggingface_hub`` library handles file-level
locking internally.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def ensure_model_available(
    repo_id: str,
    *,
    revision: str = "main",
    cache_dir: Optional[str] = None,
) -> str:
    """Ensure a HuggingFace model is present in the local cache.

    Args:
        repo_id:   HuggingFace Hub repository ID
                   (e.g. ``"distilbert-base-uncased-finetuned-sst-2-english"``).
        revision:  Git revision (branch, tag, or commit SHA).  Defaults to
                   ``"main"``.
        cache_dir: Override the cache directory.  When *None* the standard
                   ``HF_HOME`` / ``TRANSFORMERS_CACHE`` environment variables
                   are respected.

    Returns:
        The absolute path to the cached snapshot directory.

    Raises:
        ModelDownloadError: If the download fails for any reason (network,
            disk, invalid repo, etc.).
    """
    try:
        from huggingface_hub import snapshot_download  # type: ignore[import]
    except ImportError as exc:
        raise ModelDownloadError(
            "The 'huggingface_hub' package is required for model downloads. "
            "Run: pip install huggingface_hub"
        ) from exc

    effective_cache = cache_dir or os.environ.get("HF_HOME")
    cache_label = effective_cache or "(default ~/.cache/huggingface)"

    # ------------------------------------------------------------------
    # Fast path: try a local-only resolve first (no network at all)
    # ------------------------------------------------------------------
    try:
        local_path = snapshot_download(
            repo_id,
            revision=revision,
            cache_dir=effective_cache,
            local_files_only=True,
        )
        logger.info(
            "Model '%s' already cached at %s", repo_id, local_path,
        )
        return str(local_path)
    except Exception:
        # Not cached yet — fall through to download.
        logger.info(
            "Model '%s' not found in cache (%s), downloading…",
            repo_id,
            cache_label,
        )

    # ------------------------------------------------------------------
    # Slow path: download from HuggingFace Hub
    # ------------------------------------------------------------------
    t0 = time.perf_counter()
    try:
        local_path = snapshot_download(
            repo_id,
            revision=revision,
            cache_dir=effective_cache,
        )
    except Exception as exc:
        raise ModelDownloadError(
            f"Failed to download model '{repo_id}' (revision={revision}): {exc}"
        ) from exc

    elapsed_s = round(time.perf_counter() - t0, 1)
    logger.info(
        "Model '%s' downloaded in %.1fs → %s", repo_id, elapsed_s, local_path,
    )
    return str(local_path)


def get_cache_dir() -> str:
    """Return the effective HuggingFace cache directory path."""
    return os.environ.get("HF_HOME", str(Path.home() / ".cache" / "huggingface"))


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class ModelDownloadError(RuntimeError):
    """Raised when a model download or cache lookup fails."""
