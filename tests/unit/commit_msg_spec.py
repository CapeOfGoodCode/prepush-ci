import pytest

from prepush_ci.core.commit_msg import (
    Cleanup,
    InvalidMode,
    Mode,
    UnsupportedCommentChar,
    clean_up,
    editor_was_used,
    is_blank_message,
    is_template_untouched,
    parse_mode,
    require_known_comment_setting,
    resolve_cleanup,
)
from prepush_ci.core.config import Trailer


def test_unset_variable_means_not_opted_in() -> None:
    assert parse_mode(None) is Mode.OFF


def test_empty_variable_counts_as_unset() -> None:
    assert parse_mode("") is Mode.OFF


def test_off_means_not_opted_in() -> None:
    assert parse_mode("off") is Mode.OFF


def test_full_means_opted_in() -> None:
    assert parse_mode("full") is Mode.FULL


@pytest.mark.parametrize("value", ["ful", "FULL", "Off", "full ", "1", "yes"])
def test_any_other_value_is_refused_and_the_error_names_full_and_off(
    value: str,
) -> None:
    with pytest.raises(InvalidMode) as error_info:
        parse_mode(value)

    message = str(error_info.value)
    assert "`full`" in message
    assert "`off`" in message
    assert repr(value) in message


@pytest.mark.parametrize(
    "text",
    ["", "\n", "  \n\t\n", "# Please enter the commit message\n", "\n# a\n# b\n"],
)
def test_a_message_of_only_whitespace_and_comment_lines_is_blank(text: str) -> None:
    assert is_blank_message(text)


@pytest.mark.parametrize("text", ["add x\n", "# comment\nsubject\n", "\n\nx"])
def test_a_message_with_any_other_line_is_not_blank(text: str) -> None:
    assert not is_blank_message(text)


def test_trailer_renders_as_key_colon_space_value() -> None:
    assert Trailer("Full-Check", "yes").line() == "Full-Check: yes"


SCISSORS = "# ------------------------ >8 ------------------------"


def test_everything_below_the_scissors_line_is_not_part_of_the_message() -> None:
    text = f"\n{SCISSORS}\n# Do not modify or remove the line above.\ndiff --git a/b b/b\n+b\n"

    assert is_blank_message(text)


def test_a_message_above_the_scissors_line_is_not_blank() -> None:
    assert not is_blank_message(f"add x\n{SCISSORS}\ndiff --git a/b b/b\n")


def test_a_scissors_line_with_another_comment_char_ends_the_message() -> None:
    text = (
        "\n; ------------------------ >8 ------------------------\ndiff --git a/b b/b\n"
    )

    assert is_blank_message(text, comment=";")


def test_the_default_comment_char_scissors_line_is_text_under_another_comment_char() -> (
    None
):
    assert not is_blank_message(f"{SCISSORS}\n", comment=";")


def test_lines_starting_with_the_configured_comment_char_are_comments() -> None:
    assert is_blank_message("; Please enter the message\n;\n", comment=";")


def test_hash_lines_are_text_when_the_comment_char_is_another() -> None:
    assert not is_blank_message("# heading\n", comment=";")


def test_a_multi_character_comment_string_marks_comment_lines() -> None:
    assert is_blank_message("// a\n//b\n", comment="//")
    assert not is_blank_message("/ a\n", comment="//")


def test_no_comment_setting_and_a_fixed_one_are_accepted() -> None:
    require_known_comment_setting(None)
    require_known_comment_setting(";")
    require_known_comment_setting("//")


def test_the_automatic_comment_char_is_refused_with_an_explanation() -> None:
    with pytest.raises(UnsupportedCommentChar) as error_info:
        require_known_comment_setting("auto")

    assert "auto" in str(error_info.value)
    assert "PREPUSH_CI" in str(error_info.value)


def test_an_empty_comment_setting_is_refused() -> None:
    with pytest.raises(UnsupportedCommentChar):
        require_known_comment_setting("")


def test_comment_lines_are_text_when_git_only_cleans_up_whitespace() -> None:
    assert not is_blank_message("#123 fix the bug\n", Cleanup.WHITESPACE)
    assert not is_blank_message("# a\n", Cleanup.SCISSORS)


def test_whitespace_alone_is_blank_in_every_mode_but_verbatim() -> None:
    for cleanup in (Cleanup.STRIP, Cleanup.WHITESPACE, Cleanup.SCISSORS):
        assert is_blank_message("  \n\t\n", cleanup)
    assert not is_blank_message("  \n", Cleanup.VERBATIM)


def test_a_verbatim_message_is_blank_only_without_any_byte() -> None:
    assert is_blank_message("", Cleanup.VERBATIM)
    assert not is_blank_message("# a\n", Cleanup.VERBATIM)


