"""The facts a pass records: what the check wrote, against real repositories.

The config is an ignored file and so are the result directories, so a spec can change them without
dirtying the worktree, as a real project ignores its build output.
"""

import json
import os
import stat
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from prepush_ci import pass_cache, result_files
from prepush_ci.core.run_cache import Key, fingerprint, result_ref
from prepush_ci.git import GitError
from prepush_ci.repo_config import load_repository_config

Git = Callable[..., "subprocess.CompletedProcess[str]"]

TRAILER = "\n\nPrepush-CI: full"
POSIX_ONLY = pytest.mark.skipif(
    sys.platform == "win32",
    reason="needs symbolic links, permissions or a file system that tells cases apart",
)
WINDOWS_ONLY = pytest.mark.skipif(sys.platform != "win32", reason="needs a junction")
IGNORED = [
    "/.prepush-ci.toml",
    "out",
    "build",
    "vendor",
    "/cov.json",
]
# On Windows git ignores case and a trailing dot, so these would hide docs/cov.json itself.
if sys.platform != "win32":
    IGNORED += ["Docs", "docs/cov.json."]
EMIT = """\
import json, pathlib, sys, time

plan = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
time.sleep(plan.get("sleep", 0))
print(plan.get("print", ""))
files = {name: text.encode("utf-8") for name, text in plan.get("files", {}).items()}
files.update({name: bytes.fromhex(text) for name, text in plan.get("bytes", {}).items()})
for name, data in files.items():
    path = pathlib.Path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
for name in plan.get("dirs", []):
    pathlib.Path(name).mkdir(parents=True, exist_ok=True)
sys.exit(plan.get("exit", 0))
"""


def junit(*cases: tuple[str | None, str]) -> str:
    """A JUnit file with a case for each (file, outcome); the outcome is a tag or empty."""
    body = ""
    for file, outcome in cases:
        where = "" if file is None else f' file="{file}"'
        inner = f"<{outcome}/>" if outcome else ""
        body += f'<testcase classname="c" name="n"{where}>{inner}</testcase>'
    return f"<testsuites><testsuite>{body}</testsuite></testsuites>"


def coverage(shown: str) -> str:
    return json.dumps({"totals": {"percent_covered_display": shown}})


class Project:
    """A repository whose check is a script that writes the files a plan names."""

    def __init__(self, repo: Path, scratch: Path, git: Git) -> None:
        self.repo, self.scratch, self.git = repo, scratch, git
        (scratch / "emit.py").write_text(EMIT)
        (repo / ".git" / "info" / "exclude").write_text("\n".join(IGNORED) + "\n")

    def configure(self, results: str = "", *extra: str, **plan: Any) -> None:
        (self.scratch / "plan.json").write_text(json.dumps(plan))
        python = Path(sys.executable).as_posix()
        emit = (self.scratch / "emit.py").as_posix()
        plan_file = (self.scratch / "plan.json").as_posix()
        lines = [
            f'check = \'"{python}" "{emit}" "{plan_file}"\'',
            "require_up_to_date = false",
            *extra,
        ]
        if results:
            lines.append(f"results = {results}")
        (self.repo / ".prepush-ci.toml").write_text("\n".join(lines) + "\n")

    def commit(
        self, message: str = "init", files: dict[str, str] | None = None
    ) -> None:
        for name, text in (files or {}).items():
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, newline="\n")
            self.git(self.repo, "add", name)
        self.git(self.repo, "commit", "--allow-empty", "-q", "-m", message)

    def run(self) -> "subprocess.CompletedProcess[str]":
        env = {k: v for k, v in os.environ.items() if k != "PREPUSH_CI"}
        return subprocess.run(
            [sys.executable, "-m", "prepush_ci", "run"],
            cwd=self.repo,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )

    def hook_up(self, tmp_path: Path) -> None:
        """The pre-push hook, a bare `origin`, and `main` as the branch."""
        self.git(tmp_path, "init", "-q", "--bare", str(tmp_path / "remote.git"))
        self.git(self.repo, "symbolic-ref", "HEAD", "refs/heads/main")
        hook = self.repo / ".git" / "hooks" / "pre-push"
        python = Path(sys.executable).as_posix()
        hook.write_text(
            f'#!/bin/sh\nexec "{python}" -m prepush_ci hook pre-push "$@"\n'
        )
        hook.chmod(hook.stat().st_mode | stat.S_IXUSR)
        self.git(self.repo, "remote", "add", "origin", str(tmp_path / "remote.git"))

    def push(self, refspec: str = "main") -> "subprocess.CompletedProcess[str]":
        return self.git(self.repo, "push", "origin", refspec, check=False)

    def refs(self) -> list[str]:
        return self.git(
            self.repo, "for-each-ref", "--format=%(refname)", "refs/prepush-ci/results"
        ).stdout.split()

    def message(self) -> str:
        assert len(self.refs()) == 1, self.refs()
        return self.git(self.repo, "log", "-1", "--format=%B", self.refs()[0]).stdout

    def facts(self) -> dict[str, Any] | None:
        """The facts of the only result ref, or None when it holds none."""
        paragraphs = self.message().strip().split("\n\n")
        if len(paragraphs) < 3:
            return None
        assert paragraphs[2].startswith("facts ")
        facts: dict[str, Any] = json.loads(paragraphs[2].removeprefix("facts "))
        return facts


