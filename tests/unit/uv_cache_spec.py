from prepush_ci.core.uv_cache import (
    TEMPORARY_WARNING,
    cache_directory,
    inside,
    is_temporary,
)


def test_a_path_below_the_directory_is_inside() -> None:
    assert inside("/home/me/.cache/uv/venv/bin/python", "/home/me/.cache/uv")


def test_the_directory_itself_is_inside() -> None:
    assert inside("/home/me/.cache/uv", "/home/me/.cache/uv")


def test_a_sibling_that_shares_a_name_prefix_is_not_inside() -> None:
    assert not inside("/home/me/.cache/uv2/bin/python", "/home/me/.cache/uv")


def test_a_trailing_separator_and_dot_segments_do_not_matter() -> None:
    assert inside("/home/me/.cache/uv/./a/../bin/python", "/home/me/.cache/uv/")


def test_a_path_that_climbs_out_of_the_directory_is_not_inside() -> None:
    assert not inside("/home/me/.cache/uv/../bin/python", "/home/me/.cache/uv")


def test_everything_absolute_is_inside_the_root() -> None:
    assert inside("/usr/bin/python", "/")


def test_a_relative_path_is_not_inside_an_absolute_directory() -> None:
    assert not inside("home/me/.cache/uv/bin/python", "/home/me/.cache/uv")


def test_on_windows_case_and_separators_do_not_matter() -> None:
    assert inside(
        "C:/Users/Me/AppData/Local/UV/cache/venv/Scripts/python.exe",
        r"c:\users\me\appdata\local\uv\cache",
        windows=True,
    )


def test_on_windows_another_drive_is_not_inside() -> None:
    assert not inside("D:/uv/cache/python.exe", "C:/uv/cache", windows=True)


def test_on_other_platforms_case_matters() -> None:
    assert not inside("/Home/me/.cache/uv/python", "/home/me/.cache/uv")


def test_uv_cache_dir_names_the_cache_directory() -> None:
    environ = {"UV_CACHE_DIR": "/elsewhere/uv", "XDG_CACHE_HOME": "/x", "HOME": "/h"}

    assert cache_directory(environ, "/work") == "/elsewhere/uv"


def test_a_relative_uv_cache_dir_is_relative_to_the_working_directory() -> None:
    assert cache_directory({"UV_CACHE_DIR": "cache"}, "/work") == "/work/cache"


def test_an_empty_uv_cache_dir_is_ignored() -> None:
    environ = {"UV_CACHE_DIR": "", "XDG_CACHE_HOME": "/xdg"}

    assert cache_directory(environ, "/work") == "/xdg/uv"


def test_the_default_follows_xdg_cache_home() -> None:
    assert cache_directory({"XDG_CACHE_HOME": "/xdg", "HOME": "/h"}, "/w") == "/xdg/uv"


def test_an_empty_xdg_cache_home_is_ignored() -> None:
    assert cache_directory({"XDG_CACHE_HOME": "", "HOME": "/h"}, "/w") == "/h/.cache/uv"


def test_the_default_is_under_home_when_nothing_else_is_set() -> None:
    assert cache_directory({"HOME": "/home/me"}, "/work") == "/home/me/.cache/uv"


def test_without_any_variable_the_cache_directory_is_unknown() -> None:
    assert cache_directory({}, "/work") is None


def test_on_windows_the_default_is_under_local_app_data() -> None:
    environ = {"LOCALAPPDATA": r"C:\Users\Me\AppData\Local", "HOME": "/h"}

    assert (
        cache_directory(environ, r"C:\work", windows=True)
        == r"C:\Users\Me\AppData\Local\uv\cache"
    )


def test_on_windows_home_and_xdg_cache_home_play_no_part() -> None:
    environ = {"XDG_CACHE_HOME": "/xdg", "HOME": "/h"}

    assert cache_directory(environ, r"C:\work", windows=True) is None


def test_an_interpreter_in_the_cache_is_temporary() -> None:
    environ = {"UV_CACHE_DIR": "/c"}

    assert is_temporary("/c/builds/venv/bin/python", environ, "/work")


def test_an_interpreter_outside_the_cache_is_not_temporary() -> None:
    environ = {"UV_CACHE_DIR": "/c"}

    assert not is_temporary("/usr/bin/python", environ, "/work")


def test_an_unknown_cache_directory_makes_nothing_temporary() -> None:
    assert not is_temporary("/usr/bin/python", {}, "/work")


def test_an_interpreter_inside_the_resolved_cache_directory_is_temporary() -> None:
    environ = {"UV_CACHE_DIR": "/link"}

    assert is_temporary(
        "/real/builds/venv/bin/python", environ, "/work", resolve=lambda d: "/real"
    )


def test_the_cache_directory_as_found_still_counts_when_it_resolves_elsewhere() -> None:
    environ = {"UV_CACHE_DIR": "/link"}

    assert is_temporary(
        "/link/builds/venv/bin/python", environ, "/work", resolve=lambda d: "/real"
    )


def test_a_sibling_of_the_resolved_cache_directory_is_not_temporary() -> None:
    environ = {"UV_CACHE_DIR": "/link"}

    assert not is_temporary(
        "/real2/bin/python", environ, "/work", resolve=lambda d: "/real"
    )


def test_the_interpreter_is_never_resolved() -> None:
    seen: list[str] = []

    def resolve(directory: str) -> str:
        seen.append(directory)
        return directory

    is_temporary("/usr/bin/python", {"UV_CACHE_DIR": "/c"}, "/work", resolve=resolve)

    assert seen == ["/c"]


def test_nothing_is_resolved_when_the_cache_directory_is_unknown() -> None:
    def resolve(directory: str) -> str:
        raise AssertionError(directory)

    assert not is_temporary("/usr/bin/python", {}, "/work", resolve=resolve)


def test_the_warning_says_temporary_and_names_the_fix() -> None:
    assert "temporary" in TEMPORARY_WARNING
    assert "uv tool install prepush-ci" in TEMPORARY_WARNING
    assert "prepush-ci install" in TEMPORARY_WARNING
