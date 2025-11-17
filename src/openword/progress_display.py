"""
Rich-based progress display utilities for long-running operations.

This module provides a reusable ProgressDisplay class that uses Rich's Live
display to show updating progress information without scrolling the terminal.
"""

import time
from typing import Dict, Optional, Any
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box


class ProgressDisplay:
    """
    Context manager for displaying live-updating progress metrics.

    Usage:
        with ProgressDisplay("Loading entries") as progress:
            for i, item in enumerate(items):
                progress.update(loaded=i+1, processed=processed_count)
    """

    def __init__(
        self,
        title: str = "Progress",
        refresh_per_second: int = 10,
        update_interval: int = 1000,
        auto_track_time: bool = True
    ):
        """
        Initialize a ProgressDisplay.

        Args:
            title: Title for the progress panel
            refresh_per_second: How many times per second to refresh the display
            update_interval: Update display every N iterations (to reduce overhead)
            auto_track_time: Automatically track elapsed time and rate
        """
        self.title = title
        self.refresh_per_second = refresh_per_second
        self.update_interval = update_interval
        self.auto_track_time = auto_track_time

        self.metrics: Dict[str, Any] = {}
        self.live: Optional[Live] = None
        self.start_time: float = 0
        self.iteration_count: int = 0
        self._primary_metric: Optional[str] = None

    def __enter__(self):
        """Start the live display."""
        self.start_time = time.time()

        if self.auto_track_time:
            self.metrics["Elapsed"] = 0.0

        self.live = Live(
            self._make_panel(),
            refresh_per_second=self.refresh_per_second
        )
        self.live.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop the live display."""
        if self.live:
            # Final update
            self._update_auto_metrics()
            self.live.update(self._make_panel())
            self.live.__exit__(exc_type, exc_val, exc_tb)
        return False

    def update(self, **metrics):
        """
        Update progress metrics.

        Args:
            **metrics: Key-value pairs of metrics to update (e.g., loaded=1000, processed=500)
        """
        self.iteration_count += 1

        # Update metrics
        self.metrics.update(metrics)

        # Track the first metric as primary for rate calculation
        if self._primary_metric is None and metrics:
            self._primary_metric = next(iter(metrics.keys()))

        # Only update display every N iterations to reduce overhead
        if self.iteration_count % self.update_interval == 0:
            self._update_auto_metrics()
            if self.live:
                self.live.update(self._make_panel())

    def _update_auto_metrics(self):
        """Update automatically tracked metrics like elapsed time and rate."""
        if self.auto_track_time:
            elapsed = time.time() - self.start_time
            self.metrics["Elapsed"] = elapsed

            # Calculate rate based on primary metric
            if self._primary_metric and self._primary_metric in self.metrics:
                count = self.metrics[self._primary_metric]
                if elapsed > 0 and isinstance(count, (int, float)):
                    self.metrics["Rate"] = count / elapsed

    def _make_panel(self) -> Panel:
        """Create a Rich panel with the current metrics."""
        grid = Table.grid(padding=(0, 2))
        grid.add_column(justify="left", no_wrap=True)   # Label
        grid.add_column(justify="right", no_wrap=True)  # Value

        for key, value in self.metrics.items():
            label = Text(f"{key}:", style="bold grey50")
            formatted_value = self._format_value(key, value)
            value_text = Text(formatted_value, style="bright_cyan")
            grid.add_row(label, value_text)

        return Panel(
            grid,
            title=self.title,
            box=box.SIMPLE,
            border_style="bright_black"
        )

    def _format_value(self, key: str, value: Any) -> str:
        """Format a metric value for display."""
        if isinstance(value, float):
            if key == "Elapsed":
                # Format as HH:MM:SS or MM:SS
                if value >= 3600:
                    hours = int(value // 3600)
                    minutes = int((value % 3600) // 60)
                    seconds = int(value % 60)
                    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                else:
                    minutes = int(value // 60)
                    seconds = int(value % 60)
                    return f"{minutes:02d}:{seconds:02d}"
            elif key == "Rate" or "rate" in key.lower():
                # Format as rate with unit
                return f"{value:,.1f}/s"
            else:
                # Generic float formatting
                return f"{value:,.2f}"
        elif isinstance(value, int):
            # Format integers with comma separators
            return f"{value:,}"
        else:
            # Default string representation
            return str(value)
