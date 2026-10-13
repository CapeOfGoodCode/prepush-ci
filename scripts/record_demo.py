"""Record the terminal demo of the README: `docs/assets/demo.svg`.

Regenerate it with:

    uv run python scripts/record_demo.py

The script makes an empty scratch repository with a bare remote, runs each step of `ACTS` there
with the real `prepush-ci` (a shim that starts `sys.executable -m prepush_ci`) and writes an
animated SVG from the output and exit status each command really had. Only the timing is made
up: a fixed schedule, so a slow machine cannot make the animation longer. The recording runs the
steps through `sh -c`, so it needs a POSIX system; only standard-library modules and git are used.
"""

import argparse
import os
import re
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree
from xml.sax.saxutils import escape, quoteattr

ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / "docs" / "assets" / "demo.svg"
COMMAND = "uv run python scripts/record_demo.py"

BRANCH = "feat/greeting"
INSTALL = "uv tool install prepush-ci"
SETUP_COMMIT = "chore: set up prepush-ci"
FIX_COMMIT = "fix: end the greeting with !"
SUCCESS_LINE = "ok: greet() ends with !"
FAILURE_LINE = "FAIL: greet() must end with !"

# The screen, cleared between acts. Wider than 80 columns so that the longest line of the story,
# the answer of `verify` with its 40-character sha (91 columns), is shown whole; as tall as the
# longest act needs.
COLUMNS = 92
ROWS = 12
MAX_OUTPUT_LINES = 6
CUT = "…"
MIN_SECONDS = 40.0  # slow enough to follow the typing and read each output
MAX_SECONDS = 60.0

# The schedule, in seconds: nothing here depends on how long a command really took.
TYPING_PER_CHARACTER = 0.05
BEFORE_TYPING = 0.4
BEFORE_OUTPUT = 0.4
PER_OUTPUT_LINE = 0.1
AFTER_STEP = 1.0
AFTER_ACT = 1.8
REFUSED_HOLD = 2.0  # the screen of a refused push is the one to read: it stays longer
AFTER_LAST_ACT = 2.5


@dataclass(frozen=True)
class Step:
    """One typed command. `run` is False for the one that needs the network and a release."""

    command: str
    run: bool = True
    refused: bool = False  # the step the story needs to end with a non-zero status


# The story, in order. Each act is one screen. The commit lines carry the opt-in on screen: the
# steps are separate `sh -c` processes, so an `export` would not reach the next one.
ACTS: tuple[tuple[Step, ...], ...] = (
    (
        Step(INSTALL, run=False),
        Step('prepush-ci init --non-interactive --check "sh check.sh"'),
    ),
    (
        Step("git add .claude .prepush-ci.toml"),
        Step(f'PREPUSH_CI=full git commit -m "{SETUP_COMMIT}"'),
        Step("git log -1 --format=%B"),
    ),
    (Step(f"git push origin {BRANCH}", refused=True),),
    (
        Step(
            'printf \'def greet(name):\\n    return "Hello, " + name + "!"\\n\' > app.py'
        ),
        Step(f'PREPUSH_CI=full git commit -am "{FIX_COMMIT}"'),
        Step(f"git push origin {BRANCH}"),
        Step("prepush-ci verify HEAD"),
    ),
)

APP = 'def greet(name):\n    return "Hello, " + name\n'


def check_script(delay: float) -> str:
    """The check of the scratch repository: it answers with one line on each outcome."""
    sleep = f"sleep {delay:g}\n" if delay > 0 else ""
    return (
        f"{sleep}"
        "if grep -q '+ \"!\"$' app.py; then\n"
        f'    echo "{SUCCESS_LINE}"\n'
        "else\n"
        f'    echo "{FAILURE_LINE}"\n'
        "    exit 1\n"
        "fi\n"
    )


class RecordingError(Exception):
    """The recording cannot be written: a step ended wrong, or its output holds a private path."""


@dataclass
class Recorded:
    step: Step
    output: list[str]
    exit_status: int | None  # None for the step that is not run


# --- Running the steps -------------------------------------------------------------------------


@dataclass
class Scratch:
    base: Path  # the scratch directory: the bare remote and the shim live in it
    repo: Path  # the repository the steps run in
    env: dict[str, str] = field(default_factory=dict)


