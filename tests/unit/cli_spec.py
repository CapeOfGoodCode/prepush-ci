import pytest

from prepush_ci.cli import main


def test_version_flag_prints_the_installed_package_version(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])

    assert exit_info.value.code == 0
    assert capsys.readouterr().out.startswith("prepush-ci ")


def test_running_without_a_command_prints_usage_and_succeeds(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main([]) == 0
    assert "usage: prepush-ci" in capsys.readouterr().out


def test_the_usage_lists_the_verify_command(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main([]) == 0
    assert "verify" in capsys.readouterr().out


def test_verify_without_a_sha_exits_1_instead_of_argparses_usage_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["verify"]) == 1
    assert capsys.readouterr().out.startswith("not verified: the sha is missing")


def test_verify_after_a_double_dash_without_a_sha_exits_1(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--", "verify"]) == 1
    assert capsys.readouterr().out.startswith("not verified: the sha is missing")


def test_the_usage_lists_the_run_command(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main([]) == 0
    assert "run " in capsys.readouterr().out
