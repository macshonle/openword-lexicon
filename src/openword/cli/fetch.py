#!/usr/bin/env python3
"""
owfetch — Unified source fetcher for OpenWord Lexicon

Fetches data sources defined in sources.yaml with progress feedback,
error handling, and SOURCE.json metadata generation.

Usage:
    owfetch                     # Fetch default sources
    owfetch wordnet             # Fetch specific source
    owfetch --list              # List available sources
    owfetch --force             # Re-download even if exists
    owfetch --group profanity   # Fetch a group
    owfetch --all               # Fetch all sources
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import select
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from glob import glob
from pathlib import Path
from typing import Any
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

import yaml

# ==============================================================================
# Constants
# ==============================================================================

# Find project root (from src/openword/cli/)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

# Sources configuration (schema-driven)
SOURCES_DIR = PROJECT_ROOT / "schema" / "sources"
SOURCES_INDEX = SOURCES_DIR / "index.yaml"

# CI mode detection
CI_MODE = os.environ.get("CI") == "true" or os.environ.get("OPENWORD_CI") == "1"

# Terminal colors (disabled in CI mode or non-TTY)
USE_COLOR = sys.stdout.isatty() and not CI_MODE


def color(code: str, text: str) -> str:
    """Apply ANSI color code if colors are enabled."""
    if USE_COLOR:
        return f"\033[{code}m{text}\033[0m"
    return text


RED = lambda t: color("0;31", t)
GREEN = lambda t: color("0;32", t)
YELLOW = lambda t: color("1;33", t)
BLUE = lambda t: color("0;34", t)
BOLD = lambda t: color("1", t)
DIM = lambda t: color("2", t)


# ==============================================================================
# Utilities
# ==============================================================================


def compute_sha256(path: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def get_file_size(path: Path) -> int:
    """Get file size in bytes."""
    return path.stat().st_size


def format_size(size_bytes: int) -> str:
    """Format bytes as human-readable size."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}" if unit != "B" else f"{size_bytes} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def get_file_age_days(path: Path) -> int:
    """Get file age in days."""
    mtime = path.stat().st_mtime
    age_seconds = datetime.now().timestamp() - mtime
    return int(age_seconds / 86400)


def count_lines(path: Path, skip_header: int = 0) -> int:
    """Count lines in a file, optionally skipping header lines."""
    with open(path, "rb") as f:
        count = sum(1 for _ in f)
    return max(0, count - skip_header)


def interpolate_vars(value: str, variables: dict[str, str]) -> str:
    """Interpolate {var} placeholders in a string."""
    if not isinstance(value, str):
        return value
    for key, val in variables.items():
        value = value.replace(f"{{{key}}}", val)
    return value


# ==============================================================================
# Download Functions
# ==============================================================================


