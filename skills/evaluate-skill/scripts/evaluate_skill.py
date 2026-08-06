#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Run paired Claude Code experiments to evaluate a skill."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import html
import json
import os
import random
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

EFFORTS = ("low", "medium", "high", "xhigh", "max")
SNAPSHOT_FILE_LIMIT = 100_000
SNAPSHOT_TOTAL_LIMIT = 1_000_000
SCHEMA_VERSION = 1
JUDGE_PROMPT_VERSION = 1
ACTIVE_PROCESS: subprocess.Popen[str] | None = None
TERMINATION_SIGNAL: int | None = None

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "a_score": {"type": "number", "minimum": 0, "maximum": 100},
        "b_score": {"type": "number", "minimum": 0, "maximum": 100},
        "preference": {"type": "string", "enum": ["A", "B", "tie"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "rationale": {"type": "string"},
    },
    "required": ["a_score", "b_score", "preference", "confidence", "rationale"],
    "additionalProperties": False,
}


class EvaluationError(Exception):
    """A user-facing validation or execution error."""


@dataclass
class RunResult:
    arm: str
    command: list[str]
    returncode: int
    duration_seconds: float
    response: str
    stdout: str
    stderr: str
    cli_json: dict[str, Any] | None
    usage: Any
    cost_usd: float | None
    changes: list[dict[str, Any]]
    error: str | None = None


def signal_handler(signum: int, _frame: Any) -> None:
    """Record termination and stop the active child process."""
    global TERMINATION_SIGNAL
    TERMINATION_SIGNAL = signum
    terminate_active_process()


def check_termination() -> None:
    if TERMINATION_SIGNAL is not None:
        raise KeyboardInterrupt


def terminate_active_process() -> None:
    process = ACTIVE_PROCESS
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def start_managed_process(
    command: list[str], *, cwd: Path | None = None
) -> subprocess.Popen[str]:
    global ACTIVE_PROCESS
    check_termination()
    previous_mask: set[int] | None = None
    if hasattr(signal, "pthread_sigmask"):
        previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM})
    try:
        check_termination()
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        ACTIVE_PROCESS = process
        return process
    finally:
        if previous_mask is not None:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)


def load_skill(skill_dir: Path) -> str:
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.is_file():
        raise EvaluationError(f"Skill directory has no SKILL.md: {skill_dir}")
    text = skill_file.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise EvaluationError("SKILL.md must start with YAML frontmatter")
    try:
        closing = lines.index("---", 1)
    except ValueError as exc:
        raise EvaluationError("SKILL.md frontmatter is not closed") from exc
    frontmatter = lines[1:closing]
    name = None
    for line in frontmatter:
        if line.startswith("name:"):
            name = line.partition(":")[2].strip().strip("'\"")
            break
    if not name:
        raise EvaluationError("SKILL.md frontmatter must contain a non-empty name")
    if name != skill_dir.name:
        raise EvaluationError(
            f"Skill name {name!r} does not match directory {skill_dir.name!r}"
        )
    return name


def reject_symlink_components(path: Path, label: str) -> None:
    absolute = path.expanduser().absolute()
    components = [absolute]
    components.extend(absolute.parents)
    for component in reversed(components):
        if component.is_symlink():
            raise EvaluationError(f"{label} path contains a symlink: {component}")