@pytest.fixture
def project(repo: Path, tmp_path: Path, git: Git) -> Project:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    return Project(repo, scratch, git)


def lines_for(result: "subprocess.CompletedProcess[str]", key: str) -> list[str]:
    return [line for line in result.stderr.splitlines() if f"`{key}`" in line]


# --- What a pass records ----------------------------------------------------------------------


def test_run_records_a_duration_of_two_seconds_or_more_for_a_check_that_takes_that_long(
    project: Project,
) -> None:
    project.configure(sleep=2)
    project.commit()

    result = project.run()

    assert result.returncode == 0, result.stderr
    facts = project.facts()
    assert facts is not None
    assert facts["seconds"] >= 2


def test_run_records_a_duration_even_when_no_results_are_named(
    project: Project,
) -> None:
    project.configure()
    project.commit()

    project.run()

    facts = project.facts()
    assert facts is not None
    assert set(facts) == {"v", "seconds"}


def test_the_message_of_a_pass_names_the_commit_in_its_second_paragraph_and_holds_the_facts_in_its_third(
    project: Project,
) -> None:
    project.configure()
    project.commit()
    sha = project.git(project.repo, "rev-parse", "HEAD").stdout.strip()

    project.run()

    subject, commit, facts = project.message().strip().split("\n\n")
    assert subject == "prepush-ci: the check passed"
    assert commit == f"commit {sha}"
    assert facts.startswith("facts {")


def test_the_pre_push_hook_records_a_duration_as_well(
    project: Project, tmp_path: Path
) -> None:
    project.configure()
    project.hook_up(tmp_path)
    project.commit("work" + TRAILER)

    pushed = project.push()

    assert pushed.returncode == 0, pushed.stderr
    facts = project.facts()
    assert facts is not None
    assert facts["seconds"] >= 0


def forge(project: Project, last_paragraph: str | None) -> None:
    """A result ref for the tree of `HEAD` made as an older version made it, or with a third
    paragraph that is not valid facts."""
    config = load_repository_config(project.repo)
    head = pass_cache.current_head(project.repo)
    key = Key(head.tree, fingerprint(config, ""))
    message = ["-m", "prepush-ci: the check passed", "-m", f"commit {head.sha}"]
    if last_paragraph is not None:
        message += ["-m", last_paragraph]
    made = project.git(project.repo, "commit-tree", head.tree, *message).stdout.strip()
    project.git(project.repo, "update-ref", result_ref(key), made)


@pytest.mark.parametrize("last_paragraph", [None, "facts not json"])
def test_a_pass_without_readable_facts_is_still_a_pass_that_skips_the_check(
    project: Project, tmp_path: Path, last_paragraph: str | None
) -> None:
    project.configure()
    project.hook_up(tmp_path)
    project.commit("work" + TRAILER)
    forge(project, last_paragraph)

    pushed = project.push()

    assert pushed.returncode == 0, pushed.stderr
    assert "passed earlier" in pushed.stderr


# --- What the files say ------------------------------------------------------------------------


