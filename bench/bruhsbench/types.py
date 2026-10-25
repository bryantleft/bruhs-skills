from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Arm = Literal["bare", "bruhs"]
Cli = Literal["claude", "codex", "grok"]
Category = Literal["feature", "debug", "audit", "ui", "copy", "pr-review", "ship"]

CATEGORIES: tuple[str, ...] = (
    "feature", "debug", "audit", "ui", "copy", "pr-review", "ship",
)


@dataclass(frozen=True)
class ModelSpec:
    cli: Cli
    model: str
    effort: str


MODELS: tuple[ModelSpec, ...] = (
    ModelSpec("claude", "claude-opus-5-5", "high"),
    ModelSpec("codex", "gpt-6.1-sol", "high"),
    ModelSpec("grok", "grok-4.7", "high"),
)


@dataclass(frozen=True)
class Task:
    id: str
    category: Category
    dir: Path
    repo: Path | None  # real tasks: local repo + base commit; seeded: dir/fixture
    base: str | None
    prompt: str
    setup: Path | None
    allowed_paths: tuple[str, ...]  # globs for scope grader
    pages: tuple[str, ...]  # URL paths to screenshot (ui/copy)
    dev_cmd: str | None
    dev_port: int | None
    checks: dict[str, str]  # name -> shell cmd (build, typecheck, lint, test)
    hidden_tests: Path | None
    known_issues: Path | None
    checklist: Path | None
    heldout: bool
    # runs after the bench-base commit: leaves uncommitted work (e.g. a messy diff to ship)
    after_base: Path | None = None


@dataclass(frozen=True)
class RunSpec:
    task: Task
    model: ModelSpec
    arm: Arm
    repeat: int

    @property
    def run_id(self) -> str:
        return f"{self.task.id}__{self.model.cli}__{self.arm}__r{self.repeat}"


@dataclass
class RunResult:
    run_id: str
    status: Literal["ok", "timeout", "error", "setup_failed"]
    wall_s: float
    turns: int | None
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None
    final_message: str
    diff_path: Path
    transcript_path: Path
    # R9: absolute paths outside the run's sandbox (real home, source repos) seen in output
    # None: the scanned output had no tool-level events, so nothing could be checked
    contaminated: bool | None = False
    contamination: list[str] = field(default_factory=list)
    workspace: Path | None = None  # agent's checkout, kept in the work root for graders
    error: str | None = None  # traceback when the harness itself failed during the run
    # R22: agent-writable files the harness refused to read (symlink, FIFO, hard link, ...)
    unsafe_files: list[str] = field(default_factory=list)
    # a descendant that left the process group still held the output pipes after the run
    # (its remaining output was dropped instead of hanging the harness)
    orphaned_output: bool = False
    # free space (GiB) on the work/results filesystem when the run started
    free_gb_at_start: float | None = None
    # the run's work dir (workspace, home) was deleted after capture + grade
    workspace_deleted: bool = False
