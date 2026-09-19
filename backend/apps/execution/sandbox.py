"""
Sandbox execution layer for TASK 4.

KNOWN LIMITATION (documented, not hidden — see TASK 4 Security Review):

Phase 9 §4-§9 mandates gVisor (runsc) + Zero Network Namespace +
ephemeral non-root containers as the actual security boundary for
untrusted student code, with Worker-Host provisioning explicitly
assigned to Phase 29 (Deployment infrastructure).

The LocalProcessSandboxRunner below is an interim MVP implementation
using OS-level POSIX resource limits (CPU time, address space,
process count, file-size) plus an isolated temporary workspace and
a stripped environment.

It does NOT provide:

- network isolation
- filesystem namespace isolation
- privilege separation from the Celery worker's OS user

The LocalProcessSandboxRunner is therefore intended for Linux/POSIX
worker environments only.

On Windows, the module remains importable so that Django management
commands such as `python manage.py check` can run successfully, but
the LocalProcessSandboxRunner refuses execution because the required
POSIX security primitives are unavailable.

SandboxRunner is an abstract interface specifically so a real
gVisor-backed runner can be substituted at Phase 29 without changing
apps/execution/services.py, apps/execution/tasks.py, or any API contract.
"""

import abc
import dataclasses
import os
import subprocess
import tempfile

try:
    import resource
except ImportError:
    resource = None


@dataclasses.dataclass
class SandboxRunResult:
    completed: bool
    timed_out: bool
    system_error: bool
    exit_code: int | None
    stdout: str
    stderr: str
    truncated: bool


class SandboxRunner(abc.ABC):
    @abc.abstractmethod
    def run(self, code: str, stdin_data: str) -> SandboxRunResult:
        ...


class LocalProcessSandboxRunner(SandboxRunner):
    """
    MVP sandbox runner.

    This runner requires a POSIX/Linux environment because its security
    controls depend on the Python `resource` module and `preexec_fn`.

    See the module docstring for the security limitations relative to
    the approved Phase 9 architecture.
    """

    def __init__(
        self,
        python_binary: str,
        timeout_seconds: int,
        cpu_seconds: int,
        memory_bytes: int,
        pids_limit: int,
        output_limit_bytes: int,
    ):
        self.python_binary = python_binary
        self.timeout_seconds = timeout_seconds
        self.cpu_seconds = cpu_seconds
        self.memory_bytes = memory_bytes
        self.pids_limit = pids_limit
        self.output_limit_bytes = output_limit_bytes

    def _ensure_posix_support(self) -> None:
        """
        Ensure the required POSIX security primitives are available.

        Windows must not silently fall back to an unrestricted subprocess.
        """
        if os.name != "posix" or resource is None:
            raise RuntimeError(
                "LocalProcessSandboxRunner requires a POSIX/Linux "
                "environment. Windows is not a supported execution "
                "worker environment for the local sandbox."
            )

    def _preexec(self):
        self._ensure_posix_support()

        cpu_seconds = self.cpu_seconds
        memory_bytes = self.memory_bytes
        pids_limit = self.pids_limit
        output_limit_bytes = self.output_limit_bytes

        def _apply():
            os.setsid()

            resource.setrlimit(
                resource.RLIMIT_CPU,
                (cpu_seconds, cpu_seconds),
            )

            resource.setrlimit(
                resource.RLIMIT_AS,
                (memory_bytes, memory_bytes),
            )

            resource.setrlimit(
                resource.RLIMIT_NPROC,
                (pids_limit, pids_limit),
            )

            resource.setrlimit(
                resource.RLIMIT_FSIZE,
                (output_limit_bytes, output_limit_bytes),
            )

        return _apply

    def _truncate(self, text: str) -> tuple[str, bool]:
        data = text.encode("utf-8", errors="replace")

        if len(data) <= self.output_limit_bytes:
            return text, False

        truncated = data[
            : self.output_limit_bytes
        ].decode("utf-8", errors="ignore")

        return truncated + "\n[OUTPUT_TRUNCATED]", True

    def run(self, code: str, stdin_data: str) -> SandboxRunResult:
        self._ensure_posix_support()

        with tempfile.TemporaryDirectory(prefix="exec_") as workspace:
            code_path = os.path.join(workspace, "submission.py")

            with open(code_path, "w", encoding="utf-8") as handle:
                handle.write(code)

            # Zero-knowledge environment (Phase 9 §6/§14):
            # no inherited environment variables from the worker process,
            # no secrets, and only the minimum PATH required to invoke
            # the interpreter.
            env = {
                "PATH": "/usr/bin:/bin",
                "PYTHONDONTWRITEBYTECODE": "1",
            }

            try:
                process = subprocess.run(
                    [
                        self.python_binary,
                        "-I",
                        "-B",
                        code_path,
                    ],
                    input=stdin_data,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                    cwd=workspace,
                    env=env,
                    preexec_fn=self._preexec(),
                )

            except subprocess.TimeoutExpired:
                return SandboxRunResult(
                    completed=False,
                    timed_out=True,
                    system_error=False,
                    exit_code=None,
                    stdout="",
                    stderr="",
                    truncated=False,
                )

            except OSError:
                return SandboxRunResult(
                    completed=False,
                    timed_out=False,
                    system_error=True,
                    exit_code=None,
                    stdout="",
                    stderr="",
                    truncated=False,
                )

            stdout, truncated_out = self._truncate(process.stdout)
            stderr, truncated_err = self._truncate(process.stderr)

            return SandboxRunResult(
                completed=True,
                timed_out=False,
                system_error=False,
                exit_code=process.returncode,
                stdout=stdout,
                stderr=stderr,
                truncated=truncated_out or truncated_err,
            )


def build_sandbox_runner() -> SandboxRunner:
    from django.conf import settings

    return LocalProcessSandboxRunner(
        python_binary=settings.EXECUTION_PYTHON_BINARY,
        timeout_seconds=settings.EXECUTION_TIMEOUT_SECONDS,
        cpu_seconds=settings.EXECUTION_CPU_SECONDS,
        memory_bytes=settings.EXECUTION_MEMORY_LIMIT_BYTES,
        pids_limit=settings.EXECUTION_PIDS_LIMIT,
        output_limit_bytes=settings.EXECUTION_OUTPUT_LIMIT_BYTES,
    )