# Git's per-repository variables: a hook that started this script would send every git of the
# story to its own repository.
_REPOSITORY_VARIABLES = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_COMMON_DIR",
    "GIT_PREFIX",
    "GIT_NAMESPACE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_QUARANTINE_PATH",
)


def step_environment(base: Path) -> dict[str, str]:
    """The environment of every step: the shim first on `PATH`, no inherited opt-in or opt-out,
    no git configuration of the maintainer."""
    kept = {
        name: value
        for name, value in os.environ.items()
        if name != "PREPUSH_CI"
        and not name.startswith("PRE_COMMIT_")
        and name not in _REPOSITORY_VARIABLES
    }
    identity = {"NAME": "Ada Lovelace", "EMAIL": "ada@example.com"}
    return {
        **kept,
        "PATH": os.pathsep.join([str(base / "bin"), kept.get("PATH", "")]),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "PYTHONIOENCODING": "utf-8",  # the output of a step is UTF-8 whatever the locale
        **{f"GIT_AUTHOR_{k}": v for k, v in identity.items()},
        **{f"GIT_COMMITTER_{k}": v for k, v in identity.items()},
    }


def write_shim(base: Path) -> None:
    """`prepush-ci` as the steps type it, started the way the tests start the CLI."""
    shim = base / "bin" / "prepush-ci"
    shim.parent.mkdir()
    shim.write_text(
        f'#!/bin/sh\nexec {shlex.quote(sys.executable)} -m prepush_ci "$@"\n',
        encoding="utf-8",
    )
    shim.chmod(0o755)


def git(repo: Path, env: dict[str, str], *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, env=env, check=True, capture_output=True)


def make_scratch(base: Path, check_delay: float) -> Scratch:
    """The scratch repository on `main` with one commit pushed to a bare remote, then on `BRANCH`.

    The check fails until `greet()` ends with `!`; the story fixes that.
    """
    write_shim(base)
    env = step_environment(base)
    remote = base / "remote.git"
    repo = base / "repo"
    git(base, env, "init", "-q", "--bare", "-b", "main", remote.name)
    git(base, env, "init", "-q", "-b", "main", repo.name)
    (repo / "app.py").write_text(APP, encoding="utf-8")
    (repo / "check.sh").write_text(check_script(check_delay), encoding="utf-8")
    git(repo, env, "add", "app.py", "check.sh")
    git(repo, env, "commit", "-q", "-m", "feat: greet by name")
    git(repo, env, "remote", "add", "origin", "../remote.git")
    git(repo, env, "push", "-q", "origin", "main")
    git(repo, env, "switch", "-q", "-c", BRANCH)
    return Scratch(base, repo, env)