def test_the_scissors_line_ends_the_message_in_the_scissors_mode() -> None:
    assert is_blank_message(f"\n{SCISSORS}\ndiff\n", Cleanup.SCISSORS)
    assert not is_blank_message(f"# a\n{SCISSORS}\ndiff\n", Cleanup.SCISSORS)


@pytest.mark.parametrize("mode", list(Cleanup))
def test_a_configured_cleanup_mode_wins_over_the_editor(mode: Cleanup) -> None:
    assert resolve_cleanup(mode.value, editor_used=True) is mode
    assert resolve_cleanup(mode.value, editor_used=False) is mode


@pytest.mark.parametrize("configured", [None, "default"])
def test_the_default_cleanup_strips_when_an_editor_is_used(
    configured: str | None,
) -> None:
    assert resolve_cleanup(configured, editor_used=True) is Cleanup.STRIP


@pytest.mark.parametrize("configured", [None, "default"])
def test_the_default_cleanup_keeps_comment_lines_without_an_editor(
    configured: str | None,
) -> None:
    assert resolve_cleanup(configured, editor_used=False) is Cleanup.WHITESPACE


def test_git_marks_a_commit_without_editor_with_the_colon_command() -> None:
    assert not editor_was_used(":", "#123 fix the bug\n")


def test_any_other_editor_was_used() -> None:
    assert editor_was_used("vim", "\n# Please enter the message\n")
    assert editor_was_used(None, "#123\n")


def test_the_colon_command_chosen_by_the_user_leaves_the_editor_template() -> None:
    assert editor_was_used(":", "\n# Please enter the commit message\n")


def test_a_message_equal_to_the_template_after_cleanup_is_untouched() -> None:
    template = "Subject here\n\n# describe why\n"
    message = "Subject here\n\n# describe why\n#\n# On branch main\n"

    assert is_template_untouched(message, template, Cleanup.STRIP)


def test_a_message_that_differs_from_the_template_is_touched() -> None:
    assert not is_template_untouched("Real subject\n", "Subject here\n", Cleanup.STRIP)
    assert not is_template_untouched(
        "Subject here\n\nmore\n", "Subject here\n", Cleanup.STRIP
    )


def test_whitespace_differences_do_not_make_a_template_touched() -> None:
    assert is_template_untouched(
        "Subject here  \n\n\n", "Subject here\n", Cleanup.WHITESPACE
    )


def test_comment_lines_count_for_the_template_unless_the_cleanup_strips_them() -> None:
    assert not is_template_untouched(
        "Subject\n# note\n", "Subject\n", Cleanup.WHITESPACE
    )
    assert is_template_untouched("Subject\n# note\n", "Subject\n", Cleanup.STRIP)


def test_a_message_kept_verbatim_is_never_untouched() -> None:
    assert not is_template_untouched("Subject\n", "Subject\n", Cleanup.VERBATIM)


def test_an_empty_template_is_never_untouched() -> None:
    assert not is_template_untouched("Subject\n", "", Cleanup.STRIP)
    assert not is_template_untouched("", "", Cleanup.STRIP)


def test_the_diff_below_the_scissors_line_is_not_part_of_the_message_for_the_template() -> (
    None
):
    assert is_template_untouched(
        f"Subject\n{SCISSORS}\ndiff\n", "Subject\n", Cleanup.SCISSORS
    )


def test_the_template_is_cleaned_with_the_configured_comment_prefix() -> None:
    assert is_template_untouched(
        "Subject\n; note\n", "Subject\n; other\n", Cleanup.STRIP, comment=";"
    )


def test_cleaning_up_trims_collapses_and_keeps_verbatim_text_as_it_is() -> None:
    text = "\n\nsubject  \n\n\n\nbody\n\n"

    assert clean_up(text, Cleanup.WHITESPACE) == "subject\n\nbody\n"
    assert clean_up(text, Cleanup.VERBATIM) == text


def test_sign_off_lines_do_not_make_a_message_non_blank() -> None:
    assert is_blank_message("\nSigned-off-by: A <a@example.com>\n\n# Please enter\n")
    assert is_blank_message(
        "Signed-off-by: A <a@example.com>\nSigned-off-by: B <b@x.y>\n"
    )
    assert not is_blank_message("subject\nSigned-off-by: A <a@example.com>\n")


def test_sign_off_lines_do_not_make_a_template_touched() -> None:
    template = "Subject here\n\n# describe why\n"
    message = "Subject here\n\nSigned-off-by: A <a@example.com>\n\n# Please enter\n"

    assert is_template_untouched(message, template, Cleanup.STRIP)


def test_text_after_the_template_makes_it_touched_even_with_a_sign_off() -> None:
    assert not is_template_untouched(
        "Subject\nmore\nSigned-off-by: A <a@example.com>\n", "Subject\n", Cleanup.STRIP
    )
