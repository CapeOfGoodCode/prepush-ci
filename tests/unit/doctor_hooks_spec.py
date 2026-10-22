from dataclasses import replace

from prepush_ci.core import doctor_hooks
from prepush_ci.core.doctor import Check
from prepush_ci.core.doctor_hooks import (
    Binary,
    ManagerFacts,
    NativeFacts,
    Script,
    native_check,
    none_check,
    refusal_check,
)
from prepush_ci.core.hook_managers import pre_commit_block

DIRECTORY = "/repo/.git/prepush-ci/hooks"
GOOD_SCRIPT = Script(exists=True, executable=True, content="#!/bin/sh\n")


def native(**changes: object) -> NativeFacts:
    facts = NativeFacts(
        configured=DIRECTORY,
        ours=True,
        directory=DIRECTORY,
        scripts={"commit-msg": GOOD_SCRIPT, "pre-push": GOOD_SCRIPT},
        interpreter="/venv/bin/python",
        interpreter_exists=True,
    )
    return replace(facts, **changes)  # type: ignore[arg-type]


def test_native_hooks_with_everything_in_place_pass() -> None:
    assert native_check("pre-push", native()).status == "ok"


def test_no_hooks_wanted_passes_and_says_so() -> None:
    check = none_check("pre-push")

    assert check.status == "ok"
    assert "no local hooks wanted" in check.text


def test_a_refusal_fails_with_its_message_and_asks_for_the_option() -> None:
    check = refusal_check("pre-push", "several hook managers found (a, b)")

    assert check.status == "fail"
    assert "several hook managers" in check.text
    assert check.fix is not None and "--hooks" in check.fix


def test_an_unset_hooks_path_fails_and_names_it() -> None:
    check = native_check("pre-push", native(configured=None, ours=False))

    assert check.status == "fail"
    assert "core.hooksPath is not set" in check.text
    assert check.fix is not None and "prepush-ci install" in check.fix


def test_another_hooks_path_fails_and_names_it() -> None:
    check = native_check("pre-push", native(configured=".githooks", ours=False))

    assert check.status == "fail"
    assert ".githooks" in check.text


def test_a_missing_script_fails() -> None:
    scripts = {"commit-msg": GOOD_SCRIPT, "pre-push": Script(exists=False)}

    assert native_check("pre-push", native(scripts=scripts)).status == "fail"
    assert native_check("commit-msg", native(scripts=scripts)).status == "ok"


def test_a_script_that_is_not_executable_fails_and_says_so() -> None:
    scripts = {"commit-msg": Script(exists=True), "pre-push": GOOD_SCRIPT}

    check = native_check("commit-msg", native(scripts=scripts))

    assert check.status == "fail"
    assert "not executable" in check.text


def test_a_missing_python_file_fails() -> None:
    check = native_check("pre-push", native(interpreter=None))

    assert check.status == "fail"
    assert "python" in check.text


def test_an_interpreter_that_is_gone_fails_and_names_it() -> None:
    check = native_check("pre-push", native(interpreter_exists=False))

    assert check.status == "fail"
    assert "/venv/bin/python" in check.text


BLOCK = (
    "# prepush-ci: begin\n- id: prepush-ci-pre-push\n  entry: prepush-ci hook pre-push\n"
    "  verbose: true\n# prepush-ci: end\n"
)


def manager(name: str = "pre-commit", **changes: object) -> ManagerFacts:
    facts = ManagerFacts(
        manager=name,
        detected=True,
        file=".pre-commit-config.yaml",
        content=BLOCK,
        hooks_path=None,
        hooks_directory="/repo/.git/hooks",
        installed=Script(exists=True, executable=True, content=f"# run {name}\n"),
    )
    return replace(facts, **changes)  # type: ignore[arg-type]


OWN = "prepush-ci 0.2.0 (git abcdef0)"
FOUND = "/usr/local/bin/prepush-ci"
SAME = Binary(FOUND, OWN)


def manager_check(hook: str, facts: ManagerFacts, binary: Binary = SAME) -> Check:
    return doctor_hooks.manager_check(hook, facts, OWN, lambda: binary)


def test_a_manager_with_its_block_and_its_activation_passes() -> None:
    assert manager_check("pre-push", manager()).status == "ok"
    assert manager_check("pre-push", manager("lefthook")).status == "ok"


def test_a_missing_manager_file_fails_and_names_it() -> None:
    check = manager_check("pre-push", manager(content=None))

    assert check.status == "fail"
    assert ".pre-commit-config.yaml" in check.text


