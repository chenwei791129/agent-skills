from __future__ import annotations

import importlib.util
import json
import signal
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

MODULE_PATH = Path(__file__).parents[1] / "evaluate_skill.py"
SPEC = importlib.util.spec_from_file_location("evaluate_skill", MODULE_PATH)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def write_skill(path: Path, name: str | None = None) -> Path:
    path.mkdir()
    (path / "SKILL.md").write_text(
        f"---\nname: {name or path.name}\ndescription: test\n---\n", encoding="utf-8"
    )
    return path


def write_cases(path: Path, cases: list[dict] | None = None) -> Path:
    path.write_text(
        json.dumps(
            {
                "name": "suite",
                "cases": cases
                or [{"id": "one", "prompt": "Do it", "rubric": "Be correct"}],
            }
        ),
        encoding="utf-8",
    )
    return path


def result(arm: str, response: str = "answer", error: str | None = None):
    return module.RunResult(
        arm, ["claude"], 0, 1.0, response, "", "", {}, {}, 0.1, [], error
    )


def test_load_skill_validates_name(tmp_path: Path) -> None:
    skill = write_skill(tmp_path / "target", "other")
    with pytest.raises(module.EvaluationError, match="does not match"):
        module.load_skill(skill)


def test_load_cases_rejects_missing_fields_duplicate_and_fixture(
    tmp_path: Path,
) -> None:
    cases = write_cases(
        tmp_path / "cases.json",
        [
            {"id": "same", "prompt": "ok", "rubric": "ok"},
            {"id": "same", "prompt": "ok", "rubric": "ok"},
        ],
    )
    with pytest.raises(module.EvaluationError, match="Duplicate"):
        module.load_cases(cases)

    write_cases(cases, [{"id": "x", "prompt": "", "rubric": "ok"}])
    with pytest.raises(module.EvaluationError, match="prompt"):
        module.load_cases(cases)

    write_cases(
        cases,
        [{"id": "x", "prompt": "ok", "rubric": "ok", "fixture": "missing"}],
    )
    with pytest.raises(module.EvaluationError, match="Fixture"):
        module.load_cases(cases)


def test_validate_launcher_checks_static_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flags = (
        "--print --output-format --model --effort --no-session-persistence "
        "--permission-mode --disable-slash-commands --json-schema "
        "--setting-sources --strict-mcp-config --mcp-config --no-chrome --tools"
    )
    calls: list[list[str]] = []

    class Process:
        returncode = 0

        def __init__(self, command, **kwargs):
            self.command = command
            calls.append(command)

        def communicate(self, timeout=None):
            return ("1.0", "") if "--version" in self.command else (flags, "")

        def poll(self):
            return self.returncode

    monkeypatch.setattr(module.subprocess, "Popen", Process)
    monkeypatch.setattr(module.signal, "pthread_sigmask", lambda *args: set())
    assert module.validate_launcher("claude") == "1.0"
    assert calls == [["claude", "--version"], ["claude", "--help"]]


def test_launcher_metadata_child_is_terminated_on_signal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    class Process:
        returncode = -15

        def __init__(self, command, **kwargs):
            pass

        def communicate(self, timeout=None):
            module.signal_handler(signal.SIGTERM, None)
            return "", "terminated"

        def poll(self):
            return None

        def terminate(self):
            calls.append("terminate")

        def wait(self, timeout=None):
            calls.append("wait")

    monkeypatch.setattr(module.subprocess, "Popen", Process)
    monkeypatch.setattr(module.signal, "pthread_sigmask", lambda *args: set())
    module.TERMINATION_SIGNAL = None
    with pytest.raises(KeyboardInterrupt):
        module.run_launcher_metadata(["claude", "--version"])
    assert calls == ["terminate", "wait"]
    module.TERMINATION_SIGNAL = None


def test_parse_args_rejects_invalid_rounds_removed_budget_and_effort() -> None:
    base = [
        "--skill",
        "x",
        "--cases",
        "x",
        "--model",
        "m",
        "--judge-model",
        "j",
    ]
    with pytest.raises(SystemExit):
        module.parse_args(base + ["--rounds", "0"])
    with pytest.raises(SystemExit):
        module.parse_args(base + ["--max-budget-usd", "1"])
    with pytest.raises(SystemExit):
        module.parse_args(base + ["--effort", "extreme"])


