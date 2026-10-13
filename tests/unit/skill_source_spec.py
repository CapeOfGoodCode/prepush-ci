from prepush_ci.core.skill import INSTALLED_FILE, choose

DATA_FILE = "../../../prepush-ci-setup/SKILL.md"


def test_the_checkout_file_is_used_when_it_exists_even_if_the_distribution_lists_one() -> (
    None
):
    source = choose(True, [DATA_FILE])

    assert source is not None
    assert source.checkout is True


def test_the_installed_data_file_is_used_without_a_checkout() -> None:
    source = choose(False, ["prepush_ci/cli.py", DATA_FILE])

    assert source is not None
    assert (source.checkout, source.entry) == (False, DATA_FILE)


def test_the_skill_is_not_found_without_a_checkout_and_without_a_data_file() -> None:
    assert choose(False, []) is None
    assert choose(False, ["prepush_ci/cli.py", "other/SKILL.md", "SKILL.md"]) is None


def test_a_listed_file_is_the_skill_only_when_it_ends_with_the_whole_path_of_the_file() -> (
    None
):
    assert choose(False, [f"x-{INSTALLED_FILE}"]) is None
    source = choose(False, [INSTALLED_FILE])
    assert source is not None
    assert source.entry == INSTALLED_FILE


def test_the_checkout_is_chosen_without_an_entry() -> None:
    source = choose(True, [])

    assert source is not None
    assert source.entry is None
