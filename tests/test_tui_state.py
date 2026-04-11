from src.tui.state import SessionState


def test_session_state_switches_workspace_and_target():
    session = SessionState()
    session.set_workspace("/tmp/repo", initialized=True, agent_profile="default")
    session.set_target("folder", folder="/tmp/repo/pkg")

    assert session.active_workspace_root == "/tmp/repo"
    assert session.selected_agent_profile == "default"
    assert session.selected_target.scope == "folder"
    assert session.selected_target.folder == "/tmp/repo/pkg"


def test_session_hints_reflect_failures_and_profile():
    session = SessionState()
    session.set_workspace("/tmp/repo", initialized=True, agent_profile="budget")
    session.last_run_summary = {"returncode": 1}

    hints = session.hints()

    assert any("Tests failed" == hint.title for hint in hints)
    assert any("budget" in hint.body for hint in hints)