def test_the_tests_a_junit_file_holds_are_counted_in_total_and_per_test_file(
    project: Project,
) -> None:
    project.commit(files={"tests/a_spec.py": "x"})
    project.configure(
        '{ junit = ["out/a.xml"] }',
        files={
            "out/a.xml": junit(
                *[("tests/a_spec.py", "")] * 3, ("tests/a_spec.py", "skipped")
            )
        },
    )

    result = project.run()

    assert result.returncode == 0, result.stderr
    facts = project.facts()
    assert facts is not None
    assert facts["tests"] == [3, 0, 1]
    assert facts["files"] == [["tests/a_spec.py", 3, 0, 1]]


def test_the_cases_of_several_junit_files_are_added(project: Project) -> None:
    project.commit()
    project.configure(
        '{ junit = ["out/a.xml", "out/b.xml"] }',
        files={
            "out/a.xml": junit((None, ""), (None, "")),
            "out/b.xml": junit((None, ""), (None, ""), (None, "")),
        },
    )

    project.run()

    facts = project.facts()
    assert facts is not None
    assert facts["tests"] == [5, 0, 0]


def test_a_coverage_file_and_clean_ruff_and_mypy_files_give_a_coverage_and_no_errors(
    project: Project,
) -> None:
    project.commit()
    project.configure(
        '{ coverage = "out/cov.json", ruff = "out/ruff.json", mypy = "out/mypy.txt" }',
        files={
            "out/cov.json": coverage("94.5"),
            "out/ruff.json": "[]",
            "out/mypy.txt": "Success: no issues found in 12 source files\n",
        },
    )

    project.run()

    facts = project.facts()
    assert facts is not None
    assert (facts["coverage"], facts["ruff"], facts["mypy"]) == ("94.5", 0, 0)


def test_the_errors_of_ruff_and_mypy_are_counted(project: Project) -> None:
    project.commit()
    project.configure(
        '{ ruff = "out/ruff.json", mypy = "out/mypy.txt" }',
        files={
            "out/ruff.json": json.dumps([{"code": "E1"}, {"code": "E2"}]),
            "out/mypy.txt": "a.py:1: error: x\nFound 3 errors in 1 file\n",
        },
    )

    result = project.run()

    assert result.returncode == 0, result.stderr
    facts = project.facts()
    assert facts is not None
    assert (facts["ruff"], facts["mypy"]) == (2, 3)
    assert result.stderr == ""


def test_without_results_the_facts_hold_the_duration_and_nothing_else(
    project: Project,
) -> None:
    project.commit()
    project.configure(files={"out/a.xml": junit((None, ""))})

    project.run()

    facts = project.facts()
    assert facts is not None
    assert set(facts) == {"v", "seconds"}


# --- The files of this run only ----------------------------------------------------------------


def test_a_stale_file_is_not_read_as_a_fact_of_this_run(project: Project) -> None:
    project.commit()
    project.configure('{ junit = ["out/a.xml"] }')
    stale = project.repo / "out" / "a.xml"
    stale.parent.mkdir()
    stale.write_text(junit(*[(None, "failure")] * 4))

    result = project.run()

    assert result.returncode == 0, result.stderr
    assert not stale.exists()
    facts = project.facts()
    assert facts is not None
    assert "tests" not in facts
    assert len(lines_for(result, "results.junit")) == 1


def test_the_file_the_check_writes_is_the_one_that_is_read(project: Project) -> None:
    project.commit()
    project.configure(
        '{ junit = ["out/a.xml"] }', files={"out/a.xml": junit(*[(None, "")] * 3)}
    )
    stale = project.repo / "out" / "a.xml"
    stale.parent.mkdir()
    stale.write_text(junit(*[(None, "failure")] * 4))

    project.run()

    facts = project.facts()
    assert facts is not None
    assert facts["tests"] == [3, 0, 0]


def test_a_skipped_check_deletes_nothing(project: Project, tmp_path: Path) -> None:
    project.configure('{ junit = ["out/a.xml"] }')
    project.hook_up(tmp_path)
    project.commit("work" + TRAILER)
    assert project.push().returncode == 0
    kept = project.repo / "out" / "a.xml"
    kept.parent.mkdir()
    kept.write_text("kept")

    pushed = project.push("main:other")

    assert pushed.returncode == 0, pushed.stderr
    assert "passed earlier" in pushed.stderr
    assert kept.read_text() == "kept"