def download_file(
    url: str,
    dest: Path,
    *,
    resume: bool = False,
    show_progress: bool = True,
    large_file: bool = False,
) -> bool:
    """
    Download a file from URL to destination.

    Returns True on success, False on failure.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Check for partial download (resume support)
    start_byte = 0
    if resume and dest.exists():
        start_byte = dest.stat().st_size

    headers = {"User-Agent": "OpenWord-Lexicon/1.0"}
    if start_byte > 0:
        headers["Range"] = f"bytes={start_byte}-"

    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=30) as response:
            # Get total size from Content-Length or Content-Range
            total_size = None
            content_length = response.headers.get("Content-Length")
            content_range = response.headers.get("Content-Range")

            if content_range:
                # Format: bytes start-end/total
                total_size = int(content_range.split("/")[-1])
            elif content_length:
                total_size = int(content_length) + start_byte

            # Open file in append mode if resuming
            mode = "ab" if start_byte > 0 else "wb"
            downloaded = start_byte

            with open(dest, mode) as f:
                chunk_size = 8192 if not large_file else 65536
                last_percent = -1

                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)

                    # Show progress
                    if show_progress and total_size:
                        percent = int(downloaded * 100 / total_size)
                        if percent != last_percent:
                            bar_width = 30
                            filled = int(bar_width * percent / 100)
                            bar = "━" * filled + "╺" + "─" * (bar_width - filled - 1)
                            size_str = format_size(downloaded)
                            sys.stdout.write(
                                f"\r      {bar} {percent:3d}% {size_str}  "
                            )
                            sys.stdout.flush()
                            last_percent = percent

            if show_progress and total_size:
                print()  # Newline after progress bar

        return True

    except HTTPError as e:
        print(f"\n      {RED('Error')}: HTTP {e.code} - {e.reason}")
        return False
    except URLError as e:
        print(f"\n      {RED('Error')}: {e.reason}")
        return False
    except TimeoutError:
        print(f"\n      {RED('Error')}: Connection timed out")
        return False


def clone_repo(
    repo_url: str,
    dest: Path,
    *,
    tag: str | None = None,
    shallow: bool = True,
    activity_timeout: int = 120,  # Timeout if no progress for this many seconds
) -> tuple[bool, str | None]:
    """
    Clone a git repository with activity-based timeout.

    Instead of a fixed timeout, we monitor git's progress output and only
    timeout if no progress is made for `activity_timeout` seconds. This
    allows slow but steady downloads to complete.

    Returns (success, commit_hash).
    """
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing directory
    if dest.exists():
        shutil.rmtree(dest)

    # Build git clone command
    cmd = ["git", "clone"]
    if shallow:
        cmd.extend(["--depth", "1"])
    if tag:
        cmd.extend(["--branch", tag])
    cmd.extend(["--progress", repo_url, str(dest)])

    # Disable git prompts
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"

    process: subprocess.Popen[bytes] | None = None
    try:
        # Use Popen to stream stderr and monitor for activity
        process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        last_activity = time.time()
        stderr_output: list[bytes] = []
        stderr = process.stderr
        assert stderr is not None  # We set stderr=PIPE above

        while True:
            # Check if process has finished
            retcode = process.poll()
            if retcode is not None:
                break

            # Wait for output with timeout
            ready, _, _ = select.select([stderr], [], [], 1.0)

            if ready:
                # Read available data (non-blocking since select said it's ready)
                chunk = stderr.read(1024)
                if chunk:
                    last_activity = time.time()
                    stderr_output.append(chunk)
                    # Show progress to terminal if interactive
                    if sys.stdout.isatty():
                        sys.stderr.buffer.write(chunk)
                        sys.stderr.buffer.flush()

            # Check for activity timeout
            if time.time() - last_activity > activity_timeout:
                process.kill()
                process.wait()
                print(f"\n      {RED('Error')}: git clone stalled (no progress for {activity_timeout}s)")
                if dest.exists():
                    shutil.rmtree(dest)
                return False, None

        # Process finished - check return code
        if retcode != 0:
            print(f"      {RED('Error')}: git clone failed")
            stderr_text = b"".join(stderr_output).decode("utf-8", errors="replace")
            if stderr_text:
                for line in stderr_text.strip().split("\n")[:3]:
                    print(f"      {DIM(line)}")
            return False, None

        # Get commit hash
        git_dir = dest / ".git"
        if git_dir.exists():
            head_file = git_dir / "HEAD"
            if head_file.exists():
                ref = head_file.read_text().strip()
                if ref.startswith("ref: "):
                    ref_path = git_dir / ref[5:]
                    if ref_path.exists():
                        commit = ref_path.read_text().strip()
                        return True, commit
                else:
                    return True, ref

        return True, None

    except Exception as e:
        print(f"      {RED('Error')}: {e}")
        # Clean up process if still running
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()
        if dest.exists():
            shutil.rmtree(dest)
        return False, None


# ==============================================================================
# Post-Processing
# ==============================================================================


def post_process_concatenate(
    temp_dir: Path, output_file: Path, pattern: str, variables: dict[str, str]
) -> bool:
    """Concatenate files matching a glob pattern."""
    pattern = interpolate_vars(pattern, variables)
    full_pattern = str(temp_dir / pattern)
    files = sorted(glob(full_pattern))

    if not files:
        print(f"      {RED('Error')}: No files match pattern: {pattern}")
        return False

    print(f"      Concatenating {len(files)} files...")
    with open(output_file, "wb") as out:
        for f in files:
            with open(f, "rb") as inp:
                out.write(inp.read())

    return True


def post_process_find_file(
    temp_dir: Path, output_file: Path, patterns: list[str], variables: dict[str, str]
) -> bool:
    """Find and copy a file matching one of the patterns."""
    for pattern in patterns:
        pattern = interpolate_vars(pattern, variables)
        full_path = temp_dir / pattern

        # Try exact path first
        if full_path.exists():
            shutil.copy2(full_path, output_file)
            return True

        # Try glob pattern
        matches = list(glob(str(temp_dir / pattern)))
        if matches:
            shutil.copy2(matches[0], output_file)
            return True

    # Last resort: recursive search
    for pattern in patterns:
        pattern = interpolate_vars(pattern, variables)
        filename = Path(pattern).name
        for match in temp_dir.rglob(filename):
            if match.is_file():
                shutil.copy2(match, output_file)
                return True

    print(f"      {RED('Error')}: Could not find file matching patterns")
    return False


def post_process_archive(temp_dir: Path, output_file: Path) -> bool:
    """Create a tar.gz archive of the directory."""
    print("      Creating archive...")
    try:
        with tarfile.open(output_file, "w:gz") as tar:
            tar.add(temp_dir, arcname=".")
        return True
    except Exception as e:
        print(f"      {RED('Error')}: Failed to create archive: {e}")
        return False


# ==============================================================================
# SOURCE.json Generation
# ==============================================================================


def write_source_json(
    source_config: dict[str, Any],
    output_file: Path,
    source_json_path: Path,
    *,
    checksum: str,
    file_size: int,
    entry_count: int | None = None,
    git_commit: str | None = None,
    git_tag: str | None = None,
) -> None:
    """Write SOURCE.json metadata file."""
    metadata = {
        "name": source_config.get("name", "Unknown"),
        "title": source_config.get("title", ""),
    }

    # Add metadata fields from config
    if "metadata" in source_config:
        for key, value in source_config["metadata"].items():
            metadata[key] = value

    # Add URL/repo info
    if "url" in source_config:
        metadata["url"] = source_config["url"]
    if "repo" in source_config:
        metadata["url"] = source_config["repo"]

    # Add git info
    if git_commit:
        metadata["git_commit"] = git_commit
    if git_tag:
        metadata["git_tag"] = git_tag

    # Add license info
    if "license" in source_config:
        metadata["license"] = source_config["license"]
    if "license_url" in source_config:
        metadata["license_url"] = source_config["license_url"]
    if "license_text" in source_config:
        metadata["license_text"] = source_config["license_text"]
    if "license_note" in source_config:
        metadata["license_note"] = source_config["license_note"]
    if "attribution" in source_config:
        metadata["attribution"] = source_config["attribution"]

    # Add file info
    metadata["sha256"] = checksum
    metadata["file_size_bytes"] = file_size

    if entry_count is not None:
        metadata["entry_count"] = entry_count

    # Add format info
    if "format" in source_config:
        metadata["format"] = source_config["format"]
    metadata["encoding"] = "UTF-8"

    if "notes" in source_config:
        metadata["notes"] = source_config["notes"]

    metadata["downloaded_at"] = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    with open(source_json_path, "w") as f:
        json.dump(metadata, f, indent=2)
        f.write("\n")


# ==============================================================================
# Source Fetching
# ==============================================================================


def fetch_source(
    source_id: str,
    source_config: dict[str, Any],
    variables: dict[str, str],
    *,
    force: bool = False,
    dry_run: bool = False,
) -> tuple[str, str | None]:
    """
    Fetch a single source.

    Returns (status, message) where status is one of:
    - "fetched": Successfully downloaded
    - "skipped": Already exists (or dry run)
    - "failed": Error occurred
    """
    # Interpolate variables in config values
    output_dir = source_config.get("output_dir", f"data/raw/{variables['lang']}")
    output_dir = interpolate_vars(output_dir, variables)
    output_file = interpolate_vars(source_config["output"], variables)

    output_path = PROJECT_ROOT / output_dir / output_file
    source_json_name = f"{source_id}.SOURCE.json"
    source_json_path = output_path.parent / source_json_name

    # Check if already exists
    if output_path.exists() and source_json_path.exists() and not force:
        # Check max_age_days for time-sensitive sources
        max_age = source_config.get("max_age_days")
        if max_age:
            age = get_file_age_days(output_path)
            if age < max_age:
                return "skipped", f"Already exists ({age} days old, max {max_age})"
        else:
            return "skipped", "Already exists"

    if dry_run:
        method = source_config.get("method", "http")
        if method == "http":
            return "skipped", f"Would download from {source_config.get('url')}"
        else:
            return "skipped", f"Would clone from {source_config.get('repo')}"

    # Create output directory
    output_path.parent.mkdir(parents=True, exist_ok=True)

    method = source_config.get("method", "http")
    git_commit = None
    git_tag = source_config.get("tag")

    if method == "http":
        # HTTP download
        url = source_config["url"]
        resume = source_config.get("resume", False)
        large_file = source_config.get("large_file", False)

        success = download_file(
            url, output_path, resume=resume, large_file=large_file
        )
        if not success:
            return "failed", "Download failed"

    elif method == "git":
        # Git clone with post-processing
        repo = source_config["repo"]

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "repo"

            print(f"      Cloning repository...")
            success, git_commit = clone_repo(repo, temp_path, tag=git_tag)
            if not success:
                return "failed", "Clone failed"

            # Post-processing
            post_process = source_config.get("post_process", {})
            pp_type = post_process.get("type") if isinstance(post_process, dict) else None

            if pp_type == "concatenate":
                pattern = post_process["pattern"]
                if not post_process_concatenate(temp_path, output_path, pattern, variables):
                    return "failed", "Post-processing failed"

            elif pp_type == "find_file":
                patterns = post_process["patterns"]
                if not post_process_find_file(temp_path, output_path, patterns, variables):
                    return "failed", "Could not find source file"

            elif pp_type == "archive":
                if not post_process_archive(temp_path, output_path):
                    return "failed", "Archive creation failed"

            else:
                # No post-processing needed - this shouldn't happen for git sources
                return "failed", "Git source missing post_process configuration"

    else:
        return "failed", f"Unknown method: {method}"

    # Verify output
    if not output_path.exists() or output_path.stat().st_size == 0:
        return "failed", "Output file is empty or missing"

    # Compute metadata
    print(f"      Computing checksum...")
    checksum = compute_sha256(output_path)
    file_size = get_file_size(output_path)

    # Count entries if applicable
    entry_count = None
    if output_path.suffix in (".txt", ".tsv", ".csv"):
        header_lines = source_config.get("count_header_lines", 0)
        entry_count = count_lines(output_path, header_lines)

    # Write SOURCE.json
    write_source_json(
        source_config,
        output_path,
        source_json_path,
        checksum=checksum,
        file_size=file_size,
        entry_count=entry_count,
        git_commit=git_commit,
        git_tag=git_tag,
    )

    # Build success message
    size_str = format_size(file_size)
    if entry_count:
        msg = f"{entry_count:,} entries | {size_str}"
    else:
        msg = size_str
    msg += f" | sha256:{checksum[:12]}..."

    return "fetched", msg


def show_interactive_warning(sources: list[tuple[str, dict]]) -> bool:
    """Show interactive warning for flagged sources. Returns True to proceed."""
    if CI_MODE:
        print(f"      {YELLOW('CI mode')}: Auto-confirming download")
        return True

    # Collect warnings from all sources
    warnings = set()
    for _, config in sources:
        if "warning" in config:
            warnings.add(config["warning"].strip())

    if not warnings:
        return True

    # Print warning banner
    line = "━" * 66
    print(f"\n{RED(line)}")
    print(f"{RED('⚠️  WARNING: EXPLICIT/SENSITIVE CONTENT  ⚠️')}")
    print(f"{RED(line)}\n")

    for warning in warnings:
        for line in warning.strip().split("\n"):
            print(f"{YELLOW(line)}")
    print()

    try:
        input(f"{RED('Press Enter to continue or Ctrl+C to cancel...')}")
        print()
        return True
    except KeyboardInterrupt:
        print("\nCancelled.")
        return False


# ==============================================================================
# Main
# ==============================================================================


def load_source_schema(source_id: str, schema_file: str | None = None) -> dict[str, Any] | None:
    """Load a single source schema file."""
    if schema_file:
        schema_path = SOURCES_DIR / schema_file
    else:
        schema_path = SOURCES_DIR / f"{source_id}.yaml"

    if schema_path.exists():
        with open(schema_path) as f:
            return yaml.safe_load(f)
    return None


def load_sources() -> dict[str, Any]:
    """
    Load sources configuration from schema/sources/.

    Merges index.yaml with individual source schema files to produce
    a unified configuration compatible with the fetch logic.
    """
    # Load the index
    with open(SOURCES_INDEX) as f:
        index = yaml.safe_load(f)

    settings = index.get("settings", {})
    groups = index.get("groups", {})
    source_refs = index.get("sources", {})

    # Build the merged sources dict
    sources: dict[str, Any] = {}

    for source_id, source_ref in source_refs.items():
        # Load the full schema for this source
        schema_file = source_ref.get("schema") if isinstance(source_ref, dict) else None
        source_schema = load_source_schema(source_id, schema_file)

        if source_schema is None:
            print(f"{YELLOW('Warning')}: No schema found for source: {source_id}")
            continue

        # Merge: schema provides base, index entry provides overrides
        merged = {}

        # Copy base info from schema
        merged["name"] = source_schema.get("name", source_id)
        merged["title"] = source_schema.get("title", "")

        # Copy fetch config
        fetch = source_schema.get("fetch", {})
        merged["method"] = fetch.get("method", "http")
        merged["url"] = fetch.get("url")
        merged["repo"] = fetch.get("repo")
        merged["output"] = fetch.get("output")
        merged["format"] = fetch.get("format")
        merged["tag"] = fetch.get("tag")

        # Post-processing
        if "post_process" in fetch:
            merged["post_process"] = fetch["post_process"]

        # Attribution/license from schema
        attribution = source_schema.get("attribution", {})
        merged["license"] = attribution.get("license")
        merged["license_url"] = attribution.get("license_url")
        merged["license_text"] = attribution.get("license_text")
        merged["attribution"] = attribution.get("attribution_text")

        # Metadata
        if "metadata" in source_schema:
            merged["metadata"] = source_schema["metadata"]

        # Data characteristics
        data = source_schema.get("data", {})
        if "notes" in source_schema.get("data", {}):
            merged["notes"] = data.get("description", "")

        # Apply overrides from index entry
        if isinstance(source_ref, dict):
            if source_ref.get("large_file"):
                merged["large_file"] = True
            if source_ref.get("max_age_days"):
                merged["max_age_days"] = source_ref["max_age_days"]
            if source_ref.get("resume"):
                merged["resume"] = True
            if source_ref.get("interactive"):
                merged["interactive"] = True
            if source_ref.get("skip_in_default"):
                merged["skip_in_default"] = True
            if source_ref.get("group"):
                merged["group"] = source_ref["group"]
            if source_ref.get("output_dir"):
                merged["output_dir"] = source_ref["output_dir"]
            if source_ref.get("warning"):
                merged["warning"] = source_ref["warning"]

        sources[source_id] = merged

    return {
        "settings": settings,
        "groups": groups,
        "sources": sources,
    }


def list_sources(config: dict[str, Any]) -> None:
    """Print available sources."""
    settings = config.get("settings", {})
    sources = config.get("sources", {})

    print(f"\n{BOLD('Available sources:')}\n")

    # Group sources
    default_sources = []
    grouped_sources: dict[str, list] = {}

    for source_id, source_config in sources.items():
        group = source_config.get("group")
        if group:
            grouped_sources.setdefault(group, []).append((source_id, source_config))
        elif not source_config.get("skip_in_default"):
            default_sources.append((source_id, source_config))

    # Print default sources
    print(f"  {BOLD('Default sources')} (fetched with no arguments):")
    for source_id, source_config in default_sources:
        name = source_config.get("name", source_id)
        print(f"    {GREEN(source_id):20} {name}")

    # Print grouped sources
    for group, group_sources in grouped_sources.items():
        print(f"\n  {BOLD(f'Group: {group}')} (use --group {group}):")
        for source_id, source_config in group_sources:
            name = source_config.get("name", source_id)
            print(f"    {YELLOW(source_id):20} {name}")

    print()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch data sources for OpenWord Lexicon",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "sources",
        nargs="*",
        help="Specific sources to fetch (default: all non-skipped sources)",
    )
    parser.add_argument(
        "--list", "-l", action="store_true", help="List available sources"
    )
    parser.add_argument(
        "--force", "-f", action="store_true", help="Re-download even if exists"
    )
    parser.add_argument(
        "--dry-run", "-n", action="store_true", help="Show what would be done"
    )
    parser.add_argument(
        "--group", "-g", help="Fetch all sources in a group (e.g., profanity)"
    )
    parser.add_argument(
        "--all", "-a", action="store_true", help="Fetch all sources including skipped"
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue fetching other sources if one fails",
    )

    args = parser.parse_args()

    # Load configuration
    config = load_sources()
    settings = config.get("settings", {})
    all_sources = config.get("sources", {})

    # Handle --list
    if args.list:
        list_sources(config)
        return 0

    # Build variables for interpolation
    lang = os.environ.get("LEXICON_LANG", settings.get("lang", "en"))
    variables = {"lang": lang}

    # Determine which sources to fetch
    sources_to_fetch: list[tuple[str, dict]] = []

    if args.sources:
        # Specific sources requested
        for source_id in args.sources:
            if source_id not in all_sources:
                print(f"{RED('Error')}: Unknown source: {source_id}")
                print("Use --list to see available sources")
                return 1
            sources_to_fetch.append((source_id, all_sources[source_id]))

    elif args.group:
        # Fetch all sources in a group
        for source_id, source_config in all_sources.items():
            if source_config.get("group") == args.group:
                sources_to_fetch.append((source_id, source_config))
        if not sources_to_fetch:
            print(f"{RED('Error')}: No sources found in group: {args.group}")
            return 1

    elif args.all:
        # Fetch all sources
        sources_to_fetch = list(all_sources.items())

    else:
        # Default: fetch non-skipped sources
        for source_id, source_config in all_sources.items():
            if not source_config.get("skip_in_default"):
                sources_to_fetch.append((source_id, source_config))

    if not sources_to_fetch:
        print("No sources to fetch.")
        return 0

    # Check for interactive sources
    interactive_sources = [
        (sid, cfg) for sid, cfg in sources_to_fetch if cfg.get("interactive")
    ]
    if interactive_sources:
        if not show_interactive_warning(interactive_sources):
            return 1

    # Fetch sources
    total = len(sources_to_fetch)
    fetched = 0
    skipped = 0
    failed = 0

    print(f"\n{BOLD(f'Fetching sources ({total})...')}")

    try:
        for i, (source_id, source_config) in enumerate(sources_to_fetch, 1):
            name = source_config.get("name", source_id)
            title = source_config.get("title", "")
            title_display = title[:50] + '...' if len(title) > 50 else title

            print(f"[{i}/{total}] {BOLD(source_id)} {DIM(title_display)}")

            status, message = fetch_source(
                source_id,
                source_config,
                variables,
                force=args.force,
                dry_run=args.dry_run,
            )

            if status == "fetched":
                print(f"      -> {GREEN('OK')} {message}")
                fetched += 1
            elif status == "skipped":
                print(f"      -> {message}")
                skipped += 1
            else:  # failed
                print(f"      -> {RED('ERROR')} {message}")
                failed += 1
                if not args.continue_on_error:
                    print(f"{RED('Aborting due to error.')}")
                    print("Use --continue-on-error to fetch remaining sources.")
                    return 1

    except KeyboardInterrupt:
        print(f"\n\n{YELLOW('Interrupted.')} Partial downloads may remain.")
        print("Re-run to resume (resumable sources will continue where they left off).")
        return 130  # Standard exit code for SIGINT

    # Summary
    summary_parts = []
    if fetched:
        summary_parts.append(f"{GREEN(f'{fetched} fetched')}")
    if skipped:
        summary_parts.append(f"{BLUE(f'{skipped} skipped')}")
    if failed:
        summary_parts.append(f"{RED(f'{failed} failed')}")

    status_icon = GREEN("OK") if failed == 0 else RED("ERROR")
    print(f"\n{status_icon} Complete: {', '.join(summary_parts)}")

    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