def run_step(scratch: Scratch, step: Step) -> Recorded:
    """Run the step as a shell line; its output is what the terminal would show (both streams)."""
    if not step.run:
        return Recorded(step, [], None)
    done = subprocess.run(
        ["sh", "-c", step.command],
        cwd=scratch.repo,
        env=scratch.env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return Recorded(step, done.stdout.splitlines(), done.returncode)


# --- What the output may show ------------------------------------------------------------------


def as_output(path: str) -> str:
    """A path as the output of a step shows it: the steps print UTF-8, whatever the locale of this
    process decodes a path with."""
    return os.fsencode(path).decode("utf-8", "surrogateescape")


def private_paths() -> list[str]:
    """The paths that must not reach the asset: the home directory, the interpreter."""
    paths = {str(Path.home()), sys.executable, str(Path(sys.executable).resolve())}
    return sorted(as_output(path) for path in paths if path not in ("", "/", os.sep))


def without_scratch(line: str, scratch: Scratch) -> str:
    """The scratch repository is `.`; git prints the remote as `../remote.git` by itself."""
    for form in {str(scratch.repo), str(scratch.repo.resolve())}:
        line = line.replace(as_output(form), ".")
    return line


def shown_lines(step: Step, lines: list[str], scratch: Scratch) -> list[str]:
    """The lines of a step's output as the asset shows them.

    The scratch directory is replaced; a line that still holds the home directory or the
    interpreter's path fails the recording rather than being rewritten (a traceback must not
    reach a README); long output is cut to its first lines, never edited; a line wider than the
    screen fails the recording rather than being cut.
    """
    shown: list[str] = []
    for line in lines:
        replaced = without_scratch(line.rstrip(), scratch)
        for path in private_paths():
            if path in replaced:
                raise RecordingError(
                    f"step `{step.command}` printed a path of this machine: {path}"
                )
        shown.append(replaced)
    while shown and not shown[-1]:
        shown.pop()
    if len(shown) > MAX_OUTPUT_LINES:
        shown = [*shown[:MAX_OUTPUT_LINES], CUT]
    for line in shown:
        if len(line) > COLUMNS:
            raise RecordingError(
                f"step `{step.command}` printed a line of {len(line)} columns, "
                f"wider than the {COLUMNS} of the screen: {line}"
            )
    return shown


def check_status(recorded: Recorded) -> None:
    """The story needs 0 from every step that runs, except the refused push."""
    step, status = recorded.step, recorded.exit_status
    if status is None:
        return
    if step.refused and status == 0:
        raise RecordingError(
            f"step `{step.command}` exited 0, but the check must refuse it"
        )
    if not step.refused and status != 0:
        raise RecordingError(f"step `{step.command}` exited {status}, not 0")


def record(base: Path, check_delay: float = 0.0) -> list[list[Recorded]]:
    """Run the story in a scratch repository under `base`, one list of results per act."""
    for command in (s.command for act in ACTS for s in act):
        if len(PROMPT_TEXT) + len(command) > COLUMNS:
            raise RecordingError(f"`{command}` does not fit {COLUMNS} columns")
    scratch = make_scratch(base, check_delay)
    acts: list[list[Recorded]] = []
    for act in ACTS:
        results: list[Recorded] = []
        for step in act:
            recorded = run_step(scratch, step)
            check_status(recorded)
            recorded.output = shown_lines(step, recorded.output, scratch)
            results.append(recorded)
        acts.append(results)
    return acts


# --- The animation -----------------------------------------------------------------------------

CHARACTER_WIDTH = 8.4
ROW_HEIGHT = 20
PADDING = 24
TOP = 44  # room for the window bar
WIDTH = round(COLUMNS * CHARACTER_WIDTH + 2 * PADDING)
HEIGHT = TOP + ROWS * ROW_HEIGHT + PADDING // 2
PROMPT = "$"
PROMPT_TEXT = PROMPT + " "
PROMPT_WIDTH = len(PROMPT_TEXT)

BACKGROUND = "#0d1117"
FOREGROUND = "#e6edf3"
GREEN = "#3fb950"
RED = "#ff7b72"


@dataclass
class Timed:
    """A step with its place on the timeline, in seconds from the start of the cycle."""

    recorded: Recorded
    row: int
    start: float
    typed: float  # the end of the typing
    lines: list[float]  # the start of each output line
    end: float


def schedule(
    acts: list[list[Recorded]],
) -> tuple[list[list[Timed]], list[tuple[float, float]], float]:
    """The timeline: the steps of each act, the (start, end) of each act, the whole duration."""
    clock = hold = 0.0
    timed_acts: list[list[Timed]] = []
    spans: list[tuple[float, float]] = []
    for results in acts:
        act_start = clock
        timed: list[Timed] = []
        row = 0
        for recorded in results:
            start = clock + BEFORE_TYPING
            typed = start + len(recorded.step.command) * TYPING_PER_CHARACTER
            first = typed + BEFORE_OUTPUT
            lines = [first + n * PER_OUTPUT_LINE for n in range(len(recorded.output))]
            end = lines[-1] + PER_OUTPUT_LINE if lines else typed
            timed.append(Timed(recorded, row, start, typed, lines, end))
            row += 1 + len(recorded.output)
            clock = end + AFTER_STEP
        if row > ROWS:
            raise RecordingError(f"an act of {row} rows does not fit {ROWS} rows")
        hold = AFTER_ACT + (REFUSED_HOLD if any(r.exit_status for r in results) else 0)
        clock += hold - AFTER_STEP
        spans.append((act_start, clock))
        timed_acts.append(timed)
    duration = clock - hold + AFTER_LAST_ACT
    if duration > MAX_SECONDS:
        raise RecordingError(
            f"the animation would last {duration:.1f} seconds, over {MAX_SECONDS:g}"
        )
    if duration < MIN_SECONDS:
        raise RecordingError(
            f"the animation would last {duration:.1f} seconds, under {MIN_SECONDS:g}"
        )
    return timed_acts, spans, duration


def percent(seconds: float, duration: float) -> str:
    return f"{100 * seconds / duration:.4f}".rstrip("0").rstrip(".")


def visible_keyframes(
    name: str, start: float, end: float | None, duration: float
) -> str:
    """Hidden until `start`, then shown until `end` (the end of the cycle when None); `step-end`
    holds each value until the next frame."""
    frames = ["0%{opacity:0}", f"{percent(start, duration)}%{{opacity:1}}"]
    if end is not None:
        frames.append(f"{percent(end, duration)}%{{opacity:0}}")
    return f"@keyframes {name}{{{''.join(frames)}}}"


def typing_keyframes(name: str, timed: Timed, duration: float) -> str:
    """The cover that hides the command slides right one character at a time (`steps(n)`)."""
    chars = len(timed.recorded.step.command)
    distance = chars * CHARACTER_WIDTH
    return (
        f"@keyframes {name}{{"
        f"0%{{transform:translateX(0)}}"
        f"{percent(timed.start, duration)}%{{transform:translateX(0);"
        f"animation-timing-function:steps({chars},start)}}"
        f"{percent(timed.typed, duration)}%{{transform:translateX({distance:.1f}px)}}"
        f"100%{{transform:translateX({distance:.1f}px)}}}}"
    )


def line_class(recorded: Recorded, line: str) -> str:
    if recorded.exit_status not in (None, 0) and not line.startswith("To "):
        return "bad"
    if line.startswith(("ok:", "verified:")):
        return "good"
    return "plain"


def svg(acts: list[list[Recorded]]) -> str:
    """The animated SVG: every command typed one character at a time, its output after it."""
    timed_acts, spans, duration = schedule(acts)
    style: list[str] = [
        f".t{{font:14px ui-monospace,SFMono-Regular,Menlo,Consolas,'DejaVu Sans Mono',monospace;"
        f"fill:{FOREGROUND};white-space:pre}}",
        f".plain{{fill:{FOREGROUND}}}.good{{fill:{GREEN}}}.bad{{fill:{RED}}}.p{{fill:{GREEN}}}",
        f".c{{fill:{BACKGROUND}}}.k{{fill:{FOREGROUND}}}",
        f".a{{animation-duration:{duration:.2f}s;animation-iteration-count:infinite;"
        f"animation-timing-function:step-end}}",
    ]
    body: list[str] = []
    for number, (timed, (act_start, act_end)) in enumerate(
        zip(timed_acts, spans, strict=True)
    ):
        style.append(visible_keyframes(f"act{number}", act_start, act_end, duration))
        body.append(f'<g class="a" style="animation-name:act{number}">')
        for item in timed:
            body.append(step_markup(item, number, duration, style))
        body.append("</g>")
    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
            f'viewBox="0 0 {WIDTH} {HEIGHT}" role="img" data-duration="{duration:.2f}">',
            "<title>prepush-ci in a terminal</title>",
            "<desc>Setting up a repository with prepush-ci init, a push refused because the full "
            "check fails, and a push that goes through once it passes.</desc>",
            f"<style>{''.join(style)}</style>",
            f'<rect width="{WIDTH}" height="{HEIGHT}" rx="10" fill="{BACKGROUND}"/>',
            '<circle cx="24" cy="22" r="6" fill="#ff5f56"/><circle cx="44" cy="22" r="6" '
            'fill="#ffbd2e"/><circle cx="64" cy="22" r="6" fill="#27c93f"/>',
            *body,
            "</svg>",
        ]
    )


