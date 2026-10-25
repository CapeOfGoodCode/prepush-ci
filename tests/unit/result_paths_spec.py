"""Which named result files the tool may delete: decided from what git lists, never from the disk."""

from prepush_ci.core.result_paths import (
    TRACKED,
    components,
    fold,
    listed,
    tracked_reason,
)

TREE_LISTING = (
    "100644 blob " + "a" * 40 + "\tdocs/cov.json\0"
    "160000 commit " + "b" * 40 + "\tsub\0"
    "100755 blob " + "c" * 40 + "\tscripts/ci\0"
)
INDEX_LISTING = (
    "100644 " + "a" * 40 + " 0\tdocs/cov.json\0"
    "100644 " + "d" * 40 + " 0\tout/a.xml\0"
    "160000 " + "e" * 40 + " 0\tvendor/lib\0"
)


def test_a_name_folds_without_case_and_without_trailing_dots_and_spaces_in_each_component() -> (
    None
):
    assert fold("Docs/Cov.JSON.") == "docs/cov.json"
    assert fold("docs. /cov.json ") == "docs/cov.json"
    assert fold("out/a.xml") == "out/a.xml"


def test_a_listing_gives_every_path_and_the_gitlinks() -> None:
    paths, gitlinks = listed(TREE_LISTING, INDEX_LISTING)

    assert paths == {
        "docs/cov.json",
        "sub",
        "scripts/ci",
        "out/a.xml",
        "vendor/lib",
    }
    assert gitlinks == {"sub", "vendor/lib"}


def test_an_empty_listing_lists_nothing() -> None:
    assert listed("", "") == (frozenset(), frozenset())


def test_a_path_of_the_listing_is_tracked() -> None:
    paths, gitlinks = listed(TREE_LISTING, INDEX_LISTING)

    assert tracked_reason("docs/cov.json", paths, gitlinks) == "the file is tracked"


def test_a_path_that_is_only_in_the_index_is_tracked() -> None:
    paths, gitlinks = listed(TREE_LISTING, INDEX_LISTING)

    assert tracked_reason("out/a.xml", paths, gitlinks) == "the file is tracked"


def test_a_path_under_another_case_or_a_trailing_dot_is_tracked() -> None:
    paths, gitlinks = listed(TREE_LISTING, INDEX_LISTING)

    assert tracked_reason("Docs/Cov.json", paths, gitlinks) == "the file is tracked"
    assert tracked_reason("docs/cov.json.", paths, gitlinks) == "the file is tracked"


def test_a_path_under_a_gitlink_is_in_another_repository() -> None:
    paths, gitlinks = listed(TREE_LISTING, INDEX_LISTING)
    another = "the file is in another repository"

    assert tracked_reason("sub/README.md", paths, gitlinks) == another
    assert tracked_reason("Vendor/lib/deep/a.xml", paths, gitlinks) == another


def test_a_path_that_is_not_listed_may_be_deleted() -> None:
    paths, gitlinks = listed(TREE_LISTING, INDEX_LISTING)

    assert tracked_reason("out/b.xml", paths, gitlinks) is None
    assert tracked_reason("docs/other.json", paths, gitlinks) is None


def test_a_dot_and_an_empty_component_are_dropped_from_a_path() -> None:
    assert components("./docs//./cov.json/") == ["docs", "cov.json"]


def test_a_path_that_is_only_dots_and_slashes_has_no_component() -> None:
    assert components("./") == []


def test_a_tracked_path_is_tracked_however_it_is_written() -> None:
    paths, gitlinks = listed(TREE_LISTING)

    assert tracked_reason("docs//./cov.json/", paths, gitlinks) == TRACKED