def test_a_file_without_the_block_for_this_hook_fails() -> None:
    check = manager_check("commit-msg", manager())

    assert check.status == "fail"
    assert "no prepush-ci block for commit-msg" in check.text


def test_a_block_that_is_never_closed_fails_with_the_reason() -> None:
    check = manager_check("pre-push", manager(content="# prepush-ci: begin\nx\n"))

    assert check.status == "fail"
    assert "begin" in check.text


def test_the_fix_names_install_without_the_option_for_a_detected_manager() -> None:
    check = manager_check("pre-push", manager(content=None))

    assert check.fix is not None
    assert check.fix.startswith("run `prepush-ci install`;")
    assert "--hooks native" in check.fix


def test_the_fix_names_the_option_for_a_named_manager_and_no_native_hint() -> None:
    check = manager_check("pre-push", manager(content=None, detected=False))

    assert check.fix == "run `prepush-ci install --hooks pre-commit`"


def test_a_manager_that_is_not_activated_names_the_step() -> None:
    for name, step in (
        ("pre-commit", "pre-commit install"),
        ("lefthook", "lefthook install"),
    ):
        check = manager_check("pre-push", manager(name, installed=Script(exists=False)))

        assert check.status == "fail"
        assert "not activated" in check.text
        assert check.fix is not None and step in check.fix


def test_a_hook_script_that_is_not_executable_is_not_an_activation() -> None:
    check = manager_check(
        "pre-push", manager(installed=Script(exists=True, content="pre-commit"))
    )

    assert check.status == "fail"
    assert "not executable" in check.text


def test_a_hook_script_that_does_not_name_the_manager_is_not_an_activation() -> None:
    script = Script(exists=True, executable=True, content="#!/bin/sh\necho mine\n")

    check = manager_check("pre-push", manager(installed=script))

    assert check.status == "fail"
    assert "does not run pre-commit" in check.text


def husky(**changes: object) -> ManagerFacts:
    defaults: dict[str, object] = {
        "file": ".husky/pre-push",
        "hooks_path": ".husky/_",
        "hooks_directory": "/repo/.husky/_",
        "installed": GOOD_SCRIPT,
    }
    return manager("husky", **{**defaults, **changes})


def test_husky_with_its_hooks_path_and_its_hook_passes() -> None:
    assert manager_check("pre-push", husky()).status == "ok"
    assert manager_check("pre-push", husky(hooks_path=".husky")).status == "ok"


def test_husky_without_its_hooks_path_fails_and_names_it_and_npx_husky() -> None:
    for path in (None, "/elsewhere"):
        check = manager_check("pre-push", husky(hooks_path=path))

        assert check.status == "fail"
        assert "core.hooksPath" in check.text and "husky" in check.text
        assert check.fix is not None and "npx husky" in check.fix


def test_a_husky_hook_that_is_missing_or_not_executable_fails() -> None:
    missing = manager_check("pre-push", husky(installed=Script(exists=False)))
    plain = manager_check("pre-push", husky(installed=Script(exists=True)))

    assert missing.status == "fail"
    assert ".husky/_/pre-push" in missing.text and "does not exist" in missing.text
    assert plain.status == "fail"
    assert "not executable" in plain.text


# The prepush-ci the hooks find on PATH


def test_the_same_version_on_path_passes_and_the_line_names_the_executable_and_its_line() -> (
    None
):
    check = manager_check("pre-push", manager(), Binary(FOUND, OWN))

    assert check.status == "ok"
    assert FOUND in check.text and OWN in check.text


def test_another_version_on_path_fails_and_names_the_executable_both_lines_and_path() -> (
    None
):
    check = manager_check("pre-push", manager(), Binary(FOUND, "prepush-ci 0.0.1"))

    assert check.status == "fail"
    assert (
        FOUND in check.text and "prepush-ci 0.0.1" in check.text and OWN in check.text
    )
    assert check.fix is not None and "PATH" in check.fix and OWN in check.fix


def test_the_whole_line_is_compared_not_the_version_number() -> None:
    check = manager_check(
        "pre-push", manager(), Binary(FOUND, "prepush-ci 0.2.0 (direct install)")
    )

    assert check.status == "fail"


def test_no_executable_on_path_fails_and_names_path() -> None:
    check = manager_check("pre-push", manager(), Binary(None))

    assert check.status == "fail"
    assert "PATH" in check.text
    assert check.fix is not None and "PATH" in check.fix and OWN in check.fix