def step_markup(item: Timed, act: int, duration: float, style: list[str]) -> str:
    recorded = item.recorded
    step = recorded.step
    name = f"s{act}_{item.row}"
    chars = len(step.command)
    y = TOP + item.row * ROW_HEIGHT
    x_command = PADDING + PROMPT_WIDTH * CHARACTER_WIDTH
    attributes = [
        f"data-command={quoteattr(step.command)}",
        f'data-chars="{chars}"',
        f'data-run="{str(step.run).lower()}"',
        *(
            []
            if recorded.exit_status is None
            else [f'data-exit="{recorded.exit_status}"']
        ),
        f'data-start="{item.start:.2f}"',
        f'data-typed="{item.typed:.2f}"',
        f'data-end="{item.end:.2f}"',
    ]
    style.append(visible_keyframes(f"{name}p", item.start, None, duration))
    style.append(typing_keyframes(f"{name}t", item, duration))
    parts = [
        f'<g class="step" id="{name}" {" ".join(attributes)}>',
        f'<text class="t p a" style="animation-name:{name}p" x="{PADDING}" y="{y}">{PROMPT}</text>',
        f'<text class="t plain" x="{x_command:.1f}" y="{y}" textLength="{chars * CHARACTER_WIDTH:.1f}" '
        f'xml:space="preserve">{escape(step.command)}</text>',
        f'<rect class="c a" style="animation-name:{name}t" x="{x_command:.1f}" y="{y - 14}" '
        f'width="{chars * CHARACTER_WIDTH:.1f}" height="{ROW_HEIGHT}"/>',
    ]
    for number, (line, start) in enumerate(
        zip(recorded.output, item.lines, strict=True)
    ):
        line_name = f"{name}o{number}"
        style.append(visible_keyframes(line_name, start, None, duration))
        row_y = y + (number + 1) * ROW_HEIGHT
        parts.append(
            f'<text class="t {line_class(recorded, line)} line a" style="animation-name:{line_name}" '
            f'data-start="{start:.2f}" x="{PADDING}" y="{row_y}" '
            f'textLength="{len(line) * CHARACTER_WIDTH:.1f}" xml:space="preserve">'
            f"{escape(line) if line else ' '}</text>"
        )
    parts.append("</g>")
    return "\n".join(parts)


