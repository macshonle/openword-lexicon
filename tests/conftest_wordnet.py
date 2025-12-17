"""
Extended pytest configuration for WordNet testing.

Provides detailed logging and result collection for version control.
"""

import pytest
import json
import sys
from datetime import datetime
from pathlib import Path


class DetailedTestReporter:
    """Custom reporter that captures detailed test information."""

    def __init__(self):
        self.results = []
        self.start_time = None
        self.end_time = None

    def pytest_runtest_logreport(self, report):
        """Capture test results with full details."""
        if report.when == "call":
            result = {
                "test_id": report.nodeid,
                "outcome": report.outcome,
                "duration": report.duration,
                "keywords": list(report.keywords),
            }

            if report.outcome == "failed":
                result["error"] = {
                    "message": str(report.longrepr),
                    "traceback": str(report.longrepr) if hasattr(report.longrepr, "__str__") else None
                }

            if hasattr(report, "sections"):
                result["output"] = {
                    name: content for name, content in report.sections
                }

            self.results.append(result)

    def pytest_sessionstart(self, session):
        """Record session start time."""
        self.start_time = datetime.utcnow()

    def pytest_sessionfinish(self, session, exitstatus):
        """Save results to file after session."""
        self.end_time = datetime.utcnow()

        # Prepare summary
        summary = {
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": (
                (self.end_time - self.start_time).total_seconds()
                if self.start_time and self.end_time else None
            ),
            "exit_status": exitstatus,
            "python_version": sys.version,
            "test_count": len(self.results),
            "passed": sum(1 for r in self.results if r["outcome"] == "passed"),
            "failed": sum(1 for r in self.results if r["outcome"] == "failed"),
            "skipped": sum(1 for r in self.results if r["outcome"] == "skipped"),
            "results": self.results,
        }

        # Save to file
        output_path = Path("tests/wordnet_test_detailed_results.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        print(f"\n\n{'='*60}")
        print(f"Detailed test results saved to: {output_path}")
        print(f"Total tests: {summary['test_count']}")
        print(f"Passed: {summary['passed']}")
        print(f"Failed: {summary['failed']}")
        print(f"Skipped: {summary['skipped']}")
        print(f"Duration: {summary['duration_seconds']:.2f}s")
        print(f"{'='*60}\n")


@pytest.fixture(scope="session")
def detailed_reporter():
    """Provide detailed reporter instance."""
    return DetailedTestReporter()


def pytest_configure(config):
    """Register custom reporter plugin."""
    if config.option.verbose > 0:
        reporter = DetailedTestReporter()
        config.pluginmanager.register(reporter, "detailed_reporter")
