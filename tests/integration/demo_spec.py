"""`scripts/record_demo.py` records the README demo from the real CLI into `docs/assets/demo.svg`.

The specs that record run the script as a subprocess (or its `main`, with a different story),
which runs real git and the real `prepush-ci` in a scratch repository. The recording runs its
steps through `sh -c`, so those specs are skipped on Windows; the specs that read the steps or the
committed asset run on every platform.
"""

import importlib.util
import os
import re
import shlex
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any
from xml.etree import ElementTree

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "record_demo.py"
ASSET = ROOT / "docs" / "assets" / "demo.svg"
README = ROOT / "README.md"
SVG = "{http://www.w3.org/2000/svg}"
EMBED = "https://raw.githubusercontent.com/CapeOfGoodCode/prepush-ci/main/docs/assets/demo.svg"

posix_only = pytest.mark.skipif(
    sys.platform == "win32",
    reason="the recording runs its shell lines through sh -c; only the reading specs run on Windows",
)


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("record_demo", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["record_demo"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script() -> ModuleType:
    return load_script()


def record(
    out: Path,
    *args: str,
    scratch_parent: Path | None = None,
    env: dict[str, str] | None = None,
) -> "subprocess.CompletedProcess[str]":
    """Run the script as the maintainer does, writing the SVG to `out`."""
    inherited = dict(os.environ)
    if scratch_parent is not None:
        inherited["TMPDIR"] = str(scratch_parent)
    return subprocess.run(
        [sys.executable, SCRIPT.as_posix(), "--output", out.as_posix(), *args],
        capture_output=True,
        text=True,
        check=False,
        env={**inherited, **(env or {})},
    )


def steps_of(asset: str) -> list[ElementTree.Element]:
    root = ElementTree.fromstring(asset)
    return [g for g in root.iter(f"{SVG}g") if g.get("class") == "step"]


def step(
    asset: str, command: str, exit_status: str | None = None
) -> ElementTree.Element:
    (found,) = [
        s
        for s in steps_of(asset)
        if s.get("data-command", "").startswith(command)
        and exit_status in (None, s.get("data-exit"))
    ]
    return found


def lines_of(element: ElementTree.Element) -> list[str]:
    return [
        "".join(t.itertext()).rstrip()
        for t in element.iter(f"{SVG}text")
        if "line" in (t.get("class") or "").split()
    ]


@pytest.fixture(scope="module")
def recording(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[tuple[str, Path, "subprocess.CompletedProcess[str]"]]:
    """One recording for the specs that read it: the asset, the parent of its scratch directory
    and the finished process."""
    if sys.platform == "win32":
        pytest.skip("the recording runs its shell lines through sh -c")
    parent = tmp_path_factory.mktemp("scratch-parent")
    out = tmp_path_factory.mktemp("out") / "demo.svg"
    done = record(out, scratch_parent=parent)
    assert done.returncode == 0, done.stdout + done.stderr
    yield out.read_text(encoding="utf-8"), parent, done


# --- The demo is recorded from the real tool --------------------------------------------------


@posix_only
def test_recording_a_scratch_repository_writes_an_svg_and_changes_nothing_in_the_checkout(
    tmp_path: Path,
) -> None:
    def status() -> str:
        return subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout

    before = status()
    out = tmp_path / "out" / "demo.svg"

    done = record(out)

    assert done.returncode == 0, done.stdout + done.stderr
    assert ElementTree.fromstring(out.read_text(encoding="utf-8")).tag == f"{SVG}svg"
    assert status() == before


def test_output_is_the_real_output_of_the_failing_push(
    recording: tuple[str, Path, Any],
) -> None:
    asset = recording[0]

    refused = lines_of(step(asset, "git push origin feat/greeting", "1"))

    assert "FAIL: greet() must end with !" in refused
    assert any(line.startswith("prepush-ci: the check failed") for line in refused)


def test_the_passing_push_shows_the_line_the_check_printed_on_success(
    recording: tuple[str, Path, Any],
) -> None:
    asset = recording[0]
    passing = [
        s
        for s in steps_of(asset)
        if s.get("data-command", "").startswith("git push")
        and s.get("data-exit") == "0"
    ]

    assert [lines_of(s)[0] for s in passing] == ["ok: greet() ends with !"]


def test_long_output_is_cut_to_six_lines_and_an_ellipsis(
    recording: tuple[str, Path, Any],
) -> None:
    shown = lines_of(step(recording[0], "prepush-ci init"))

    assert len(shown) == 7
    assert shown[-1] == "…"
    assert shown[0] == "written: .prepush-ci.toml"


def test_a_line_wider_than_the_screen_fails_the_recording_naming_the_step(
    script: ModuleType, tmp_path: Path
) -> None:
    scratch = script.Scratch(tmp_path, tmp_path / "repo")
    wide = script.Step("git log")
    fits = "x" * script.COLUMNS

    assert script.shown_lines(wide, [fits], scratch) == [fits]
    with pytest.raises(script.RecordingError, match="`git log`"):
        script.shown_lines(wide, [fits + "x"], scratch)


def test_the_push_shows_the_remote_as_one_directory_up_with_no_path_artifact(
    recording: tuple[str, Path, Any],
) -> None:
    pushes = [
        line
        for exit_status in ("0", "1")
        for line in lines_of(step(recording[0], "git push origin", exit_status))
        if "remote.git" in line
    ]

    assert pushes
    assert all(re.search(r"(^|[\s'])\.\./remote\.git'?$", line) for line in pushes)


# --- No machine path in the asset --------------------------------------------------------------


def test_the_asset_holds_no_scratch_directory_no_home_directory_and_no_interpreter_path(
    recording: tuple[str, Path, Any],
) -> None:
    asset, parent, _ = recording
    scratch_forms = {str(parent), str(parent.resolve())}

    for forbidden in {*scratch_forms, str(Path.home()), sys.executable}:
        assert forbidden not in asset


def test_the_scratch_directory_behind_a_symlink_is_replaced_all_the_same(
    tmp_path: Path,
) -> None:
    if sys.platform == "win32":
        pytest.skip("the recording runs its shell lines through sh -c")
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    out = tmp_path / "demo.svg"

    done = record(out, scratch_parent=link)

    asset = out.read_text(encoding="utf-8")
    assert done.returncode == 0, done.stdout + done.stderr
    assert str(real.resolve()) not in asset and str(link) not in asset
    assert "installed: ./.git/prepush-ci/hooks" in lines_of(
        step(asset, "prepush-ci init")
    )


@posix_only
def test_a_step_that_prints_the_home_directory_fails_the_recording_naming_it(
    script: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    leaking = script.Step('echo "$HOME"')
    monkeypatch.setattr(script, "ACTS", ((leaking,),))
    out = tmp_path / "demo.svg"

    status = script.main(["--output", str(out)])

    assert status == 1
    assert not out.exists()


@posix_only
def test_the_output_check_names_the_step_whose_output_holds_the_interpreters_path(
    script: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setattr(sys, "executable", "/opt/elsewhere/bin/python")
    scratch = script.Scratch(tmp_path, tmp_path / "repo")
    leaking = script.Step("python -V")

    with pytest.raises(script.RecordingError, match=re.escape("`python -V`")):
        script.shown_lines(leaking, ["File /opt/elsewhere/bin/python, line 1"], scratch)


def test_the_output_check_names_the_step_whose_output_holds_the_home_directory(
    script: ModuleType, tmp_path: Path
) -> None:
    scratch = script.Scratch(tmp_path, tmp_path / "repo")

    with pytest.raises(script.RecordingError, match="`ls`"):
        script.shown_lines(script.Step("ls"), [f"{Path.home()}/notes.txt"], scratch)


# --- One command regenerates the asset ---------------------------------------------------------


def test_the_help_names_the_command_that_regenerates_the_asset() -> None:
    done = subprocess.run(
        [sys.executable, SCRIPT.as_posix(), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert done.returncode == 0
    assert "uv run python scripts/record_demo.py" in done.stdout


# --- The install step is typed, not run --------------------------------------------------------


def test_only_the_install_is_a_step_that_is_not_run(script: ModuleType) -> None:
    steps = [s for act in script.ACTS for s in act]

    assert [s.command for s in steps if not s.run] == ["uv tool install prepush-ci"]


def test_the_asset_marks_the_install_step_and_every_other_step_has_a_status(
    recording: tuple[str, Path, Any],
) -> None:
    steps = steps_of(recording[0])

    not_run = [s for s in steps if s.get("data-run") == "false"]
    assert [s.get("data-command") for s in not_run] == ["uv tool install prepush-ci"]
    assert "data-exit" not in not_run[0].attrib and lines_of(not_run[0]) == []
    assert all(s.get("data-exit") is not None for s in steps if s not in not_run)
    assert all(s.get("data-run") == "true" for s in steps if s not in not_run)


# --- The demo tells the story in order ---------------------------------------------------------


def test_the_refused_push_comes_before_the_passing_one_and_verify_is_the_last_command(
    recording: tuple[str, Path, Any],
) -> None:
    steps = steps_of(recording[0])
    pushes = [s for s in steps if s.get("data-command", "").startswith("git push")]
    commands = [s.get("data-command", "") for s in steps]

    assert [s.get("data-exit") for s in pushes] == ["1", "0"]
    assert commands[-1] == "prepush-ci verify HEAD"
    assert steps[-1].get("data-exit") == "0"
    assert commands.index("uv tool install prepush-ci") < next(
        i for i, c in enumerate(commands) if c.startswith("prepush-ci init")
    )


def test_each_commit_is_typed_with_the_opt_in_on_its_line(
    recording: tuple[str, Path, Any],
) -> None:
    commits = [
        s.get("data-command", "")
        for s in steps_of(recording[0])
        if " git commit" in s.get("data-command", "")
    ]

    assert len(commits) == 2
    assert all(
        c.startswith("PREPUSH_CI=full ") or " PREPUSH_CI=full git commit" in c
        for c in commits
    )


def test_the_shown_commit_message_has_the_trailer(
    recording: tuple[str, Path, Any],
) -> None:
    shown = lines_of(step(recording[0], "git log -1 --format=%B"))

    assert "Prepush-CI: full" in shown


@posix_only
def test_an_inherited_opt_out_changes_nothing_in_the_recorded_story(
    tmp_path: Path, recording: tuple[str, Path, Any]
) -> None:
    out = tmp_path / "demo.svg"

    done = record(out, env={"PREPUSH_CI": "off"})

    assert done.returncode == 0, done.stdout + done.stderr
    statuses = [s.get("data-exit") for s in steps_of(out.read_text(encoding="utf-8"))]
    assert statuses == [s.get("data-exit") for s in steps_of(recording[0])]
    assert "Prepush-CI: full" in lines_of(
        step(out.read_text(encoding="utf-8"), "git log -1 --format=%B")
    )


# --- The recording runs on POSIX shells --------------------------------------------------------


@posix_only
def test_steps_run_through_sh_and_the_shim_is_a_sh_script(
    script: ModuleType, tmp_path: Path
) -> None:
    scratch = script.make_scratch(tmp_path, 0.0)

    shell = script.run_step(scratch, script.Step('echo "$0"'))

    assert shell.output == ["sh"]
    shim = (tmp_path / "bin" / "prepush-ci").read_text(encoding="utf-8")
    assert shim.splitlines()[0] == "#!/bin/sh"


# --- The recording fails on a wrong status -----------------------------------------------------


def story_with(script: ModuleType, replaced: str, by: Any) -> tuple[Any, ...]:
    """The story with the step that starts with `replaced` swapped for `by`."""
    return tuple(
        tuple(by if s.command.startswith(replaced) else s for s in act)
        for act in script.ACTS
    )


@posix_only
def test_a_refused_push_that_exits_zero_fails_the_recording_and_writes_no_asset(
    script: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    easy = script.Step("git status --short", refused=True)
    monkeypatch.setattr(script, "ACTS", story_with(script, "git push", easy))
    out = tmp_path / "demo.svg"

    status = script.main(["--output", str(out)])

    assert status == 1
    assert not out.exists()
    error = capsys.readouterr().err
    assert "git status --short" in error and "exited 0" in error


@posix_only
def test_a_step_that_exits_non_zero_where_the_story_needs_zero_fails_the_recording(
    script: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    broken = script.Step("git log -1 --format=%B && false")
    monkeypatch.setattr(script, "ACTS", story_with(script, "git log", broken))
    out = tmp_path / "demo.svg"

    status = script.main(["--output", str(out)])

    assert status == 1
    assert not out.exists()
    assert "exited 1" in capsys.readouterr().err


# --- Every command of the demo exists ----------------------------------------------------------

OPERATORS = {"&&", "||", ";", "|"}


def prepush_ci_invocations(command: str) -> list[str]:
    """The `prepush-ci ...` invocations of a shell line, found by its words, so that a commit
    message that mentions the tool is not taken for one."""
    found: list[str] = []
    words = shlex.split(command)
    at_command_position = True
    for index, word in enumerate(words):
        if word in OPERATORS:
            at_command_position = True
            continue
        if at_command_position and re.fullmatch(r"[A-Za-z_]\w*=.*", word):
            continue
        if at_command_position and word == "prepush-ci":
            rest = []
            for after in words[index + 1 :]:
                if after in OPERATORS:
                    break
                rest.append(after)
            found.append(shlex.join(["prepush-ci", *rest]))
        at_command_position = False
    return found


def problems_of(invocations: Any, commands: list[str]) -> list[str]:
    return [
        problem
        for command in commands
        for invocation in prepush_ci_invocations(command)
        for problem in invocations.problems(f"`{invocation}`")
    ]


def test_the_shipped_steps_name_no_command_and_no_option_the_cli_lacks(
    script: ModuleType, invocations: Any
) -> None:
    commands = [s.command for act in script.ACTS for s in act]

    assert sum(len(prepush_ci_invocations(c)) for c in commands) == 2
    assert problems_of(invocations, commands) == []


def test_a_step_with_an_option_the_cli_lacks_is_reported(invocations: Any) -> None:
    assert problems_of(invocations, ["prepush-ci run --fast"]) == [
        "unknown option --fast for run"
    ]


# --- The asset shows the typing ----------------------------------------------------------------


def test_each_command_is_revealed_in_as_many_steps_as_it_has_characters(
    recording: tuple[str, Path, Any],
) -> None:
    asset = recording[0]

    for element in steps_of(asset):
        command = element.get("data-command", "")
        assert element.get("data-chars") == str(len(command))
        reveal = re.search(
            rf"@keyframes {element.get('id')}t\{{.*?steps\((\d+),start\)", asset
        )
        assert reveal is not None and int(reveal.group(1)) == len(command)
    assert "monospace" in asset


def test_the_output_lines_start_after_the_typing_and_one_after_the_other(
    recording: tuple[str, Path, Any],
) -> None:
    for element in steps_of(recording[0]):
        typed = float(element.get("data-typed", "nan"))
        starts = [
            float(t.get("data-start", "nan"))
            for t in element.iter(f"{SVG}text")
            if t.get("data-start")
        ]
        assert starts == sorted(starts)
        assert all(start >= typed for start in starts)
        assert len(set(starts)) == len(starts)


def test_the_keyframes_of_an_output_line_start_where_its_attribute_says(
    recording: tuple[str, Path, Any],
) -> None:
    asset = recording[0]
    duration = float(ElementTree.fromstring(asset).get("data-duration", "nan"))
    refused = step(asset, "git push origin feat/greeting", "1")
    first = next(t for t in refused.iter(f"{SVG}text") if t.get("data-start"))
    name = re.search(r"animation-name:(\S+?)\"?$", first.get("style", ""))
    assert name is not None

    frames = re.search(
        rf"@keyframes {name.group(1)}\{{0%\{{opacity:0\}}([\d.]+)%", asset
    )

    assert frames is not None
    assert float(frames.group(1)) == pytest.approx(
        100 * float(first.get("data-start", "nan")) / duration, abs=0.01
    )


# --- The animation lasts between 40 and 60 seconds ------------------------------------------


def test_the_shipped_asset_is_paced_to_be_followed_and_its_durations_agree(
    script: ModuleType,
) -> None:
    asset = ASSET.read_text(encoding="utf-8")

    assert script.timeline_problems(asset) == []
    assert 40 <= float(ElementTree.fromstring(asset).get("data-duration", "nan")) <= 60


@posix_only
def test_recordings_of_a_fast_and_a_slow_check_have_the_same_duration(
    tmp_path: Path,
) -> None:
    durations = []
    for delay in ("0", "2"):
        out = tmp_path / f"demo{delay}.svg"
        done = record(out, "--check-delay", delay)
        assert done.returncode == 0, done.stdout + done.stderr
        durations.append(
            ElementTree.fromstring(out.read_text("utf-8")).get("data-duration")
        )

    assert durations[0] == durations[1]


def crafted(duration: float, last_end: float, animation: float | None = None) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" data-duration="{duration}">'
        f"<style>.a{{animation-duration:{animation or duration}s}}</style>"
        f'<g class="step" data-command="git push" data-start="1" data-end="{last_end}"/>'
        "</svg>"
    )


def test_an_asset_of_61_seconds_is_reported_as_above_60_seconds(
    script: ModuleType,
) -> None:
    assert script.timeline_problems(crafted(61, 20)) == [
        "the duration 61 is above 60 seconds"
    ]


def test_an_asset_of_39_seconds_is_reported_as_below_40_seconds(
    script: ModuleType,
) -> None:
    assert script.timeline_problems(crafted(39, 20)) == [
        "the duration 39 is below 40 seconds"
    ]


def test_an_asset_of_40_and_one_of_60_seconds_are_not_reported(
    script: ModuleType,
) -> None:
    assert script.timeline_problems(crafted(40, 20)) == []
    assert script.timeline_problems(crafted(60, 20)) == []


def test_a_step_that_ends_after_the_duration_is_reported(script: ModuleType) -> None:
    assert script.timeline_problems(crafted(45, 46)) == [
        "step `git push` ends at 46, after the duration 45"
    ]


def test_an_asset_whose_css_duration_differs_from_its_attribute_is_reported(
    script: ModuleType,
) -> None:
    assert script.timeline_problems(crafted(45, 10, animation=50)) == [
        "data-duration 45 differs from the animation duration 50"
    ]


def test_a_story_that_would_run_past_60_seconds_is_not_recorded(
    script: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(script, "TYPING_PER_CHARACTER", 1.0)
    out = tmp_path / "demo.svg"
    if sys.platform == "win32":
        pytest.skip("the recording runs its shell lines through sh -c")

    assert script.main(["--output", str(out)]) == 1
    assert not out.exists()


FIRST_RECORDING_TYPING = 0.03  # seconds per typed character, at 59332e7
FIRST_RECORDING_PAUSE = (
    0.75  # seconds from the end of an output to the next command, at 59332e7
)


def test_each_character_is_typed_slower_than_in_the_first_recording() -> None:
    steps = steps_of(ASSET.read_text(encoding="utf-8"))

    paces = [
        (float(s.get("data-typed", "nan")) - float(s.get("data-start", "nan")))
        / int(s.get("data-chars", "0"))
        for s in steps
    ]
    assert min(paces) > FIRST_RECORDING_TYPING


def test_the_pause_after_each_output_is_longer_than_in_the_first_recording() -> None:
    steps = steps_of(ASSET.read_text(encoding="utf-8"))
    same_screen = [
        (before, after)
        for before, after in zip(steps, steps[1:], strict=False)
        if (before.get("id") or "").split("_")[0]
        == (after.get("id") or "").split("_")[0]
    ]

    pauses = [
        float(after.get("data-start", "nan")) - float(before.get("data-end", "nan"))
        for before, after in same_screen
    ]
    assert pauses
    assert min(pauses) > FIRST_RECORDING_PAUSE


@posix_only
def test_a_story_that_would_run_under_40_seconds_is_not_recorded(
    script: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(script, "TYPING_PER_CHARACTER", 0.0)
    out = tmp_path / "demo.svg"

    assert script.main(["--output", str(out)]) == 1
    assert not out.exists()


# --- The README shows the demo near the top ----------------------------------------------------


def readme_head() -> str:
    text = README.read_text(encoding="utf-8")
    return text[: re.search(r"^## ", text, re.MULTILINE).start()]  # type: ignore[union-attr]


def embed_alt() -> str | None:
    found = re.search(
        rf"<img[^>]*src=\"{re.escape(EMBED)}\"[^>]*alt=\"([^\"]*)\"|"
        rf"<img[^>]*alt=\"([^\"]*)\"[^>]*src=\"{re.escape(EMBED)}\"|"
        rf"!\[([^\]]*)\]\({re.escape(EMBED)}\)",
        readme_head(),
    )
    return next((g for g in found.groups() if g), "") if found else None


def test_the_readme_embeds_the_demo_through_the_absolute_address_before_its_first_section() -> (
    None
):
    alt = embed_alt()

    assert alt is not None
    assert alt.strip() != ""


def test_the_embedded_file_exists_in_the_checkout_and_is_an_svg() -> None:
    path = ROOT / EMBED.removeprefix(
        "https://raw.githubusercontent.com/CapeOfGoodCode/prepush-ci/main/"
    )

    assert path == ASSET
    assert ElementTree.parse(path).getroot().tag == f"{SVG}svg"


def test_the_alternative_text_names_the_setup_the_refused_push_and_the_passing_push() -> (
    None
):
    alt = (embed_alt() or "").lower()

    assert "set up" in alt
    assert "refused" in alt
    assert "passing" in alt


def test_every_command_fits_the_columns_of_the_screen_after_its_prompt(
    script: ModuleType,
) -> None:
    commands = [s.command for act in script.ACTS for s in act]

    assert all(len("$ " + command) <= script.COLUMNS for command in commands)


def test_the_screen_of_a_refused_push_stays_longer_than_one_that_went_through(
    script: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(script, "MIN_SECONDS", 0.0)  # three short acts are not a story

    def act(status: int) -> list[Any]:
        return [script.Recorded(script.Step("git push"), ["one line"], status)]

    spans = script.schedule([act(1), act(0), act(0)])[1]

    assert spans[0][1] - spans[0][0] > spans[1][1] - spans[1][0]
