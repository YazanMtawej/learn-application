from celery import shared_task

from apps.execution.services import ExecutionRunnerService


@shared_task(bind=True, max_retries=0, ignore_result=True)
def run_exercise_attempt(self, attempt_id: str):
    """
    Async execution entrypoint (Phase 6 §7.J: Code Execution is
    mandatory Async via Queue + Worker). max_retries=0 because
    automatic retry after a terminal result exists is forbidden
    (Phase 9 ADR-9.4) — ExecutionRunnerService.run_attempt is itself
    idempotent no-op on retry attempts from infrastructure-level replay.
    """
    ExecutionRunnerService.run_attempt(attempt_id)