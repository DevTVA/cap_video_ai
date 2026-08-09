from click.testing import CliRunner
from batch_video_cutter.ui.cli import main_cli

def test_cli_render_options_help():
    runner = CliRunner()
    result = runner.invoke(main_cli, ["--help"])
    assert result.exit_code == 0
    assert "--gpu" in result.output or "--no-gpu" in result.output
    assert "--render-workers" in result.output
    assert "--preset" in result.output