# --- Checking an asset -------------------------------------------------------------------------


def timeline_problems(asset: str) -> list[str]:
    """What is wrong with the timeline of an asset, measured from its own attributes."""
    root = ElementTree.fromstring(asset)
    declared = float(root.get("data-duration", "nan"))
    problems: list[str] = []
    if declared < MIN_SECONDS:
        problems.append(f"the duration {declared:g} is below {MIN_SECONDS:g} seconds")
    elif not declared <= MAX_SECONDS:
        problems.append(f"the duration {declared:g} is above {MAX_SECONDS:g} seconds")
    animated = {
        float(found) for found in re.findall(r"animation-duration:\s*([\d.]+)s", asset)
    }
    if animated != {declared}:
        problems.append(
            f"data-duration {declared:g} differs from the animation duration "
            f"{', '.join(f'{value:g}' for value in sorted(animated))}"
        )
    for step in root.iter("{http://www.w3.org/2000/svg}g"):
        if (
            step.get("class") == "step"
            and float(step.get("data-end", "nan")) > declared
        ):
            problems.append(
                f"step `{step.get('data-command')}` ends at {step.get('data-end')}, "
                f"after the duration {declared:g}"
            )
    return problems


# --- The command line --------------------------------------------------------------------------


def parser() -> argparse.ArgumentParser:
    arguments = argparse.ArgumentParser(
        prog="record_demo.py",
        description="Record the terminal demo of the README from the real prepush-ci.",
        epilog=f"Regenerate the asset with: {COMMAND}",
    )
    arguments.add_argument(
        "--output",
        type=Path,
        default=ASSET,
        help=f"where to write the SVG (default: {ASSET.relative_to(ROOT).as_posix()})",
    )
    arguments.add_argument(
        "--check-delay",
        type=float,
        default=0.0,
        metavar="SECONDS",
        help="make the check of the scratch repository sleep first (the animation does not change)",
    )
    return arguments


def main(argv: list[str] | None = None) -> int:
    options = parser().parse_args(argv)
    # The scratch directory is resolved first: git prints the resolved path (macOS puts the
    # temporary directory behind a symlink), and a path that is replaced must match it.
    with tempfile.TemporaryDirectory(prefix="prepush-ci-demo-") as directory:
        try:
            asset = svg(record(Path(directory).resolve(), options.check_delay))
        except RecordingError as error:
            print(f"record_demo.py: {error}", file=sys.stderr)
            return 1
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(asset + "\n", encoding="utf-8")
    print(f"wrote {options.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