def load_cases(cases_path: Path) -> dict[str, Any]:
    reject_symlink_components(cases_path, "Cases")
    try:
        suite = json.loads(cases_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationError(f"Cannot read cases JSON: {exc}") from exc
    if not isinstance(suite, dict) or not isinstance(suite.get("cases"), list):
        raise EvaluationError("Cases JSON must be an object containing a cases array")
    if not isinstance(suite.get("name"), str) or not suite["name"].strip():
        raise EvaluationError("Suite name must be a non-empty string")
    seen: set[str] = set()
    for index, case in enumerate(suite["cases"]):
        if not isinstance(case, dict):
            raise EvaluationError(f"Case {index} must be an object")
        for field in ("id", "prompt", "rubric"):
            if not isinstance(case.get(field), str) or not case[field].strip():
                raise EvaluationError(f"Case {index} has invalid {field!r}")
        if case["id"] in seen:
            raise EvaluationError(f"Duplicate case ID: {case['id']}")
        seen.add(case["id"])
        if "fixture" in case:
            fixture_input = cases_path.parent / case["fixture"]
            reject_symlink_components(fixture_input, "Fixture")
            fixture = fixture_input.resolve()
            if not fixture.is_dir():
                raise EvaluationError(f"Fixture is not a directory: {fixture}")
            if (fixture / ".claude" / "skills").exists():
                raise EvaluationError(
                    "Fixture must not contain .claude/skills; evaluator controls the "
                    "skill baseline for both arms"
                )
            case["fixture_path"] = str(fixture)
    if not suite["cases"]:
        raise EvaluationError("Cases array must not be empty")
    return suite


def resolve_launcher(command: str) -> str:
    resolved = shutil.which(command)
    if resolved is None:
        raise EvaluationError(f"Claude launcher not found: {command}")
    return str(Path(resolved).resolve())


def run_launcher_metadata(command: list[str], timeout: float = 15) -> str:
    global ACTIVE_PROCESS
    check_termination()
    process: subprocess.Popen[str] | None = None
    try:
        process = start_managed_process(command)
        stdout, stderr = process.communicate(timeout=timeout)
        check_termination()
        if process.returncode != 0:
            raise EvaluationError(
                f"Launcher metadata command exited with {process.returncode}: {stderr}"
            )
        return stdout
    except subprocess.TimeoutExpired as exc:
        terminate_active_process()
        raise EvaluationError(
            f"Launcher metadata command timed out: {command}"
        ) from exc
    except OSError as exc:
        raise EvaluationError(f"Launcher metadata command failed: {exc}") from exc
    finally:
        if ACTIVE_PROCESS is process:
            ACTIVE_PROCESS = None


def validate_launcher(launcher: str) -> str:
    try:
        version = run_launcher_metadata([launcher, "--version"]).strip()
        help_text = run_launcher_metadata([launcher, "--help"])
    except EvaluationError as exc:
        raise EvaluationError(
            f"Claude launcher metadata validation failed: {exc}"
        ) from exc
    required = (
        "--print",
        "--output-format",
        "--model",
        "--effort",
        "--no-session-persistence",
        "--permission-mode",
        "--disable-slash-commands",
        "--json-schema",
        "--setting-sources",
        "--strict-mcp-config",
        "--mcp-config",
        "--no-chrome",
        "--tools",
    )
    check_termination()
    missing = [flag for flag in required if flag not in help_text]
    forwards_to_claude = "passed through to `claude` untouched" in help_text
    if missing and not forwards_to_claude:
        raise EvaluationError(
            f"Claude launcher lacks required flags: {', '.join(missing)}"
        )
    # Claude Code exposes no documented free runtime capability probe. These
    # metadata checks fail fast on obvious incompatibility; the first real run
    # remains the authoritative argv/runtime validation.
    check_termination()
    return version


def build_command(
    launcher: str,
    prompt: str,
    model: str,
    effort: str,
    *,
    without_skill: bool = False,
    schema: dict[str, Any] | None = None,
    disable_tools: bool = False,
) -> list[str]:
    command = [
        launcher,
        "--print",
        "--output-format",
        "json",
        "--no-session-persistence",
        "--permission-mode",
        "dontAsk",
        "--setting-sources",
        "project",
        "--strict-mcp-config",
        "--mcp-config",
        '{"mcpServers":{}}',
        "--no-chrome",
        "--model",
        model,
        "--effort",
        effort,
    ]
    if not disable_tools:
        command.append("--allowedTools=Bash")
    if without_skill:
        command.append("--disable-slash-commands")
    if disable_tools:
        command.extend(["--tools", ""])
    if schema is not None:
        command.extend(["--json-schema", json.dumps(schema, separators=(",", ":"))])
    command.append(prompt)
    return command


def reject_symlinks(root: Path, label: str) -> None:
    if root.is_symlink():
        raise EvaluationError(f"{label} must not be a symlink: {root}")
    for path in root.rglob("*"):
        if path.is_symlink():
            raise EvaluationError(f"{label} contains a symlink: {path}")


def make_workspace(fixture: str | None, skill_dir: Path, skill_name: str) -> Path:
    workspace = Path(tempfile.mkdtemp(prefix="evaluate-skill-"))
    try:
        if fixture:
            fixture_path = Path(fixture)
            reject_symlinks(fixture_path, "Fixture")
            if (fixture_path / ".claude" / "skills").exists():
                raise EvaluationError(
                    "Fixture must not contain .claude/skills; evaluator controls the "
                    "skill baseline for both arms"
                )
            shutil.copytree(fixture_path, workspace, dirs_exist_ok=True)
        reject_symlinks(skill_dir, "Skill")
        destination = workspace / ".claude" / "skills" / skill_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(skill_dir, destination)
        return workspace
    except BaseException:
        shutil.rmtree(workspace, ignore_errors=True)
        raise


def _is_binary(data: bytes) -> bool:
    return b"\0" in data or (
        bool(data)
        and sum(byte < 9 or 13 < byte < 32 for byte in data) / len(data) > 0.1
    )


def snapshot(workspace: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    total = 0
    root = workspace.resolve()
    for path in sorted(workspace.rglob("*")):
        relative = path.relative_to(workspace)
        if relative.parts[:2] == (".claude", "skills"):
            continue
        if path.is_symlink():
            result[relative.as_posix()] = {
                "symlink": True,
                "target": os.readlink(path),
                "omitted": "symlink target is never read",
            }
            continue
        if not path.is_file() or not path.resolve().is_relative_to(root):
            continue
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        entry: dict[str, Any] = {"size": len(data), "sha256": digest}
        if (
            len(data) <= SNAPSHOT_FILE_LIMIT
            and total + len(data) <= SNAPSHOT_TOTAL_LIMIT
            and not _is_binary(data)
        ):
            entry["text"] = data.decode("utf-8", errors="replace")
            total += len(data)
        else:
            entry["omitted"] = "binary or size limit"
        result[relative.as_posix()] = entry
    return result


def diff_snapshots(
    before: dict[str, Any], after: dict[str, Any]
) -> list[dict[str, Any]]:
    changes = []
    for name in sorted(set(before) | set(after)):
        old, new = before.get(name), after.get(name)
        if old == new:
            continue
        kind = "modified" if old and new else ("added" if new else "deleted")
        changes.append({"path": name, "kind": kind, "before": old, "after": new})
    return changes


def parse_cli_json(stdout: str) -> tuple[dict[str, Any], str, Any, float | None]:
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise EvaluationError(f"Claude output is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise EvaluationError("Claude JSON output must be an object")
    response = data.get("result", "")
    if not isinstance(response, str):
        response = json.dumps(response, ensure_ascii=False)
    usage = data.get("usage")
    cost = data.get("total_cost_usd", data.get("cost_usd"))
    return (
        data,
        response,
        usage,
        float(cost) if isinstance(cost, (int, float)) else None,
    )


def run_command(command: list[str], workspace: Path, arm: str) -> RunResult:
    global ACTIVE_PROCESS
    check_termination()
    before = snapshot(workspace)
    check_termination()
    started = time.monotonic()
    process: subprocess.Popen[str] | None = None
    try:
        process = start_managed_process(command, cwd=workspace)
        stdout, stderr = process.communicate()
        duration = time.monotonic() - started
        after = snapshot(workspace)
        data: dict[str, Any] | None = None
        response = ""
        usage: Any = None
        cost: float | None = None
        parse_error: str | None = None
        try:
            data, response, usage, cost = parse_cli_json(stdout)
        except EvaluationError as exc:
            parse_error = str(exc)
        error = None
        if process.returncode != 0:
            error = f"Claude exited with {process.returncode}"
            if parse_error:
                error = f"{error}; {parse_error}"
        elif parse_error:
            error = parse_error
        return RunResult(
            arm,
            command,
            process.returncode,
            duration,
            response,
            stdout,
            stderr,
            data,
            usage,
            cost,
            diff_snapshots(before, after),
            error,
        )
    except OSError as exc:
        return RunResult(
            arm,
            command,
            127,
            time.monotonic() - started,
            "",
            "",
            str(exc),
            None,
            None,
            None,
            [],
            str(exc),
        )
    finally:
        if ACTIVE_PROCESS is process:
            ACTIVE_PROCESS = None


def identity_disclosure(
    run: RunResult, skill_name: str, skill_dir: Path, skill_text: str
) -> bool:
    candidate = run.response + "\n" + json.dumps(run.changes, ensure_ascii=False)
    identifiers = (str(skill_dir), f"/{skill_name}")
    if any(identifier and identifier in candidate for identifier in identifiers):
        return True
    normalized_skill = " ".join(skill_text.split())
    normalized_candidate = " ".join(candidate.split())
    if len(normalized_skill) < 80:
        return normalized_skill in normalized_candidate
    skill_lines = {
        " ".join(line.split()).casefold()
        for line in skill_text.splitlines()
        if len(" ".join(line.split())) >= 40
    }
    candidate_folded = normalized_candidate.casefold()
    if any(line in candidate_folded for line in skill_lines):
        return True
    words = normalized_skill.casefold().split()
    for size in (20, 12, 5):
        fingerprints = {
            chunk
            for index in range(max(0, len(words) - size + 1))
            if len(chunk := " ".join(words[index : index + size])) >= 40
        }
        if any(chunk in candidate_folded for chunk in fingerprints):
            return True
    matcher = difflib.SequenceMatcher(
        None, normalized_skill, normalized_candidate, autojunk=False
    )
    longest = matcher.find_longest_match().size
    return longest >= min(200, int(len(normalized_skill) * 0.4))


def redact_identity(text: str, skill_name: str, skill_dir: Path) -> str:
    replacements = (str(skill_dir), skill_name, f"/{skill_name}")
    redacted = text
    for value in sorted(replacements, key=len, reverse=True):
        if value:
            redacted = redacted.replace(value, "[TARGET_SKILL_REDACTED]")
    return redacted


def changes_text(
    changes: list[dict[str, Any]], skill_name: str, skill_dir: Path
) -> str:
    serialized = json.dumps(changes, ensure_ascii=False, indent=2)
    return redact_identity(serialized, skill_name, skill_dir)


def judge_prompt(
    case: dict[str, Any],
    candidate_a: RunResult,
    candidate_b: RunResult,
    skill_name: str,
    skill_dir: Path,
) -> str:
    a_response = redact_identity(candidate_a.response, skill_name, skill_dir)
    b_response = redact_identity(candidate_b.response, skill_name, skill_dir)
    return f"""You are a blind evaluator. Score both candidates only against the task and rubric.
Do not infer which system produced either candidate. Return only the requested structured result.

TASK:
{case["prompt"]}

RUBRIC:
{case["rubric"]}

CANDIDATE A RESPONSE:
{a_response}

CANDIDATE A WORKSPACE CHANGES:
{changes_text(candidate_a.changes, skill_name, skill_dir)}

CANDIDATE B RESPONSE:
{b_response}

CANDIDATE B WORKSPACE CHANGES:
{changes_text(candidate_b.changes, skill_name, skill_dir)}
"""


def parse_judge(result: RunResult) -> dict[str, Any]:
    if result.error or result.cli_json is None:
        raise EvaluationError(result.error or "Judge returned no JSON")
    value = result.cli_json.get("structured_output", result.cli_json.get("result"))
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise EvaluationError(f"Judge structured output is invalid: {exc}") from exc
    if not isinstance(value, dict):
        raise EvaluationError("Judge structured output must be an object")
    for score in ("a_score", "b_score"):
        if (
            not isinstance(value.get(score), (int, float))
            or not 0 <= value[score] <= 100
        ):
            raise EvaluationError(f"Judge returned invalid {score}")
    if value.get("preference") not in ("A", "B", "tie"):
        raise EvaluationError("Judge returned invalid preference")
    if (
        not isinstance(value.get("confidence"), (int, float))
        or not 0 <= value["confidence"] <= 1
    ):
        raise EvaluationError("Judge returned invalid confidence")
    if not isinstance(value.get("rationale"), str):
        raise EvaluationError("Judge returned invalid rationale")
    return value


def bootstrap_ci(
    values: list[float], seed: int, samples: int = 10_000
) -> list[float] | None:
    if not values:
        return None
    rng = random.Random(seed)
    means = sorted(
        statistics.fmean(rng.choices(values, k=len(values))) for _ in range(samples)
    )
    return [means[int(samples * 0.025)], means[min(samples - 1, int(samples * 0.975))]]


def randomization_p(
    values: list[float], seed: int, samples: int = 100_000
) -> float | None:
    if not values:
        return None
    observed = abs(statistics.fmean(values))
    n = len(values)
    if n <= 20:
        extreme = 0
        total = 1 << n
        for mask in range(total):
            mean = abs(
                sum(
                    value if mask & (1 << i) else -value
                    for i, value in enumerate(values)
                )
                / n
            )
            extreme += mean >= observed - 1e-12
        return extreme / total
    rng = random.Random(seed)
    extreme = sum(
        abs(sum(value if rng.getrandbits(1) else -value for value in values) / n)
        >= observed - 1e-12
        for _ in range(samples)
    )
    return (extreme + 1) / (samples + 1)


def calculate_statistics(trials: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    valid = [trial for trial in trials if trial.get("difference") is not None]
    differences = [float(trial["difference"]) for trial in valid]
    failed = len(trials) - len(valid)
    failure_rate = failed / len(trials) if trials else 0.0
    if not differences:
        return {
            "valid_pairs": 0,
            "failed_pairs": failed,
            "failure_rate": failure_rate,
            "conclusion": "insufficient data",
        }
    with_scores = [float(trial["with_score"]) for trial in valid]
    without_scores = [float(trial["without_score"]) for trial in valid]
    mean = statistics.fmean(differences)
    ci = bootstrap_ci(differences, seed)
    p_value = randomization_p(differences, seed)
    stdev = statistics.stdev(differences) if len(differences) >= 2 else None
    dz = mean / stdev if stdev and stdev > 0 else (0.0 if mean == 0 else None)
    wins = sum(value > 0 for value in differences)
    ties = sum(value == 0 for value in differences)
    losses = sum(value < 0 for value in differences)
    significant = (
        len(differences) >= 2
        and p_value is not None
        and p_value < 0.05
        and ci is not None
        and not (ci[0] <= 0 <= ci[1])
    )
    conclusion = "insufficient evidence"
    if failure_rate > 0.25:
        conclusion = "insufficient data due to failures"
    elif significant:
        conclusion = "significant improvement" if mean > 0 else "significant regression"
    return {
        "valid_pairs": len(valid),
        "failed_pairs": failed,
        "failure_rate": failure_rate,
        "with_mean": statistics.fmean(with_scores),
        "without_mean": statistics.fmean(without_scores),
        "mean_difference": mean,
        "median_difference": statistics.median(differences),
        "confidence_interval_95": ci,
        "p_value": p_value,
        "cohens_dz": dz,
        "wins": wins,
        "ties": ties,
        "losses": losses,
        "win_rate": wins / len(differences),
        "conclusion": conclusion,
    }


def per_case_statistics(trials: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for case_id in sorted({trial["case_id"] for trial in trials}):
        case_trials = [
            trial
            for trial in trials
            if trial["case_id"] == case_id and trial.get("difference") is not None
        ]
        values = [trial["difference"] for trial in case_trials]
        rows.append(
            {
                "case_id": case_id,
                "valid_pairs": len(values),
                "mean_difference": statistics.fmean(values) if values else None,
            }
        )
    return rows


def format_number(value: Any, digits: int = 3) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def format_score(value: Any) -> str:
    """Render a 0-100 judge score with one decimal place."""
    return "n/a" if not isinstance(value, (int, float)) else f"{value:.1f}"


def format_percent(value: Any, digits: int = 1) -> str:
    return (
        "n/a" if not isinstance(value, (int, float)) else f"{value * 100:.{digits}f}%"
    )


def format_interval(value: Any) -> str:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return f"[{format_number(value[0], 2)}, {format_number(value[1], 2)}]"
    return "n/a"


def format_duration(seconds: Any) -> str:
    if not isinstance(seconds, (int, float)):
        return "n/a"
    if seconds < 60:
        return f"{seconds:.1f} 秒"
    return f"{int(seconds // 60)} 分 {seconds % 60:.0f} 秒"


def bar_width(value: Any) -> str:
    """Clamp a score to a CSS-safe bar width percentage."""
    if not isinstance(value, (int, float)):
        return "0"
    return f"{max(0.0, min(100.0, float(value))):.1f}"


ARM_LABELS = {"with": "啟用 skill", "without": "未啟用 skill"}

CONCLUSION_THEMES: dict[str, dict[str, str]] = {
    "significant improvement": {
        "mark": "↑",
        "headline": "啟用 skill 明顯更好。",
        "note": (
            "配對差異在統計上顯著為正：p &lt; 0.05，且 95% bootstrap 信賴區間不跨 0。"
            "這個結論只適用於這個 suite、這組模型與 judge 設定。"
        ),
    },
    "significant regression": {
        "mark": "↓",
        "headline": "啟用 skill 明顯更差。",
        "note": (
            "配對差異在統計上顯著為負：p &lt; 0.05，且 95% bootstrap 信賴區間不跨 0。"
            "先看 per-case 結果，找出是哪個案例被 skill 拖累。"
        ),
    },
    "insufficient evidence": {
        "mark": "≈",
        "headline": "目前證據不足，不能判定啟用 skill 會更好或更差。",
        "note": (
            "「insufficient evidence」不等於「兩者一定沒差」，而是這批樣本不足以做可靠推論："
            "沒有同時滿足 p &lt; 0.05 與 95% 信賴區間不跨 0。加大 rounds 或案例數才有機會分辨。"
        ),
    },
    "insufficient data due to failures": {
        "mark": "!",
        "headline": "失敗的配對太多，這份結果不能拿來下結論。",
        "note": (
            "失敗率超過 25% 時，顯著性判定一律被抑制。"
            "先修好執行失敗的原因（launcher 相容性、權限、案例設計）再重跑。"
        ),
    },
    "insufficient data": {
        "mark": "!",
        "headline": "沒有任何有效配對，無法計算統計量。",
        "note": "每個 pair 都執行失敗、judge 失敗，或被判定為 identity disclosure；請往下看 trial 細節。",
    },
}

UNKNOWN_THEME = {
    "mark": "?",
    "headline": "無法辨識的結論標籤。",
    "note": "報告的 summary.conclusion 不是已知的標籤值，請檢查 JSON sidecar。",
}

REPORT_CSS = """
@import url('https://fonts.googleapis.com/css2?family=LXGW+WenKai+TC:wght@400;700&family=Patrick+Hand&display=swap');
:root{--ink:#163b54;--muted:#547084;--frame:#17445f;--accent:#e35d3f;--accent2:#21829e;--good:#2f7d5f;--warn:#c37c22;--bad:#d4593d}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:#153b55;color:var(--ink);line-height:1.75;font-family:"LXGW WenKai TC",system-ui,"PingFang TC","Noto Sans TC",sans-serif}
a{color:inherit}
.page{width:min(1180px,calc(100% - 32px));margin:30px auto;padding:56px;background-color:#f7fbfc;background-image:linear-gradient(#dcebf1 1px,transparent 1px),linear-gradient(90deg,#dcebf1 1px,transparent 1px);background-size:24px 24px;box-shadow:0 20px 60px rgba(0,0,0,.3)}
.eyebrow{text-transform:uppercase;letter-spacing:.14em;font-family:"Patrick Hand",monospace;font-size:.88rem}
.hero h1{margin:.2em 0;line-height:1.05;font-family:"Patrick Hand","LXGW WenKai TC",sans-serif;font-size:clamp(2.1rem,5vw,4.2rem)}
.scribble{color:var(--accent);overflow-wrap:anywhere}
.lead{font-size:clamp(1.05rem,2vw,1.3rem);max-width:820px}
.chips{display:flex;flex-wrap:wrap;gap:9px;margin:24px 0}
.chip{padding:5px 13px;border-radius:999px;font-size:.9rem;background:#173e58;color:#fff}
.grid{display:grid;gap:22px}
.scores{grid-template-columns:repeat(2,minmax(0,1fr));margin:30px 0}
.section,.score-card{background:rgba(255,255,255,.94);border:2px solid var(--frame);border-radius:8px;box-shadow:5px 5px 0 #9cbcca}
.score-card{position:relative;padding:24px}
.score-card:after{content:"// measured";position:absolute;right:18px;bottom:3px;font-family:monospace;font-size:.8rem;color:#789}
.score-top{display:flex;align-items:flex-end;justify-content:space-between;gap:12px}
.score{font-family:"Patrick Hand",sans-serif;font-size:4.2rem;line-height:.85}
.score-label{font-weight:700}
.bar{height:13px;margin-top:20px;border-radius:30px;background:rgba(95,102,111,.13);overflow:hidden}
.bar>i{display:block;height:100%;border-radius:inherit}
.with-card .bar>i{background:var(--accent)}
.without-card .bar>i{background:var(--accent2)}
.section{margin-top:34px;padding:28px}
.section h2{margin:0 0 18px;line-height:1.2;font-size:clamp(1.5rem,3vw,2.05rem)}
.section h3{margin:24px 0 7px;font-family:monospace;font-size:1rem;overflow-wrap:anywhere}
.verdict{display:grid;grid-template-columns:auto 1fr;gap:18px;align-items:start}
.verdict-mark{font-family:"Patrick Hand",sans-serif;font-size:3rem;line-height:1;color:var(--accent)}
.facts{grid-template-columns:repeat(3,minmax(0,1fr))}
.fact{padding:18px;background:#eaf4f7;border-left:4px solid #1f7795}
.fact small{color:var(--muted)}
.fact strong{display:block;font-size:1.12rem;overflow-wrap:anywhere;font-variant-numeric:tabular-nums}
.callout{margin:20px 0;padding:20px 22px;background:#fff2c7;border:2px dashed var(--warn)}
.callout.warning{background:#ffe0d6;border-color:var(--bad)}
.judge{position:relative;margin:26px 0 0;padding:22px;background:#fff;border:2px solid var(--frame);font-size:1.02rem}
.judge:after{content:"JUDGE NOTE";position:absolute;right:12px;top:-14px;padding:2px 10px;background:var(--frame);color:#fff;font:12px monospace}
.meta{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.meta div{padding:14px;background:#e9f3f6;border:1px solid #9ebac7}
.meta span{display:block;color:var(--muted);font-size:.82rem}
.meta strong{overflow-wrap:anywhere}
.table-wrap{overflow-x:auto}
table{width:100%;border-collapse:collapse;background:#fff}
th,td{padding:9px 12px;border:1px solid #9ebac7;text-align:left}
th{background:#e9f3f6;font:.8rem/1.6 monospace;text-transform:uppercase;letter-spacing:.06em}
td.num{text-align:right;font-variant-numeric:tabular-nums}
.trial{margin-top:26px;padding-top:20px;border-top:2px dashed #9ebac7}
.trial:first-of-type{margin-top:0;padding-top:0;border-top:0}
.compare{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}
.answer{min-width:0;background:#f8fcfd;border:2px solid var(--frame)}
.answer summary{padding:16px;cursor:pointer;font-family:monospace;font-weight:700}
.answer-body{padding:0 18px 18px}
.answer-body pre{margin:0;font:inherit;line-height:1.7;white-space:pre-wrap;overflow-wrap:anywhere}
.answer-body pre.code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.82rem;line-height:1.55}
.answer.raw{margin-top:14px}
.method summary{cursor:pointer;font-family:monospace}
.method li{margin-bottom:6px}
.tiny{font-size:.86rem;color:var(--muted);overflow-wrap:anywhere}
.ok{color:var(--good);font-weight:700}
.bad{color:var(--bad);font-weight:700}
.foot{margin-top:34px;padding-top:18px;border-top:2px dashed #52778b;display:flex;justify-content:space-between;flex-wrap:wrap;gap:16px;font-size:.9rem;color:var(--muted)}
@media(max-width:760px){.page{width:100%;margin:0;padding:30px 16px}.scores,.facts,.compare{grid-template-columns:1fr}.meta{grid-template-columns:repeat(2,minmax(0,1fr))}.section{padding:20px}.score-card{padding:20px}.hero h1{font-size:2.4rem}}
@media print{body{background:#fff}.page{width:100%;margin:0;padding:0;background-image:none;box-shadow:none}.section,.score-card{box-shadow:none;break-inside:avoid}.answer[open]{break-inside:auto}}
"""


def preference_label(trial: dict[str, Any]) -> str:
    """Map the blind A/B judge preference back to a readable arm name."""
    judged = trial.get("judge") or {}
    preference = judged.get("preference")
    if preference == "tie":
        return "平手"
    order = trial.get("blind_order") or []
    index = {"A": 0, "B": 1}.get(str(preference), None)
    if index is None or index >= len(order):
        return "未知"
    return ARM_LABELS.get(order[index], str(order[index]))


def aggregate_runs(trials: list[dict[str, Any]]) -> dict[str, Any]:
    """Total wall-clock time, cost, and workspace churn across every launcher run."""
    duration = 0.0
    cost = 0.0
    has_cost = False
    changes = 0
    for trial in trials:
        for key in ("with", "without", "judge_run"):
            run = trial.get(key)
            if not isinstance(run, dict):
                continue
            if isinstance(run.get("duration_seconds"), (int, float)):
                duration += float(run["duration_seconds"])
            if isinstance(run.get("cost_usd"), (int, float)):
                cost += float(run["cost_usd"])
                has_cost = True
            if key != "judge_run" and isinstance(run.get("changes"), list):
                changes += len(run["changes"])
    return {
        "duration_seconds": duration,
        "cost_usd": cost if has_cost else None,
        "workspace_changes": changes,
    }


def render_html(report: dict[str, Any], sidecar_name: str | None = None) -> str:
    def esc(value: Any) -> str:
        return html.escape(str(value))

    stats: dict[str, Any] = report.get("summary") or {}
    config: dict[str, Any] = report.get("configuration") or {}
    trials: list[dict[str, Any]] = report.get("trials") or []
    per_case: list[dict[str, Any]] = report.get("per_case") or []

    conclusion = str(stats.get("conclusion", "insufficient data"))
    theme = CONCLUSION_THEMES.get(conclusion, UNKNOWN_THEME)
    skill_name = str(config.get("skill_name", "unknown-skill"))
    suite = str(config.get("suite", "unnamed-suite"))
    valid_pairs = stats.get("valid_pairs", 0)
    failed_pairs = stats.get("failed_pairs", 0)
    with_mean = stats.get("with_mean")
    without_mean = stats.get("without_mean")
    totals = aggregate_runs(trials)

    chips = "".join(
        f'<span class="chip">{esc(text)}</span>'
        for text in (
            f"✓ {valid_pairs} 組有效比較",
            f"✗ {failed_pairs} 組失敗配對",
            f"{config.get('model', 'unknown model')} · {config.get('effort', '?')} effort",
            f"judge {config.get('judge_model', 'unknown')} · {config.get('judge_effort', '?')} effort",
            f"{config.get('rounds', '?')} rounds · suite {suite}",
        )
    )

    if isinstance(valid_pairs, int) and valid_pairs > 0:
        score_summary = (
            f"啟用 skill 平均 {format_score(with_mean)} 分，"
            f"未啟用平均 {format_score(without_mean)} 分，"
            f"共 {valid_pairs} 組有效比較。"
        )
        verdict_detail = (
            f"啟用 skill 平均 {format_score(with_mean)} 分，未啟用平均 {format_score(without_mean)} 分；"
            f"平均配對差異 {format_number(stats.get('mean_difference'), 2)} 分，"
            f"{stats.get('wins', 0)} 勝 / {stats.get('ties', 0)} 平 / {stats.get('losses', 0)} 敗，"
            f"失敗率 {format_percent(stats.get('failure_rate'))}。"
        )
    else:
        score_summary = f"沒有任何有效配對（{failed_pairs} 組失敗）。"
        verdict_detail = (
            f"這次沒有任何有效配對（{failed_pairs} 組失敗），分數與統計量都無法計算；"
            "請往下看 trial 細節找出失敗原因。"
        )

    facts = "".join(
        f'<div class="fact"><small>{esc(label)}</small><strong>{esc(value)}</strong></div>'
        for label, value in (
            ("平均配對差異", f"{format_number(stats.get('mean_difference'), 2)} 分"),
            (
                "中位數配對差異",
                f"{format_number(stats.get('median_difference'), 2)} 分",
            ),
            ("95% bootstrap CI", format_interval(stats.get("confidence_interval_95"))),
            ("p-value（sign-flip）", format_number(stats.get("p_value"), 5)),
            ("Cohen's dz", format_number(stats.get("cohens_dz"))),
            (
                "勝 / 平 / 敗",
                f"{stats.get('wins', 0)} / {stats.get('ties', 0)} / {stats.get('losses', 0)}",
            ),
            ("Win rate", format_percent(stats.get("win_rate"))),
            ("有效 / 失敗配對", f"{valid_pairs} / {failed_pairs}"),
            ("失敗率", format_percent(stats.get("failure_rate"))),
        )
    )

    case_rows = (
        "".join(
            f"<tr><td>{esc(row.get('case_id'))}</td>"
            f'<td class="num">{esc(row.get("valid_pairs", 0))}</td>'
            f'<td class="num">{format_number(row.get("mean_difference"), 2)}</td></tr>'
            for row in per_case
        )
        or '<tr><td colspan="3">沒有 per-case 資料。</td></tr>'
    )

    judge_blocks = []
    for trial in trials:
        judged = trial.get("judge") or {}
        rationale = judged.get("rationale")
        if not rationale:
            continue
        judge_blocks.append(
            f"<h3>{esc(trial.get('case_id'))} · round {esc(trial.get('round'))}</h3>"
            f'<blockquote class="judge">{esc(rationale)}</blockquote>'
            f'<p class="tiny">Judge 偏好：{esc(preference_label(trial))} · '
            f"信心 {format_percent(judged.get('confidence'), 0)} · "
            f"啟用 skill {format_score(trial.get('with_score'))} 分 vs 未啟用 "
            f"{format_score(trial.get('without_score'))} 分</p>"
        )
    judge_section = "".join(judge_blocks) or (
        '<p class="tiny">沒有任何成功的 judge 評語可顯示。</p>'
    )

    version = str(config.get("claude_version", "n/a")).strip().splitlines()
    meta = "".join(
        f"<div><span>{esc(label)}</span><strong>{esc(value)}</strong></div>"
        for label, value in (
            ("受測 skill", skill_name),
            ("Case suite", suite),
            ("受測模型", config.get("model", "n/a")),
            ("推理強度", config.get("effort", "n/a")),
            ("Judge 模型", config.get("judge_model", "n/a")),
            ("Judge 強度", config.get("judge_effort", "n/a")),
            ("Rounds", config.get("rounds", "n/a")),
            ("Seed", config.get("seed", "n/a")),
            ("Launcher", config.get("claude_command", "n/a")),
            ("Launcher 版本", version[0] if version else "n/a"),
            ("總執行時間", format_duration(totals["duration_seconds"])),
            (
                "模型總成本",
                "n/a" if totals["cost_usd"] is None else f"US${totals['cost_usd']:.3f}",
            ),
            ("Workspace 變更檔案數", totals["workspace_changes"]),
            ("Trial 總數", len(trials)),
            (
                "Schema / judge prompt",
                f"v{config.get('schema_version', report.get('schema_version', '?'))} / v{config.get('judge_prompt_version', '?')}",
            ),
            ("Skill 路徑", config.get("skill", "n/a")),
        )
    )

    trial_blocks = []
    for trial in trials:
        status = str(trial.get("status", "unknown"))
        status_class = "ok" if status == "valid" else "bad"
        answers = []
        for arm in ("with", "without"):
            run = trial.get(arm) if isinstance(trial.get(arm), dict) else {}
            score = trial.get(f"{arm}_score")
            response = run.get("response") or "（沒有可顯示的回答）"
            error = run.get("error")
            summary = (
                f"{ARM_LABELS[arm]} · {format_score(score)} 分 · "
                f"{format_duration(run.get('duration_seconds'))}"
            )
            error_line = (
                f'<p class="tiny bad">執行錯誤：{esc(error)}</p>' if error else ""
            )
            answers.append(
                f'<details class="answer"><summary>{esc(summary)}</summary>'
                f'<div class="answer-body">{error_line}<pre>{esc(response)}</pre></div></details>'
            )
        raw = html.escape(json.dumps(trial, ensure_ascii=False, indent=2))
        trial_blocks.append(
            f'<article class="trial">'
            f"<h3>{esc(trial.get('case_id'))} · round {esc(trial.get('round'))} · "
            f'<span class="{status_class}">{esc(status)}</span></h3>'
            f'<div class="compare">{"".join(answers)}</div>'
            f'<details class="answer raw"><summary>原始 trial JSON</summary>'
            f'<div class="answer-body"><pre class="code">{raw}</pre></div></details>'
            f"</article>"
        )
    trials_section = "".join(trial_blocks) or '<p class="tiny">沒有 trial 紀錄。</p>'

    isolation = config.get("isolation_notice")
    isolation_item = f"<li>{esc(isolation)}</li>" if isolation else ""
    retained = config.get("retained_workspaces") or []
    retained_item = (
        f"<li>保留了 {len(retained)} 個暫存 workspace 供除錯，路徑記在 JSON sidecar。</li>"
        if retained
        else ""
    )

    sidecar_link = (
        f'<a href="{esc(sidecar_name)}">查看 machine-readable JSON source ↗</a>'
        if sidecar_name
        else "<span>machine-readable JSON sidecar 與本報告同名（.json）</span>"
    )

    return f"""<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Skill 評估報告 · {esc(skill_name)}</title>
<meta name="description" content="{esc(skill_name)} 的配對實驗評估報告（suite: {esc(suite)}）">
<style>{REPORT_CSS}</style></head><body><main class="page">
<header class="hero">
  <div class="eyebrow">Skill evaluation · {esc(skill_name)}</div>
  <h1><span class="scribble">{esc(skill_name)}</span><br>真的有幫上忙嗎？</h1>
  <p class="lead">{theme["headline"]} {esc(score_summary)}</p>
  <div class="chips">{chips}</div>
</header>

<section class="scores grid" aria-label="分數比較">
  <article class="score-card with-card">
    <div class="score-top"><div><div class="score-label">{ARM_LABELS["with"]}</div><small>With skill</small></div><strong class="score">{format_score(with_mean)}</strong></div>
    <div class="bar" aria-label="平均 {format_score(with_mean)} 分"><i style="width:{bar_width(with_mean)}%"></i></div>
  </article>
  <article class="score-card without-card">
    <div class="score-top"><div><div class="score-label">{ARM_LABELS["without"]}</div><small>Baseline</small></div><strong class="score">{format_score(without_mean)}</strong></div>
    <div class="bar" aria-label="平均 {format_score(without_mean)} 分"><i style="width:{bar_width(without_mean)}%"></i></div>
  </article>
</section>

<section class="section">
  <div class="verdict"><div class="verdict-mark">{theme["mark"]}</div><div>
    <h2>一句話結論</h2>
    <p><strong>{theme["headline"]}</strong></p>
    <p>{esc(verdict_detail)}</p>
  </div></div>
  <div class="callout"><strong>統計標籤「{esc(conclusion)}」是什麼意思？</strong><br>{theme["note"]}</div>
</section>

<section class="section">
  <h2>統計數字</h2>
  <p class="tiny">配對差異定義為「啟用 skill 分數 − 未啟用分數」，正值代表 skill 有幫助。</p>
  <div class="facts grid">{facts}</div>
</section>

<section class="section">
  <h2>Per-case 結果</h2>
  <p class="tiny">整體平均可能掩蓋單一案例的退步；逐案檢視才看得出 skill 在哪些任務上真的有效。</p>
  <div class="table-wrap"><table><thead><tr><th>Case</th><th>Valid pairs</th><th>Mean difference</th></tr></thead><tbody>{case_rows}</tbody></table></div>
</section>

<section class="section">
  <h2>Judge 怎麼說？</h2>
  <p class="tiny">Judge 以盲測方式比較兩份回答，skill 名稱與來源路徑已遮蔽；A/B 位置每輪隨機對調。</p>
  {judge_section}
</section>

<section class="section">
  <h2>這次怎麼測？</h2>
  <div class="meta">{meta}</div>
</section>

<section class="section">
  <h2>想看每一輪的完整回答？</h2>
  <p class="tiny">預設收起。每個 trial 同時附上原始 JSON，內容與 sidecar 一致。</p>
  {trials_section}
</section>

<section class="section method">
  <details><summary><strong>方法與限制：給想深挖的人</strong></summary>
    <ul>
      <li>每個 trial 在同一 fixture 的獨立副本上配對執行；兩個 arm 取得相同的 project-local skill tree，差別只在明確啟用與 slash command 可用性。</li>
      <li>Arm 執行順序與 judge 的 A/B 位置以 seed {esc(config.get("seed", "n/a"))} 隨機化，統計抽樣使用同一個 seed。</li>
      <li>95% 信賴區間為 seeded nonparametric bootstrap；p-value 為雙尾 paired sign-flip randomization test。顯著性需 p &lt; 0.05 且 95% 區間不含 0；失敗率超過 25% 時一律不宣告顯著。</li>
      <li>LLM judge 不是客觀 ground truth。identity 字串已遮蔽、judge 工具已停用，但風格等間接線索仍可能洩漏身份。</li>
      <li>把 case-round 配對彙總是描述性統計，不是跨任務的母體推論；「insufficient evidence」不代表沒有差異。</li>
      {isolation_item}
      {retained_item}
    </ul>
  </details>
</section>

<footer class="foot"><span>資料產生時間：{esc(report.get("generated_at", "n/a"))}</span>{sidecar_link}</footer>
</main></body></html>"""


def write_report(report: dict[str, Any], output: Path) -> tuple[Path, Path]:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.suffix.casefold() != ".html":
        output = output.with_name(f"{output.name}.html")
    sidecar = output.with_name(f"{output.stem}.json")
    if sidecar == output:
        raise EvaluationError("HTML report and JSON sidecar paths must differ")
    sidecar.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    output.write_text(render_html(report, sidecar.name), encoding="utf-8")
    return output, sidecar


def run_experiment(args: argparse.Namespace) -> dict[str, Any]:
    reject_symlink_components(args.skill, "Skill")
    skill_dir = args.skill.resolve()
    reject_symlinks(skill_dir, "Skill")
    skill_name = load_skill(skill_dir)
    reject_symlink_components(args.cases, "Cases")
    suite = load_cases(args.cases)
    launcher = resolve_launcher(args.claude_bin)
    version = validate_launcher(launcher)
    check_termination()
    skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    rng = random.Random(args.seed)
    trials: list[dict[str, Any]] = []
    retained: list[str] = []
    for case in suite["cases"]:
        for round_number in range(1, args.rounds + 1):
            print(
                f"[{case['id']} round {round_number}] running paired arms",
                file=sys.stderr,
            )
            arm_order = ["with", "without"]
            rng.shuffle(arm_order)
            runs: dict[str, RunResult] = {}
            workspaces: dict[str, Path] = {}
            judge_workspace: Path | None = None
            try:
                for arm in arm_order:
                    check_termination()
                    # Both arms receive the identical project-local skill tree. The
                    # without arm differs only by slash-command availability/prompt.
                    workspace = make_workspace(
                        case.get("fixture_path"), skill_dir, skill_name
                    )
                    workspaces[arm] = workspace
                    check_termination()
                    prompt = (
                        f"/{skill_name}\n\n{case['prompt']}"
                        if arm == "with"
                        else case["prompt"]
                    )
                    command = build_command(
                        launcher,
                        prompt,
                        args.model,
                        args.effort,
                        without_skill=arm == "without",
                    )
                    runs[arm] = run_command(command, workspace, arm)
                    check_termination()
                record: dict[str, Any] = {
                    "case_id": case["id"],
                    "round": round_number,
                    "arm_order": arm_order,
                    "with": asdict(runs["with"]),
                    "without": asdict(runs["without"]),
                    "status": "run failed",
                    "difference": None,
                }
                disclosures = [
                    arm
                    for arm in ("with", "without")
                    if identity_disclosure(runs[arm], skill_name, skill_dir, skill_text)
                ]
                if disclosures:
                    record["status"] = "identity disclosure"
                    record["identity_disclosure_arms"] = disclosures
                elif not runs["with"].error and not runs["without"].error:
                    check_termination()
                    blind_order = ["with", "without"]
                    rng.shuffle(blind_order)
                    candidates = [runs[blind_order[0]], runs[blind_order[1]]]
                    judge_workspace = Path(
                        tempfile.mkdtemp(prefix="evaluate-skill-judge-")
                    )
                    command = build_command(
                        launcher,
                        judge_prompt(
                            case,
                            *candidates,
                            skill_name=skill_name,
                            skill_dir=skill_dir,
                        ),
                        args.judge_model,
                        args.judge_effort,
                        schema=JUDGE_SCHEMA,
                        disable_tools=True,
                    )
                    judge_run = run_command(command, judge_workspace, "judge")
                    check_termination()
                    record["blind_order"] = blind_order
                    record["judge_run"] = asdict(judge_run)
                    try:
                        judged = parse_judge(judge_run)
                        scores = {
                            blind_order[0]: float(judged["a_score"]),
                            blind_order[1]: float(judged["b_score"]),
                        }
                        record.update(
                            {
                                "judge": judged,
                                "with_score": scores["with"],
                                "without_score": scores["without"],
                                "difference": scores["with"] - scores["without"],
                                "status": "valid",
                            }
                        )
                    except EvaluationError as exc:
                        record["judge_error"] = str(exc)
                        record["status"] = "judge failed"
                trials.append(record)
                check_termination()
            finally:
                cleanup = list(workspaces.values())
                if judge_workspace is not None:
                    cleanup.append(judge_workspace)
                for workspace in cleanup:
                    if args.keep_workspaces:
                        retained.append(str(workspace))
                    else:
                        shutil.rmtree(workspace, ignore_errors=True)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "configuration": {
            "skill": str(skill_dir),
            "skill_name": skill_name,
            "suite": suite["name"],
            "cases": str(args.cases.absolute()),
            "claude_command": args.claude_bin,
            "claude_resolved": launcher,
            "claude_version": version,
            "launcher_validation": (
                "Static --version/--help metadata validation only; runtime argv "
                "compatibility is verified by the actual experiment or smoke run."
            ),
            "model": args.model,
            "effort": args.effort,
            "judge_model": args.judge_model,
            "judge_effort": args.judge_effort,
            "rounds": args.rounds,
            "seed": args.seed,
            "judge_prompt_version": JUDGE_PROMPT_VERSION,
            "judge_schema": JUDGE_SCHEMA,
            "retained_workspaces": retained,
            "isolation_notice": (
                "Claude customization sources, MCP, and Chrome are disabled. "
                "Temporary workspaces prevent fixture cross-contamination, but this "
                "tool does not provide an OS filesystem or network sandbox."
            ),
        },
        "summary": calculate_statistics(trials, args.seed),
        "per_case": per_case_statistics(trials),
        "trials": trials,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--claude-bin", default=os.environ.get("CLAUDE_BIN", "claude"))
    parser.add_argument("--model", required=True)
    parser.add_argument("--effort", choices=EFFORTS, default="high")
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--judge-model", required=True)
    parser.add_argument("--judge-effort", choices=EFFORTS, default="high")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--keep-workspaces", action="store_true")
    args = parser.parse_args(argv)
    if args.rounds <= 0:
        parser.error("--rounds must be greater than zero")
    return args


def main(argv: list[str] | None = None) -> int:
    global TERMINATION_SIGNAL
    TERMINATION_SIGNAL = None
    signal.signal(signal.SIGTERM, signal_handler)
    args = parse_args(argv)
    try:
        check_termination()
        report = run_experiment(args)
        check_termination()
        if args.output is None:
            args.output = Path(
                f"{report['configuration']['suite']}-{report['configuration']['skill_name']}-evaluation.html"
            )
        check_termination()
        output, sidecar = write_report(report, args.output.resolve())
        check_termination()
        print(f"Evaluation complete: {report['summary']['conclusion']}")
        print(f"HTML report: {output}")
        print(f"JSON data: {sidecar}")
        return 0
    except KeyboardInterrupt:
        terminate_active_process()
        return 128 + (TERMINATION_SIGNAL or signal.SIGINT)
    except EvaluationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