def test_an_executable_whose_version_was_not_read_fails_with_its_path_and_the_reason() -> (
    None
):
    for why in ("it exited with status 1", "it printed nothing"):
        check = manager_check("pre-push", manager(), Binary(FOUND, None, why))

        assert check.status == "fail"
        assert FOUND in check.text and "could not be read" in check.text
        assert why in check.text
        assert check.fix is not None and "PATH" in check.fix and OWN in check.fix


def test_the_executable_is_looked_up_only_for_a_check_that_passes_everything_else() -> (
    None
):
    looked: list[str] = []

    def binary() -> Binary:
        looked.append("looked")
        return Binary(FOUND, OWN)

    broken = manager(content=None)
    doctor_hooks.manager_check("pre-push", broken, OWN, binary)
    doctor_hooks.manager_check("pre-push", manager(), OWN, binary)

    assert looked == ["looked"]


def test_the_fix_of_a_failure_that_is_already_there_is_not_changed_by_the_executable() -> (
    None
):
    check = manager_check("pre-push", manager(content=None), Binary(None))

    assert check.fix is not None and check.fix.startswith("run `prepush-ci install`;")
    assert "PATH" not in check.text


def test_a_manager_whose_doctor_cannot_read_its_own_version_fails_without_running_the_executable() -> (
    None
):
    def never() -> Binary:
        raise AssertionError("the executable was run")

    check = doctor_hooks.manager_check("pre-push", manager(), None, never)

    assert check.status == "fail"
    assert "its own version" in check.text
    assert check.fix is not None and "install" in check.fix


def test_a_failure_that_is_already_there_stands_when_doctor_cannot_read_its_own_version() -> (
    None
):
    check = doctor_hooks.manager_check(
        "pre-push", manager(content=None), None, lambda: SAME
    )

    assert check.status == "fail"
    assert "its own version" not in check.text


# --- The pre-push hook of a pre-commit block shows its messages -------------------------------

VERBOSE = "      verbose: true"


def written(*, pre_push: str | None = VERBOSE, commit_msg: str | None = VERBOSE) -> str:
    """The block `install` writes, with the `verbose` line of each hook replaced (None: left out)."""
    lines = pre_commit_block("")
    hook = ""
    out: list[str] = []
    for line in lines:
        if line.strip().startswith("- id:"):
            hook = line.strip().removeprefix("- id: prepush-ci-")
        if line == VERBOSE:
            line = {"pre-push": pre_push, "commit-msg": commit_msg}[hook] or ""
            if not line:
                continue
        out.append(line)
    return "\n".join(out) + "\n"


def test_a_block_of_an_earlier_version_fails_the_pre_push_check_and_names_the_key() -> (
    None
):
    facts = manager(content=written(pre_push=None))

    check = manager_check("pre-push", facts)

    assert check.status == "fail"
    assert ".pre-commit-config.yaml" in check.text and "verbose: true" in check.text
    assert check.fix is not None and "prepush-ci install" in check.fix
    assert manager_check("commit-msg", facts).status == "ok"


def test_a_block_that_install_wrote_passes_the_pre_push_check() -> None:
    assert manager_check("pre-push", manager(content=written())).status == "ok"


def test_verbose_false_fails_the_pre_push_check() -> None:
    check = manager_check(
        "pre-push", manager(content=written(pre_push="      verbose: false"))
    )

    assert check.status == "fail"
    assert "verbose: true" in check.text


def test_a_comment_with_the_key_fails_the_pre_push_check() -> None:
    check = manager_check(
        "pre-push", manager(content=written(pre_push="      # verbose: true"))
    )

    assert check.status == "fail"


def test_the_key_on_the_other_hook_fails_the_pre_push_check() -> None:
    check = manager_check("pre-push", manager(content=written(pre_push=None)))

    assert check.status == "fail"


def test_a_commit_msg_hook_without_the_key_passes_both_checks() -> None:
    facts = manager(content=written(commit_msg=None))

    assert manager_check("commit-msg", facts).status == "ok"
    assert manager_check("pre-push", facts).status == "ok"


def test_the_missing_key_is_reported_before_the_activation() -> None:
    facts = manager(content=written(pre_push=None), installed=Script(exists=False))

    check = manager_check("pre-push", facts)

    assert check.status == "fail"
    assert "verbose: true" in check.text


def test_the_missing_key_fails_before_the_executable_is_run() -> None:
    def never() -> Binary:
        raise AssertionError("the executable was run")

    check = doctor_hooks.manager_check(
        "pre-push", manager(content=written(pre_push=None)), OWN, never
    )

    assert check.status == "fail"


def test_other_managers_do_not_need_the_key() -> None:
    check = manager_check(
        "pre-push", manager("lefthook", content=written(pre_push=None))
    )

    assert check.status == "ok"
