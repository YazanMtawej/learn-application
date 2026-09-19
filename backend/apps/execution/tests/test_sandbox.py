from django.test import SimpleTestCase, override_settings

from apps.execution.sandbox import LocalProcessSandboxRunner


class LocalProcessSandboxRunnerTests(SimpleTestCase):
    def _runner(self, **overrides):
        defaults = dict(
            python_binary="python3",
            timeout_seconds=5,
            cpu_seconds=5,
            memory_bytes=128 * 1024 * 1024,
            pids_limit=32,
            output_limit_bytes=65536,
        )
        defaults.update(overrides)
        return LocalProcessSandboxRunner(**defaults)

    def test_successful_execution_captures_stdout(self):
        runner = self._runner()
        result = runner.run("print('hello world')", stdin_data="")
        self.assertTrue(result.completed)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("hello world", result.stdout)

    def test_stdin_is_passed_to_the_program(self):
        runner = self._runner()
        code = "name = input()\nprint(f'hi {name}')"
        result = runner.run(code, stdin_data="student\n")
        self.assertIn("hi student", result.stdout)

    def test_runtime_exception_yields_nonzero_exit_code(self):
        runner = self._runner()
        result = runner.run("1 / 0", stdin_data="")
        self.assertTrue(result.completed)
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("ZeroDivisionError", result.stderr)

    def test_infinite_loop_times_out(self):
        runner = self._runner(timeout_seconds=1, cpu_seconds=1)
        result = runner.run("while True:\n    pass", stdin_data="")
        self.assertFalse(result.completed)
        self.assertTrue(result.timed_out)

    def test_memory_bomb_is_contained_by_rlimit(self):
        runner = self._runner(memory_bytes=32 * 1024 * 1024, timeout_seconds=5)
        code = "data = [0] * (10 ** 9)"
        result = runner.run(code, stdin_data="")
        # Contained: either the process is killed (non-completed) or it
        # exits with a non-zero code due to MemoryError — either way it
        # must not silently succeed with exit_code 0.
        if result.completed:
            self.assertNotEqual(result.exit_code, 0)

    def test_output_is_truncated_beyond_limit(self):
        runner = self._runner(output_limit_bytes=1024)
        code = "print('a' * 10000)"
        result = runner.run(code, stdin_data="")
        self.assertTrue(result.truncated)
        self.assertIn("[OUTPUT_TRUNCATED]", result.stdout)

    def test_environment_variables_are_stripped(self):
        runner = self._runner()
        code = "import os\nprint(len(os.environ))"
        result = runner.run(code, stdin_data="")
        # Only PATH and PYTHONDONTWRITEBYTECODE are passed through.
        self.assertIn(result.stdout.strip(), {"1", "2"})

    def test_workspace_is_isolated_per_execution(self):
        runner = self._runner()
        code = "import os\nprint(os.getcwd())"
        first = runner.run(code, stdin_data="")
        second = runner.run(code, stdin_data="")
        self.assertNotEqual(first.stdout.strip(), second.stdout.strip())