def test_without_the_cache_nothing_is_deleted(project: Project) -> None:
    project.commit()
    project.configure('{ junit = ["out/a.xml"] }', "cache = false")
    kept = project.repo / "out" / "a.xml"
    kept.parent.mkdir()
    kept.write_text("kept")

    result = project.run()

    assert result.returncode == 0, result.stderr
    assert kept.read_text() == "kept"
    assert project.refs() == []


def test_a_failing_check_records_no_result_and_reads_nothing(project: Project) -> None:
    project.commit()
    project.configure('{ junit = ["out/a.xml"] }', exit=1)
    stale = project.repo / "out" / "a.xml"
    stale.parent.mkdir()
    stale.write_text("stale")

    result = project.run()

    assert result.returncode == 1
    assert project.refs() == []
    assert lines_for(result, "results.junit") == []


# --- A path that is not safe to delete ---------------------------------------------------------


def left_alone(
    project: Project, key: str, why: str
) -> "subprocess.CompletedProcess[str]":
    """Run, and check what every left-alone path shares: success, one line naming the key and
    saying why, and the pass recorded without the fact the file would have given."""
    result = project.run()

    assert result.returncode == 0, result.stderr
    named = lines_for(result, key)
    assert len(named) == 1, result.stderr
    assert why in named[0]
    facts = project.facts()
    assert facts is not None
    assert not {"tests", "coverage"} & facts.keys()
    return result


def test_a_tracked_file_is_left_alone(project: Project) -> None:
    project.commit(files={"docs/cov.json": "tracked"})
    project.configure('{ coverage = "docs/cov.json" }')

    left_alone(project, "results.coverage", "tracked")

    assert (project.repo / "docs" / "cov.json").read_text() == "tracked"


def test_a_file_that_is_only_staged_is_left_alone(
    project: Project, capsys: pytest.CaptureFixture[str]
) -> None:
    # `run` refuses a worktree with a staged file, so the step that deletes is started directly
    project.commit()
    project.configure('{ junit = ["out/a.xml"] }')
    staged = project.repo / "out" / "a.xml"
    staged.parent.mkdir()
    staged.write_text("staged")
    project.git(project.repo, "add", "-f", "out/a.xml")

    result_files.clear(load_repository_config(project.repo), project.repo)

    assert staged.read_text() == "staged"
    lines = [
        line for line in capsys.readouterr().err.splitlines() if "results.junit" in line
    ]
    assert len(lines) == 1
    assert "tracked" in lines[0]


def test_a_directory_is_left_alone(project: Project) -> None:
    project.commit()
    project.configure('{ coverage = "out" }')
    inside = project.repo / "out" / "keep.txt"
    inside.parent.mkdir()
    inside.write_text("keep")

    left_alone(project, "results.coverage", "directory")

    assert inside.read_text() == "keep"


@POSIX_ONLY
def test_a_symbolic_link_on_the_way_is_left_alone(
    project: Project, tmp_path: Path
) -> None:
    project.commit()
    project.configure('{ junit = ["out/a.xml"] }')
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "a.xml").write_text("outside")
    (project.repo / "out").symlink_to(outside, target_is_directory=True)

    left_alone(project, "results.junit", "a link is on the way")

    assert (outside / "a.xml").read_text() == "outside"


@WINDOWS_ONLY
def test_a_junction_on_the_way_is_left_alone(project: Project, tmp_path: Path) -> None:
    project.commit()
    project.configure('{ junit = ["out/a.xml"] }')
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "a.xml").write_text("outside")
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(project.repo / "out"), str(outside)],
        check=True,
        capture_output=True,
    )

    left_alone(project, "results.junit", "a link is on the way")

    assert (outside / "a.xml").read_text() == "outside"


@POSIX_ONLY
def test_a_symbolic_link_as_the_file_is_left_alone(
    project: Project, tmp_path: Path
) -> None:
    project.commit()
    project.configure('{ coverage = "cov.json" }')
    target = tmp_path / "target.json"
    target.write_text(coverage("50"))
    (project.repo / "cov.json").symlink_to(target)

    left_alone(project, "results.coverage", "it is a link")

    assert (project.repo / "cov.json").is_symlink()
    assert target.read_text() == coverage("50")


