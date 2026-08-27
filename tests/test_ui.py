"""Tests for the Rich presentation layer (`corpora_cli.ui`).

Two things are worth pinning down here: the conversion task list actually
tracks `run_conversion`'s checkpoints (and never swallows a message it does
not recognise -- those strings live in corpora-py and can change under us),
and the help colouriser paints argparse's output without ANSI leaking into
non-terminal output.
"""

import io

import pytest
from rich.console import Console

from corpora_cli import cli, ui


def _console() -> tuple[Console, io.StringIO]:
    """A console that renders like a terminal but into a buffer."""
    buffer = io.StringIO()
    return (
        Console(
            file=buffer,
            force_terminal=True,
            width=100,
            highlight=False,
            soft_wrap=True,
            theme=ui.THEME,
        ),
        buffer,
    )


# The checkpoints `run_conversion` reports, in the order it reports them.
_CHECKPOINT_LOG = [
    "Parsing plain source and building Text-Fabric dataset...",
    "Text-Fabric dataset ready. Compiling cache and packaging .corpus archive...",
    "Validating converted corpus...",
    "Conversion complete.",
]


class TestConversionReporter:
    def test_plain_mode_keeps_the_upstream_log_lines(self, capsys):
        with ui.ConversionReporter(live=False) as reporter:
            reporter.title("Moby Dick")
            for message in _CHECKPOINT_LOG:
                reporter.log(message)

        err = capsys.readouterr().err
        assert "Title: Moby Dick" in err
        for message in _CHECKPOINT_LOG:
            assert message in err
        # The scripting contract: no live decoration, no ANSI on a non-tty.
        assert "\x1b" not in err

    def test_live_mode_renders_a_task_list(self):
        console, buffer = _console()
        with ui.ConversionReporter(console, live=True) as reporter:
            for message in _CHECKPOINT_LOG:
                reporter.log(message)

        output = buffer.getvalue()
        for label in ui._STEPS:
            assert label in output
        # Every step landed, and the final line is the completion notice.
        assert output.count(ui.OK) >= len(ui._STEPS)
        assert "Conversion complete." in output

    def test_live_mode_marks_the_running_step_failed(self):
        console, buffer = _console()
        with pytest.raises(RuntimeError):
            with ui.ConversionReporter(console, live=True) as reporter:
                reporter.log(_CHECKPOINT_LOG[0])
                raise RuntimeError("converter blew up")

        # A crash leaves a ❌ where the spinner was, never a spinner mid-flight.
        assert ui.ERR in buffer.getvalue()

    @pytest.mark.parametrize("live", [True, False])
    def test_unrecognised_messages_are_never_swallowed(self, live, capsys):
        # Converter warnings arrive through the same callback as the
        # checkpoints; a checkpoint string that changes upstream must degrade
        # to this too, rather than disappearing.
        console, buffer = _console() if live else (None, None)
        with ui.ConversionReporter(console, live=live) as reporter:
            reporter.log("Category downgraded from book to document.")

        output = buffer.getvalue() if live else capsys.readouterr().err
        assert "Category downgraded from book to document." in output


class TestHelp:
    def test_headings_and_flags_get_the_accent(self):
        text = ui.colorize_help("usage: corpora [-h]\n\noptions:\n  -h, --help  show this\n")
        styled = {(text.plain[span.start : span.end], str(span.style)) for span in text.spans}
        assert ("usage:", "heading") in styled
        assert ("options:", "heading") in styled
        assert ("--help", "arg") in styled
        # The prog name rides a named group, which is the one styling path
        # that does not name its style inline.
        assert ("corpora ", "accent") in styled

    def test_help_is_plain_text_when_not_a_terminal(self):
        buffer = io.StringIO()
        cli.build_parser().print_help(buffer)
        rendered = buffer.getvalue()
        assert "\x1b" not in rendered
        assert "convert" in rendered


class TestTables:
    def test_cell_contents_are_not_read_as_markup(self):
        console, buffer = _console()
        console.print(ui.passage_table(["[bold]not markup[/bold]"]))
        assert "[bold]not markup[/bold]" in buffer.getvalue()

    def test_key_value_table_renders_every_pair(self):
        console, buffer = _console()
        console.print(ui.key_value_table({"name": "Moby Dick"}, key_header="f", value_header="v"))
        output = buffer.getvalue()
        assert "name" in output
        assert "Moby Dick" in output
