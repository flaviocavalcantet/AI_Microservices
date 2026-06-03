"""
Dependency injection / application factory for the AI engine.

Two factory functions are provided:

create_engine(db)             – synchronous wiring (Flask + pymongo)
create_async_engine(motor_db) – asyncio wiring     (FastAPI/aiohttp + Motor)

Call the appropriate factory once at application startup.
Both factories share the same task implementations; only the repository
adapter and worker differ between the two.
"""

from __future__ import annotations

from pymongo.database import Database

from ai_engine.application.async_orchestrator import AsyncAIJobOrchestrator
from ai_engine.application.orchestrator import AIJobOrchestrator
from ai_engine.application.services.hf_summarization_service import HFSummarizationService
from ai_engine.application.tasks.dataset_profiling import DatasetProfilingTask
from ai_engine.application.tasks.sentiment_analysis import SentimentAnalysisTask
from ai_engine.application.tasks.summarization import SummarizationTask
from ai_engine.domain.models import AIJobType
from ai_engine.infrastructure.persistence.mongo_repository import MongoAIJobRepository
from ai_engine.infrastructure.persistence.motor_repository import MotorAIJobRepository
from ai_engine.infrastructure.workers.async_job_worker import AsyncAIJobWorker
from ai_engine.infrastructure.workers.job_worker import AIJobWorker

_DEFAULT_SUMMARIZATION_MODEL = "sshleifer/distilbart-cnn-12-6"


# ---------------------------------------------------------------------------
# Synchronous factory (unchanged)
# ---------------------------------------------------------------------------

def create_engine(
    db: Database,
    max_workers: int = 4,
    warmup_summarizer: bool = False,
    summarization_model: str = _DEFAULT_SUMMARIZATION_MODEL,
) -> AIJobWorker:
    """
    Wire all sync dependencies and return a ready-to-use AIJobWorker.

    Args:
        db:                   Connected pymongo Database instance.
        max_workers:          Thread-pool size for background job execution.
        warmup_summarizer:    Load the summarization model eagerly at startup.
        summarization_model:  HuggingFace model ID for summarization.

    Returns:
        Configured AIJobWorker (sync, ThreadPoolExecutor-backed).
    """
    repository = MongoAIJobRepository(db["ai_jobs"])

    summarization_service = HFSummarizationService(model_name=summarization_model)
    if warmup_summarizer:
        summarization_service.warmup()

    task_registry = {
        AIJobType.SUMMARIZATION: SummarizationTask(service=summarization_service),
        AIJobType.SENTIMENT_ANALYSIS: SentimentAnalysisTask(),
        AIJobType.DATASET_PROFILING: DatasetProfilingTask(),
    }

    orchestrator = AIJobOrchestrator(
        repository=repository,
        task_registry=task_registry,
    )

    return AIJobWorker(orchestrator=orchestrator, max_workers=max_workers)


# ---------------------------------------------------------------------------
# Asynchronous factory
# ---------------------------------------------------------------------------

async def create_async_engine(
    motor_db,  # motor.motor_asyncio.AsyncIOMotorDatabase
    max_concurrent: int = 8,
    warmup_summarizer: bool = False,
    summarization_model: str = _DEFAULT_SUMMARIZATION_MODEL,
    on_complete=None,
) -> AsyncAIJobWorker:
    """
    Wire all async dependencies and return a ready-to-use AsyncAIJobWorker.

    This coroutine must be awaited inside a running event loop, e.g. inside
    a FastAPI lifespan handler or an aiohttp startup hook.

    Args:
        motor_db:             Connected Motor AsyncIOMotorDatabase instance.
        max_concurrent:       Semaphore limit for simultaneous job coroutines.
        warmup_summarizer:    Load the summarization model eagerly at startup.
                              Note: model loading is synchronous (HuggingFace);
                              it is offloaded via asyncio.to_thread() here so
                              the event loop is not blocked.
        summarization_model:  HuggingFace model ID for summarization.
        on_complete:          Optional async callback (async def fn(job) → None)
                              called after each job completes or fails.

    Returns:
        Configured AsyncAIJobWorker (asyncio-native, no thread pool).

    Example (FastAPI)::

        from contextlib import asynccontextmanager
        from motor.motor_asyncio import AsyncIOMotorClient

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            client = AsyncIOMotorClient(MONGO_URI)
            app.state.worker = await create_async_engine(client["mydb"])
            yield
            await app.state.worker.shutdown()
    """
    import asyncio

    repository = MotorAIJobRepository(motor_db["ai_jobs"])
    await repository.ensure_indexes()

    summarization_service = HFSummarizationService(model_name=summarization_model)
    if warmup_summarizer:
        # HuggingFace pipeline loading is CPU-bound / blocking; offload it.
        await asyncio.to_thread(summarization_service.warmup)

    task_registry = {
        AIJobType.SUMMARIZATION: SummarizationTask(service=summarization_service),
        AIJobType.SENTIMENT_ANALYSIS: SentimentAnalysisTask(),
        AIJobType.DATASET_PROFILING: DatasetProfilingTask(),
    }

    orchestrator = AsyncAIJobOrchestrator(
        repository=repository,
        task_registry=task_registry,
    )

    return AsyncAIJobWorker(
        orchestrator=orchestrator,
        max_concurrent=max_concurrent,
        on_complete=on_complete,
    )
