"""Step-by-step progress logging for Prefect runs.

Inside a flow or task run, messages go to Prefect's run logger, so they appear in the run's
Logs tab in the Prefect UI. Outside Prefect (local scripts, tests) they go to the standard logger.
Messages carry all their details inline; Prefect doesn't display `extra=` fields.

    steps = RunSteps("Scrape job #3", total=7)
    with steps.step("Logging in to LinkedIn"):
        ...
    steps.info("Found 12 emails")
    steps.finish("12 emails, 4 posts")
    await steps.publish_report("scrape-job-3")   # summary table on the run's Artifacts tab
"""
import logging
import time
from contextlib import contextmanager
from typing import Iterator, Optional

module_logger = logging.getLogger("gt_linkedin_scraper.runs")


def run_logger() -> logging.Logger | logging.LoggerAdapter:
    """Prefect's logger for the current flow/task run, or a plain logger outside Prefect."""
    try:
        from prefect import get_run_logger

        return get_run_logger()
    except Exception:
        return module_logger


def fmt_duration(seconds: float) -> str:
    return f"{seconds:.1f}s" if seconds < 60 else f"{int(seconds // 60)}m {int(seconds % 60):02d}s"


class StepFailed(Exception):
    """Raised by RunSteps.step after logging, so callers can tell a reported failure apart."""


class RunSteps:
    def __init__(self, title: str, total: int, logger=None) -> None:
        self.title = title
        self.total = total
        self.log = logger or run_logger()
        self.started = time.monotonic()
        self.current = 0
        self.rows: list[tuple[str, str, str, str]] = []  # (#, step, result, duration)
        self.facts: list[tuple[str, str]] = []  # key results for the report
        self.log.info(f"══ {title}: started ══")

    @contextmanager
    def step(self, name: str) -> Iterator["RunSteps"]:
        self.current += 1
        label = f"Step {self.current}/{self.total}"
        self.log.info(f"▶ {label}: {name}")
        start = time.monotonic()
        try:
            yield self
        except Exception as exc:
            took = fmt_duration(time.monotonic() - start)
            self.log.error(f"✗ {label} failed after {took}: {name}: {type(exc).__name__}: {exc}")
            self.rows.append((str(self.current), name, f"❌ {exc}", took))
            raise
        took = fmt_duration(time.monotonic() - start)
        self.log.info(f"✓ {label} done in {took}: {name}")
        self.rows.append((str(self.current), name, "✅", took))

    def info(self, message: str) -> None:
        self.log.info(f"   • {message}")

    def warning(self, message: str) -> None:
        self.log.warning(f"   ⚠ {message}")

    def fact(self, key: str, value) -> None:
        """A headline number for the report (e.g. 'Emails found', 12)."""
        self.facts.append((key, str(value)))

    def skip_remaining(self, reason: str) -> None:
        self.log.info(f"   • Skipping remaining steps: {reason}")

    def finish(self, summary: str, ok: bool = True) -> None:
        took = fmt_duration(time.monotonic() - self.started)
        marker = "finished" if ok else "FAILED"
        log = self.log.info if ok else self.log.error
        log(f"══ {self.title}: {marker} in {took}. {summary} ══")
        self.facts.insert(0, ("Result", ("✅ " if ok else "❌ ") + summary))
        self.facts.insert(1, ("Duration", took))

    def markdown(self) -> str:
        lines = [f"# {self.title}", ""]
        if self.facts:
            lines += ["| | |", "|---|---|"] + [f"| **{k}** | {v} |" for k, v in self.facts] + [""]
        if self.rows:
            lines += ["## Steps", "", "| # | Step | Result | Time |", "|---|---|---|---|"]
            lines += [f"| {n} | {name} | {result.replace('|', '/')} | {took} |" for n, name, result, took in self.rows]
        return "\n".join(lines)

    async def publish_report(self, key: Optional[str] = None) -> None:
        """Attaches the summary to the Prefect run (Artifacts tab). No-op outside Prefect."""
        try:
            from prefect.artifacts import create_markdown_artifact

            await create_markdown_artifact(markdown=self.markdown(), key=key, description=self.title)
        except Exception as exc:  # reporting must never fail a run
            module_logger.debug(f"Run report not published: {exc}")