def test_build_commands_include_arm_model_and_effort() -> None:
    with_command = module.build_command("/claude", "/target\nDo it", "model", "xhigh")
    without_command = module.build_command(
        "/claude", "Do it", "model", "xhigh", without_skill=True
    )
    assert with_command[-1].startswith("/target")
    assert "--disable-slash-commands" not in with_command
    assert "--disable-slash-commands" in without_command
    assert with_command[with_command.index("--model") + 1] == "model"
    assert with_command[with_command.index("--effort") + 1] == "xhigh"
    assert "--max-budget-usd" not in with_command
    for flag in (
        "--setting-sources",
        "--strict-mcp-config",
        "--mcp-config",
        "--no-chrome",
    ):
        assert flag in with_command
    judge_command = module.build_command(
        "/claude", "judge", "judge", "high", disable_tools=True
    )
    assert judge_command[judge_command.index("--tools") + 1] == ""


def test_workspace_copies_fixture_without_cross_contamination(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    source = fixture / "source.txt"
    source.write_text("original", encoding="utf-8")
    skill = write_skill(tmp_path / "skill")
    first = module.make_workspace(str(fixture), skill, "skill")
    second = module.make_workspace(str(fixture), skill, "skill")
    (first / "source.txt").write_text("changed", encoding="utf-8")
    assert source.read_text(encoding="utf-8") == "original"
    assert (second / "source.txt").read_text(encoding="utf-8") == "original"
    assert (first / ".claude/skills/skill/SKILL.md").is_file()
    assert (second / ".claude/skills/skill/SKILL.md").is_file()


def test_load_skill_requires_standalone_closing_delimiter(tmp_path: Path) -> None:
    skill = tmp_path / "skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "---\nname: skill\ndescription: includes --- inline\nbody", encoding="utf-8"
    )
    with pytest.raises(module.EvaluationError, match="not closed"):
        module.load_skill(skill)


def test_root_symlink_paths_are_rejected(tmp_path: Path) -> None:
    actual_fixture = tmp_path / "actual-fixture"
    actual_fixture.mkdir()
    fixture_link = tmp_path / "fixture-link"
    fixture_link.symlink_to(actual_fixture, target_is_directory=True)
    cases = write_cases(
        tmp_path / "cases.json",
        [{"id": "x", "prompt": "ok", "rubric": "ok", "fixture": "fixture-link"}],
    )
    with pytest.raises(module.EvaluationError, match="symlink"):
        module.load_cases(cases)

    actual_skill = write_skill(tmp_path / "actual-skill", "skill-link")
    skill_link = tmp_path / "skill-link"
    skill_link.symlink_to(actual_skill, target_is_directory=True)
    with pytest.raises(module.EvaluationError, match="symlink"):
        module.reject_symlink_components(skill_link, "Skill")


def test_parent_component_and_cases_root_symlinks_are_rejected(tmp_path: Path) -> None:
    actual_parent = tmp_path / "actual-parent"
    actual_parent.mkdir()
    skill = write_skill(actual_parent / "skill")
    cases = write_cases(actual_parent / "cases.json")
    parent_link = tmp_path / "linked-parent"
    parent_link.symlink_to(actual_parent, target_is_directory=True)

    with pytest.raises(module.EvaluationError, match="symlink"):
        module.reject_symlink_components(parent_link / skill.name, "Skill")
    with pytest.raises(module.EvaluationError, match="symlink"):
        module.load_cases(parent_link / cases.name)

    cases_link = tmp_path / "cases-link.json"
    cases_link.symlink_to(cases)
    with pytest.raises(module.EvaluationError, match="symlink"):
        module.load_cases(cases_link)


