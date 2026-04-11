import src.cli as cli_module


def test_cli_console_uses_lazy_runner(monkeypatch):
    seen = {}

    def fake_run(args):
        seen["root"] = args.root
        seen["screen"] = args.screen
        return 0

    monkeypatch.setattr(cli_module, "_run_console_command", fake_run)

    exit_code = cli_module.main(["console", "--root", "/tmp/repo", "--screen", "quick"])

    assert exit_code == 0
    assert seen == {"root": "/tmp/repo", "screen": "quick"}