def test_a_file_of_a_submodule_is_left_alone(project: Project, tmp_path: Path) -> None:
    source = tmp_path / "sub-source"
    source.mkdir()
    project.git(source, "init", "-q")
    project.git(source, "config", "user.name", "Test")
    project.git(source, "config", "user.email", "test@example.com")
    (source / "README.md").write_text("sub")
    project.git(source, "add", "README.md")
    project.git(source, "commit", "-q", "-m", "sub")
    project.git(
        project.repo,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        "-q",
        str(source),
        "sub",
    )
    project.commit("add the submodule")
    project.configure('{ coverage = "sub/README.md" }')

    left_alone(project, "results.coverage", "another repository")

    assert (project.repo / "sub" / "README.md").read_text() == "sub"


def test_a_file_of_a_nested_repository_is_left_alone(project: Project) -> None:
    project.commit()
    nested = project.repo / "vendor" / "lib"
    nested.mkdir(parents=True)
    project.git(nested, "init", "-q")
    (nested / "a.xml").write_text("nested")
    project.configure('{ junit = ["vendor/lib/a.xml"] }')

    left_alone(project, "results.junit", "another repository")

    assert (nested / "a.xml").read_text() == "nested"


@POSIX_ONLY
def test_a_tracked_file_under_another_case_is_left_alone(project: Project) -> None:
    project.commit(files={"docs/cov.json": "tracked"})
    project.configure('{ coverage = "Docs/Cov.json" }')
    other = project.repo / "Docs" / "Cov.json"
    other.parent.mkdir()
    other.write_text("other case")

    left_alone(project, "results.coverage", "tracked")

    assert other.read_text() == "other case"


@POSIX_ONLY
def test_a_tracked_file_under_a_trailing_dot_is_left_alone(project: Project) -> None:
    project.commit(files={"docs/cov.json": "tracked"})
    project.configure('{ coverage = "docs/cov.json." }')
    dotted = project.repo / "docs" / "cov.json."
    dotted.write_text("dotted")

    left_alone(project, "results.coverage", "tracked")

    assert dotted.read_text() == "dotted"


@POSIX_ONLY
def test_a_deletion_that_fails_costs_one_line_and_the_pass_is_recorded(
    project: Project,
) -> None:
    project.commit()
    project.configure('{ junit = ["out/a.xml"] }')
    stale = project.repo / "out" / "a.xml"
    stale.parent.mkdir()
    stale.write_text("stale")
    stale.parent.chmod(0o555)
    try:
        result = project.run()
    finally:
        stale.parent.chmod(0o755)

    assert result.returncode == 0, result.stderr
    named = lines_for(result, "results.junit")
    assert len(named) == 1
    assert "deletion failed" in named[0]
    facts = project.facts()
    assert facts is not None
    assert "seconds" in facts
    assert "tests" not in facts


@POSIX_ONLY
def test_a_file_that_is_not_a_regular_file_is_left_alone(project: Project) -> None:
    project.commit()
    project.configure('{ junit = ["out/a.xml"] }')
    fifo = project.repo / "out" / "a.xml"
    fifo.parent.mkdir()
    os.mkfifo(fifo)

    left_alone(project, "results.junit", "not a regular file")

    assert stat.S_ISFIFO(fifo.stat().st_mode)


def test_nothing_is_deleted_when_git_cannot_say_what_it_tracks(
    project: Project,
) -> None:
    project.commit()
    project.configure('{ junit = ["out/a.xml"] }')
    kept = project.repo / "out" / "a.xml"
    kept.parent.mkdir()
    kept.write_text("kept")
    (project.repo / ".git" / "index").write_bytes(b"not an index")

    with pytest.raises(GitError):
        result_files.clear(load_repository_config(project.repo), project.repo)

    assert kept.read_text() == "kept"


def test_a_file_that_head_lists_but_the_index_no_longer_does_is_left_alone(
    project: Project, capsys: pytest.CaptureFixture[str]
) -> None:
    project.commit(files={"docs/cov.json": "tracked"})
    project.configure('{ coverage = "docs/cov.json" }')
    project.git(project.repo, "rm", "-q", "--cached", "docs/cov.json")

    result_files.clear(load_repository_config(project.repo), project.repo)

    assert (project.repo / "docs" / "cov.json").read_text() == "tracked"
    assert "tracked" in capsys.readouterr().err