def test_workspace_rejects_fixture_and_skill_symlinks(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    target = tmp_path / "outside"
    target.write_text("outside", encoding="utf-8")
    (fixture / "link").symlink_to(target)
    skill = write_skill(tmp_path / "skill")
    with pytest.raises(module.EvaluationError, match="symlink"):
        module.make_workspace(str(fixture), skill, "skill")

    (fixture / "link").unlink()
    (skill / "link").symlink_to(target)
    with pytest.raises(module.EvaluationError, match="symlink"):
        module.make_workspace(str(fixture), skill, "skill")


def test_workspace_rejects_fixture_existing_skills(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture"
    (fixture / ".claude" / "skills" / "other").mkdir(parents=True)
    skill = write_skill(tmp_path / "skill")
    cases = write_cases(
        tmp_path / "cases.json",
        [{"id": "x", "prompt": "ok", "rubric": "ok", "fixture": "fixture"}],
    )
    with pytest.raises(module.EvaluationError, match=r"\.claude/skills"):
        module.load_cases(cases)
    with pytest.raises(module.EvaluationError, match=r"\.claude/skills"):
        module.make_workspace(str(fixture), skill, "skill")


def test_parse_cli_json_and_judge_output() -> None:
    data, response, usage, cost = module.parse_cli_json(
        json.dumps(
            {
                "result": "hello",
                "usage": {"input_tokens": 2},
                "total_cost_usd": 0.2,
            }
        )
    )
    assert data["result"] == response == "hello"
    assert usage == {"input_tokens": 2}
    assert cost == 0.2

    judge = result("judge")
    judge.cli_json = {
        "structured_output": {
            "a_score": 80,
            "b_score": 70,
            "preference": "A",
            "confidence": 0.8,
            "rationale": "Better",
        }
    }
    assert module.parse_judge(judge)["a_score"] == 80


def test_run_command_records_failure_and_parses_nonzero_stdout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class Process:
        returncode = 4

        def communicate(self):
            return json.dumps({"result": "partial", "total_cost_usd": 0.3}), "failed"

        def poll(self):
            return self.returncode

    monkeypatch.setattr(module.subprocess, "Popen", lambda *a, **kw: Process())
    run = module.run_command(["claude"], tmp_path, "with")
    assert run.returncode == 4
    assert run.error == "Claude exited with 4"
    assert run.response == "partial"
    assert run.cost_usd == 0.3
    assert run.stdout


def test_identity_disclosure_detects_slash_and_skill_body(tmp_path: Path) -> None:
    skill = tmp_path / "secret-skill"
    body = "unique complete skill body"
    assert module.identity_disclosure(
        result("with", "Used /secret-skill"), "secret-skill", skill, body
    )
    run = result("with")
    run.changes = [{"after": {"text": body}}]
    assert module.identity_disclosure(run, "secret-skill", skill, body)

    long_body = " ".join(f"instruction-{index}" for index in range(100))
    near_copy = long_body.replace("instruction-50", "changed-instruction")
    assert module.identity_disclosure(
        result("with", near_copy), "secret-skill", skill, long_body
    )
    partial = " ".join(f"instruction-{index}" for index in range(20, 41))
    assert module.identity_disclosure(
        result("with", partial), "secret-skill", skill, long_body
    )
    medium_body = " ".join(f"distinctive-token-{index}" for index in range(9))
    assert 80 <= len(medium_body) < 200
    excerpt = " ".join(medium_body.split()[1:8])
    assert module.identity_disclosure(
        result("with", excerpt), "secret-skill", skill, medium_body
    )
    wordy_body = " ".join(f"distinctive-token-{index}" for index in range(80))
    five_word_excerpt = " ".join(wordy_body.split()[10:15])
    eleven_word_excerpt = " ".join(wordy_body.split()[30:39])
    multiple_excerpts = (
        " ".join(wordy_body.split()[5:10])
        + " unrelated separator "
        + " ".join(wordy_body.split()[50:55])
    )
    assert 80 <= len(five_word_excerpt) < 200
    assert 80 <= len(eleven_word_excerpt) < 200
    assert module.identity_disclosure(
        result("with", five_word_excerpt), "secret-skill", skill, wordy_body
    )
    assert module.identity_disclosure(
        result("with", eleven_word_excerpt), "secret-skill", skill, wordy_body
    )
    assert module.identity_disclosure(
        result("with", multiple_excerpts), "secret-skill", skill, wordy_body
    )
    generic_body = "This is important. " * 10
    assert not module.identity_disclosure(
        result("with", "This is important."), "secret-skill", skill, generic_body
    )


def test_judge_prompt_redacts_skill_identity(tmp_path: Path) -> None:
    skill = tmp_path / "secret-skill"
    prompt = module.judge_prompt(
        {"prompt": "task", "rubric": "rubric"},
        result("with", f"Used /secret-skill from {skill}"),
        result("without", "plain"),
        "secret-skill",
        skill,
    )
    assert "secret-skill" not in prompt
    assert str(skill) not in prompt
    assert "[TARGET_SKILL_REDACTED]" in prompt


def test_run_experiment_stops_after_signal_and_cleans_workspace(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    skill = write_skill(tmp_path / "skill")
    cases = write_cases(tmp_path / "cases.json")
    created: list[Path] = []
    original_make_workspace = module.make_workspace

    def tracked_workspace(*args, **kwargs):
        workspace = original_make_workspace(*args, **kwargs)
        created.append(workspace)
        return workspace

    calls: list[str] = []

    def interrupted_run(command, workspace, arm):
        calls.append(arm)
        module.TERMINATION_SIGNAL = signal.SIGTERM
        return result(arm)

    monkeypatch.setattr(module, "resolve_launcher", lambda command: "/claude")
    monkeypatch.setattr(module, "validate_launcher", lambda *a, **kw: "1.0")
    monkeypatch.setattr(module, "make_workspace", tracked_workspace)
    monkeypatch.setattr(module, "run_command", interrupted_run)
    args = SimpleNamespace(
        skill=skill,
        cases=cases,
        claude_bin="claude",
        seed=1,
        rounds=1,
        model="model",
        effort="high",
        judge_model="judge",
        judge_effort="high",
        keep_workspaces=False,
    )
    module.TERMINATION_SIGNAL = None
    with pytest.raises(KeyboardInterrupt):
        module.run_experiment(args)
    assert len(calls) == 1
    assert created and all(not path.exists() for path in created)
    module.TERMINATION_SIGNAL = None


def test_signal_during_workspace_creation_prevents_spawn(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    skill = write_skill(tmp_path / "skill")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    spawned: list[bool] = []

    def signal_workspace(*args, **kwargs):
        module.TERMINATION_SIGNAL = signal.SIGTERM
        return workspace

    monkeypatch.setattr(module, "make_workspace", signal_workspace)
    monkeypatch.setattr(module, "run_command", lambda *a, **kw: spawned.append(True))
    monkeypatch.setattr(module, "resolve_launcher", lambda command: "/claude")
    monkeypatch.setattr(module, "validate_launcher", lambda *a, **kw: "1.0")
    cases = write_cases(tmp_path / "cases.json")
    args = SimpleNamespace(
        skill=skill,
        cases=cases,
        claude_bin="claude",
        seed=1,
        rounds=1,
        model="m",
        effort="high",
        judge_model="j",
        judge_effort="high",
        keep_workspaces=False,
    )
    module.TERMINATION_SIGNAL = None
    with pytest.raises(KeyboardInterrupt):
        module.run_experiment(args)
    assert not spawned
    module.TERMINATION_SIGNAL = None


def test_signal_during_snapshot_prevents_spawn(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    spawned: list[bool] = []

    def signal_snapshot(workspace):
        module.TERMINATION_SIGNAL = signal.SIGTERM
        return {}

    monkeypatch.setattr(module, "snapshot", signal_snapshot)
    monkeypatch.setattr(
        module.subprocess, "Popen", lambda *a, **kw: spawned.append(True)
    )
    module.TERMINATION_SIGNAL = None
    with pytest.raises(KeyboardInterrupt):
        module.run_command(["claude"], tmp_path, "with")
    assert not spawned
    module.TERMINATION_SIGNAL = None


def test_terminate_active_process_kills_after_timeout() -> None:
    calls: list[str] = []

    class Process:
        def poll(self):
            return None

        def terminate(self):
            calls.append("terminate")

        def wait(self, timeout=None):
            calls.append("wait")
            if timeout is not None:
                raise module.subprocess.TimeoutExpired("claude", timeout)

        def kill(self):
            calls.append("kill")

    module.ACTIVE_PROCESS = Process()
    module.terminate_active_process()
    assert calls == ["terminate", "wait", "kill", "wait"]
    module.ACTIVE_PROCESS = None


def test_seeded_order_is_reproducible() -> None:
    import random

    def orders(seed: int):
        rng = random.Random(seed)
        output = []
        for _ in range(20):
            arms = ["with", "without"]
            blind = ["with", "without"]
            rng.shuffle(arms)
            rng.shuffle(blind)
            output.append((arms, blind))
        return output

    assert orders(42) == orders(42)
    assert orders(42) != orders(43)


def trial(value: float, case_id: str = "case") -> dict:
    return {
        "case_id": case_id,
        "difference": value,
        "with_score": 50 + value,
        "without_score": 50,
    }


def test_statistics_positive_negative_tie_small_and_zero_variance() -> None:
    positive = module.calculate_statistics([trial(10.0) for _ in range(8)], 1)
    negative = module.calculate_statistics([trial(-10.0) for _ in range(8)], 1)
    ties = module.calculate_statistics([trial(0.0) for _ in range(4)], 1)
    small = module.calculate_statistics([trial(5.0)], 1)
    assert positive["mean_difference"] == 10
    assert positive["conclusion"] == "significant improvement"
    assert positive["cohens_dz"] is None
    assert negative["conclusion"] == "significant regression"
    assert ties["cohens_dz"] == 0
    assert ties["conclusion"] == "insufficient evidence"
    assert small["conclusion"] == "insufficient evidence"

    failed = {"case_id": "case", "difference": None}
    failure_heavy = module.calculate_statistics([trial(10.0), failed], 1)
    assert failure_heavy["failure_rate"] == 0.5
    assert failure_heavy["conclusion"] == "insufficient data due to failures"


def test_external_cli_example_is_describe_only() -> None:
    example_path = MODULE_PATH.parents[1] / "examples" / "cases.example.json"
    suite = json.loads(example_path.read_text(encoding="utf-8"))
    case = next(
        case for case in suite["cases"] if case["id"] == "external-cli-procedure"
    )
    prompt = case["prompt"].casefold()
    rubric = case["rubric"].casefold()

    for requirement in (
        "do not execute commands",
        "do not use tools",
        "do not modify files or external state",
        "synthetic placeholders",
    ):
        assert requirement in prompt
    for failure in (
        "tool use",
        "external-state mutation",
        "claim that publication was completed",
    ):
        assert failure in rubric


def test_snapshot_never_reads_created_symlink(tmp_path: Path) -> None:
    outside = tmp_path.parent / "sensitive.txt"
    outside.write_text("secret-value", encoding="utf-8")
    (tmp_path / "leak").symlink_to(outside)
    captured = module.snapshot(tmp_path)
    assert captured["leak"]["symlink"] is True
    assert "text" not in captured["leak"]
    assert "secret-value" not in json.dumps(captured)


def test_snapshot_caps_binary_and_ignores_injected_skill(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "small.txt").write_text("safe", encoding="utf-8")
    (tmp_path / "binary.bin").write_bytes(b"\0binary")
    injected = tmp_path / ".claude/skills/target"
    injected.mkdir(parents=True)
    (injected / "SKILL.md").write_text("secret", encoding="utf-8")
    monkeypatch.setattr(module, "SNAPSHOT_FILE_LIMIT", 3)
    snapshot = module.snapshot(tmp_path)
    assert snapshot["small.txt"]["omitted"]
    assert snapshot["binary.bin"]["sha256"]
    assert not any(name.startswith(".claude/skills") for name in snapshot)


def test_html_escapes_dynamic_content_and_writes_sidecar(tmp_path: Path) -> None:
    report = {
        "configuration": {"skill_name": "<script>alert(1)</script>"},
        "summary": {
            "conclusion": "insufficient evidence",
            "valid_pairs": 0,
            "failed_pairs": 1,
            "failure_rate": 1.0,
        },
        "per_case": [
            {"case_id": "<script>x</script>", "valid_pairs": 0, "mean_difference": None}
        ],
        "trials": [
            {
                "case_id": "<b>x</b>",
                "round": 1,
                "status": "failed",
                "payload": "<script>bad</script>",
            }
        ],
    }
    output, sidecar = module.write_report(report, tmp_path / "report.html")
    rendered = output.read_text(encoding="utf-8")
    assert "一句話結論" in rendered
    assert "方法與限制" in rendered
    assert "insufficient evidence" in rendered
    assert 'class="score-card with-card"' in rendered
    assert '<a href="report.json">' in rendered
    assert "<script>bad</script>" not in rendered
    assert "&lt;script&gt;bad&lt;/script&gt;" in rendered
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered
    assert output != sidecar
    assert sidecar.name == "report.json"
    assert json.loads(sidecar.read_text(encoding="utf-8")) == report

    json_output, json_sidecar = module.write_report(report, tmp_path / "report.json")
    assert json_output.name == "report.json.html"
    assert json_sidecar.name == "report.json.json"
    assert json_output != json_sidecar

    bare_output, bare_sidecar = module.write_report(report, tmp_path / "report")
    assert bare_output.name == "report.html"
    assert bare_sidecar.name == "report.json"
    assert bare_output != bare_sidecar


def test_signal_handler_terminates_child(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    class Process:
        def poll(self):
            return None

        def terminate(self):
            calls.append("terminate")

        def wait(self, timeout=None):
            calls.append("wait")

    module.ACTIVE_PROCESS = Process()
    module.TERMINATION_SIGNAL = None
    module.signal_handler(signal.SIGTERM, None)
    assert module.TERMINATION_SIGNAL == signal.SIGTERM
    assert calls == ["terminate", "wait"]
    module.ACTIVE_PROCESS = None


def test_main_returns_signal_exit_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    args = SimpleNamespace()
    monkeypatch.setattr(module, "parse_args", lambda argv: args)

    def interrupt(_args):
        raise KeyboardInterrupt

    monkeypatch.setattr(module, "run_experiment", interrupt)
    module.TERMINATION_SIGNAL = None
    assert module.main([]) == 130

    def term_interrupt(_args):
        module.TERMINATION_SIGNAL = signal.SIGTERM
        raise KeyboardInterrupt

    monkeypatch.setattr(module, "run_experiment", term_interrupt)
    assert module.main([]) == 143
