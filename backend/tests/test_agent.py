import asyncio
import os

os.environ.setdefault("GEMINI_API_KEY", "test")

from koe import agent  # noqa: E402


def test_declarations_expose_every_registered_tool_with_a_json_schema():
    decls = {d["name"]: d for d in agent.declarations()}
    assert set(decls) == set(agent.TOOLS)
    for d in decls.values():
        assert d["description"]
        assert d["parameters_json_schema"]["type"] == "object"


def test_unknown_tool_returns_error_instead_of_raising():
    result = asyncio.run(agent.run_tool("merge_pr", {}))
    assert result["error"]["code"] == "unknown_tool"


def test_wrong_arguments_return_error_instead_of_raising():
    result = asyncio.run(agent.run_tool("github_my_prs", {"colour": "blue"}))
    assert result["error"]["code"] == "bad_args"


def test_crashing_tool_returns_error_instead_of_raising(monkeypatch):
    async def boom(**_):
        raise RuntimeError("network down")

    monkeypatch.setitem(agent.TOOLS, "github_my_prs", agent.TOOLS["github_my_prs"]._replace(fn=boom))
    result = asyncio.run(agent.run_tool("github_my_prs", {}))
    assert result["error"] == {"code": "tool_failed", "message": "network down", "hint": "Tell the user it failed; don't guess."}


def test_write_tool_never_runs_without_the_approval_gate(monkeypatch):
    ran = []

    async def write(**_):
        ran.append(True)
        return {"ok": True}

    monkeypatch.setitem(agent.TOOLS, "danger", agent.Tool(write, "writes things", {"type": "object"}, needs_approval=True))
    result = asyncio.run(agent.run_tool("danger", {}))
    assert ran == [] and result["error"]["code"] == "approval_required"


def test_no_merge_tool_exists():
    assert not any("merge" in name for name in agent.TOOLS)  # SPEC §3: the agent can't merge PRs


def test_phase4_tool_count_and_write_policy():
    assert {'github_activity', 'github_contributions'} <= set(agent.TOOLS)
    assert not agent.TOOLS['github_activity'].needs_approval
    assert not agent.TOOLS['github_contributions'].needs_approval
    assert {name for name, t in agent.TOOLS.items() if t.needs_approval} == {
        'calendar_upsert_event', 'github_comment', 'sheets_log_hours', 'notion_save', 'notion_archive', 'sheets_add_columns', 'sheets_update_row'}