def test_the_line_for_a_path_left_alone_holds_no_content(project: Project) -> None:
    project.commit()
    project.configure('{ coverage = "out" }')
    secret = project.repo / "out" / "secret.txt"
    secret.parent.mkdir()
    secret.write_text("TOKEN=abc123")

    result = project.run()

    assert len(lines_for(result, "results.coverage")) == 1
    assert "abc123" not in result.stderr


# --- A fact that cannot be read ----------------------------------------------------------------


def test_a_file_the_check_did_not_write_costs_one_line_and_the_pass_is_recorded(
    project: Project,
) -> None:
    project.commit()
    project.configure('{ junit = ["out/a.xml"] }')

    result = project.run()

    assert result.returncode == 0, result.stderr
    (line,) = lines_for(result, "results.junit")
    assert "did not write" in line
    facts = project.facts()
    assert facts is not None
    assert "seconds" in facts


def test_a_file_of_the_wrong_format_costs_one_line_without_its_text(
    project: Project,
) -> None:
    project.commit()
    project.configure(
        '{ coverage = "out/cov.json" }', files={"out/cov.json": "TOKEN=abc123"}
    )

    result = project.run()

    assert result.returncode == 0, result.stderr
    assert len(lines_for(result, "results.coverage")) == 1
    assert "abc123" not in result.stderr
    facts = project.facts()
    assert facts is not None
    assert "coverage" not in facts


def test_a_file_that_is_not_utf8_gives_no_fact(project: Project) -> None:
    project.commit()
    project.configure(
        '{ mypy = "out/mypy.txt" }', bytes={"out/mypy.txt": b"Found 1 error \xff".hex()}
    )

    result = project.run()

    assert result.returncode == 0, result.stderr
    (line,) = lines_for(result, "results.mypy")
    assert "UTF-8" in line


def test_a_result_path_the_check_made_a_directory_gives_no_fact_and_one_line(
    project: Project,
) -> None:
    project.commit()
    project.configure('{ coverage = "out/cov.json" }', dirs=["out/cov.json"])

    result = project.run()

    assert result.returncode == 0, result.stderr
    assert len(lines_for(result, "results.coverage")) == 1
    facts = project.facts()
    assert facts is not None
    assert "coverage" not in facts


def test_a_failing_case_in_a_passing_check_is_recorded_as_it_is(
    project: Project,
) -> None:
    project.commit()
    project.configure(
        '{ junit = ["out/a.xml"] }', files={"out/a.xml": junit((None, "failure"))}
    )

    result = project.run()

    assert result.returncode == 0, result.stderr
    facts = project.facts()
    assert facts is not None
    assert facts["tests"] == [0, 1, 0]


# --- Test-file names are paths of the tree -----------------------------------------------------


def test_a_file_name_that_is_not_in_the_tree_is_counted_under_other_and_not_kept(
    project: Project,
) -> None:
    project.commit()
    project.configure(
        '{ junit = ["out/a.xml"] }',
        files={
            "out/a.xml": junit(
                ("/home/someone/secret.py", ""), ("tests/secret_spec.py", "")
            )
        },
    )

    project.run()

    facts = project.facts()
    assert facts is not None
    assert facts["other"] == [2, 0, 0]
    assert "files" not in facts
    assert "secret" not in project.message()


def test_junit_cases_without_a_file_are_counted_under_other(project: Project) -> None:
    project.commit()
    project.configure(
        '{ junit = ["out/a.xml"] }', files={"out/a.xml": junit((None, ""), (None, ""))}
    )

    project.run()

    facts = project.facts()
    assert facts is not None
    assert facts["tests"] == [2, 0, 0]
    assert facts["other"] == [2, 0, 0]


def test_the_cases_of_sixty_files_are_listed_for_fifty_and_the_rest_are_under_other(
    project: Project,
) -> None:
    names = [f"tests/f{index:02d}_spec.py" for index in range(60)]
    project.commit(files=dict.fromkeys(names, "x"))
    project.configure(
        '{ junit = ["out/a.xml"] }',
        files={"out/a.xml": junit(*[(name, "") for name in names])},
    )

    project.run()

    facts = project.facts()
    assert facts is not None
    assert len(facts["files"]) == 50
    assert facts["other"] == [10, 0, 0]
    assert facts["tests"] == [60, 0, 0]


