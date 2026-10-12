from dataclasses import replace

from prepush_ci.core.doctor_hooks import (
    ManagerFacts,
    NativeFacts,
    Script,
    manager_check,
    native_check,
    none_check,
    refusal_check,
)

DIRECTORY = "/repo/.git/prepush-ci/hooks"
GOOD_SCRIPT = Script(exists=True, executable=True, text="#!/bin/sh\n")


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


BLOCK = "# prepush-ci: begin\nprepush-ci hook pre-push\n# prepush-ci: end\n"


def manager(name: str = "pre-commit", **changes: object) -> ManagerFacts:
    facts = ManagerFacts(
        manager=name,
        detected=True,
        file=".pre-commit-config.yaml",
        text=BLOCK,
        hooks_path=None,
        hooks_directory="/repo/.git/hooks",
        installed=Script(exists=True, executable=True, text=f"# run {name}\n"),
    )
    return replace(facts, **changes)  # type: ignore[arg-type]


def test_a_manager_with_its_block_and_its_activation_passes() -> None:
    assert manager_check("pre-push", manager()).status == "ok"
    assert manager_check("pre-push", manager("lefthook")).status == "ok"


def test_a_missing_manager_file_fails_and_names_it() -> None:
    check = manager_check("pre-push", manager(text=None))

    assert check.status == "fail"
    assert ".pre-commit-config.yaml" in check.text


def test_a_file_without_the_block_for_this_hook_fails() -> None:
    check = manager_check("commit-msg", manager())

    assert check.status == "fail"
    assert "no prepush-ci block for commit-msg" in check.text


def test_a_block_that_is_never_closed_fails_with_the_reason() -> None:
    check = manager_check("pre-push", manager(text="# prepush-ci: begin\nx\n"))

    assert check.status == "fail"
    assert "begin" in check.text


def test_the_fix_names_install_without_the_option_for_a_detected_manager() -> None:
    check = manager_check("pre-push", manager(text=None))

    assert check.fix is not None
    assert check.fix.startswith("run `prepush-ci install`;")
    assert "--hooks native" in check.fix


def test_the_fix_names_the_option_for_a_named_manager_and_no_native_hint() -> None:
    check = manager_check("pre-push", manager(text=None, detected=False))

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
        "pre-push", manager(installed=Script(exists=True, text="pre-commit"))
    )

    assert check.status == "fail"
    assert "not executable" in check.text


def test_a_hook_script_that_does_not_name_the_manager_is_not_an_activation() -> None:
    script = Script(exists=True, executable=True, text="#!/bin/sh\necho mine\n")

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
