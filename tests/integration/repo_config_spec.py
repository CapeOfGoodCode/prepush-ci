from pathlib import Path

import pytest

from prepush_ci.core.config import ConfigError
from prepush_ci.repo_config import load_repository_config


def test_config_file_at_the_repository_root_is_read(repo: Path) -> None:
    (repo / ".prepush-ci.toml").write_text('check = "scripts/ci"\n')

    assert load_repository_config(repo).check == "scripts/ci"


def test_config_in_pyproject_toml_is_read_when_there_is_no_dedicated_file(
    repo: Path,
) -> None:
    (repo / "pyproject.toml").write_text('[tool.prepush-ci]\ncheck = "make ci"\n')

    assert load_repository_config(repo).check == "make ci"


def test_dedicated_file_wins_over_pyproject_toml_in_a_real_repository(
    repo: Path,
) -> None:
    (repo / ".prepush-ci.toml").write_text('check = "scripts/ci"\n')
    (repo / "pyproject.toml").write_text('[tool.prepush-ci]\ncheck = "make ci"\n')

    assert load_repository_config(repo).check == "scripts/ci"


def test_config_is_read_from_the_root_when_run_in_a_subdirectory(repo: Path) -> None:
    (repo / ".prepush-ci.toml").write_text('check = "scripts/ci"\n')
    subdirectory = repo / "src" / "deep"
    subdirectory.mkdir(parents=True)

    assert load_repository_config(subdirectory).check == "scripts/ci"


def test_a_repository_without_any_config_names_both_places(repo: Path) -> None:
    with pytest.raises(ConfigError) as error_info:
        load_repository_config(repo)

    message = str(error_info.value)
    assert ".prepush-ci.toml" in message
    assert "[tool.prepush-ci]" in message


def test_a_directory_outside_any_git_repository_is_reported(tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as error_info:
        load_repository_config(tmp_path)

    assert "not inside a git working tree" in str(error_info.value)