# --- Only numbers are kept ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "shown",
    [
        "see https://example.com",
        "nan",
        "inf",
        "1e3",
        "-5",
        "101",
        "9 4",
        ".",
        ".5",
        "100.",
        "١٠٠",
        "٩٤.٥",
    ],
)
def test_a_coverage_that_is_not_a_number_gives_no_fact_and_one_line(
    project: Project, shown: str
) -> None:
    project.commit()
    project.configure(
        '{ coverage = "out/cov.json" }', files={"out/cov.json": coverage(shown)}
    )

    result = project.run()

    assert result.returncode == 0, result.stderr
    assert len(lines_for(result, "results.coverage")) == 1
    facts = project.facts()
    assert facts is not None
    assert "coverage" not in facts


def test_a_coverage_file_with_a_byte_order_mark_is_read(project: Project) -> None:
    project.commit()
    content = ("\ufeff" + coverage("93.5")).encode("utf-8")
    project.configure(
        '{ coverage = "out/cov.json" }', bytes={"out/cov.json": content.hex()}
    )

    project.run()

    facts = project.facts()
    assert facts is not None
    assert facts["coverage"] == "93.5"


def test_a_whole_number_of_coverage_stays_whole(project: Project) -> None:
    project.commit()
    project.configure(
        '{ coverage = "out/cov.json" }', files={"out/cov.json": coverage("100")}
    )

    project.run()

    facts = project.facts()
    assert facts is not None
    assert facts["coverage"] == "100"


def test_nothing_the_check_printed_is_kept(project: Project) -> None:
    project.commit()
    project.configure(**{"print": "TOKEN=abc123"})

    result = project.run()

    assert (
        "abc123" in result.stdout
    )  # the check's own output reaches the user, untouched
    assert "abc123" not in project.message()


def test_an_empty_results_table_names_nothing_and_leaves_the_duration_alone(
    project: Project,
) -> None:
    project.commit()
    project.configure("{}")

    result = project.run()

    assert result.returncode == 0, result.stderr
    facts = project.facts()
    assert facts is not None
    assert set(facts) == {"v", "seconds"}


# --- The file is judged, not the way the path is written ---------------------------------------

TRACKED_SPELLINGS = [
    "docs//cov.json",
    "docs/./cov.json",
    "./docs/cov.json",
    "docs/cov.json/",
    "docs/.//./cov.json",
]
UNTRACKED_SPELLINGS = [
    "out//cov.json",
    "out/./cov.json",
    "./out/cov.json",
    "out/cov.json/",
    "out/.//./cov.json",
]


@pytest.mark.parametrize("spelling", TRACKED_SPELLINGS)
def test_a_tracked_file_is_left_alone_however_its_path_is_written(
    project: Project, spelling: str
) -> None:
    project.commit(files={"docs/cov.json": "tracked"})
    project.configure(f'{{ coverage = "{spelling}" }}')

    left_alone(project, "results.coverage", "tracked")

    assert (project.repo / "docs" / "cov.json").read_text() == "tracked"
    assert project.git(project.repo, "status", "--porcelain").stdout == ""


@pytest.mark.parametrize("spelling", UNTRACKED_SPELLINGS)
def test_a_stale_file_is_deleted_however_its_path_is_written(
    project: Project, spelling: str
) -> None:
    project.commit()
    project.configure(f'{{ coverage = "{spelling}" }}')
    stale = project.repo / "out" / "cov.json"
    stale.parent.mkdir()
    stale.write_text(coverage("10"))

    result = project.run()

    assert result.returncode == 0, result.stderr
    assert not stale.exists()
    named = lines_for(result, "results.coverage")
    assert len(named) == 1
    assert "did not write" in named[0]


@pytest.mark.parametrize("spelling", UNTRACKED_SPELLINGS)
def test_the_file_the_check_writes_is_read_however_its_path_is_written(
    project: Project, spelling: str
) -> None:
    project.commit()
    project.configure(
        f'{{ coverage = "{spelling}" }}', files={"out/cov.json": coverage("91")}
    )

    stale = project.repo / "out" / "cov.json"
    stale.parent.mkdir()
    stale.write_text(coverage("10"))

    result = project.run()

    assert result.returncode == 0, result.stderr
    assert lines_for(result, "results.coverage") == []
    facts = project.facts()
    assert facts is not None
    assert facts["coverage"] == "91"
