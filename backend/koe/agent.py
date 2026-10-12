"""Agent core shared by every channel (web call now; WhatsApp and evals later):
the persona prompt and the tool registry (SPEC §3).

Every tool returns a JSON-able dict. Failures never raise: they come back as
{"error": {"code", "message", "hint"}} so the model can tell the user instead of guessing.
"""
from typing import Awaitable, Callable, NamedTuple

from koe.tools import github

SYSTEM_PROMPT = (
    "You are Koe (声, 'voice'), a warm, upbeat voice assistant for Rohit, a developer founder "
    "in India (timezone Asia/Kolkata). This is a live voice call: answer in one to three short "
    "spoken sentences, no lists, markdown or URLs. "
    "You can check Rohit's GitHub with your tools. Before calling a tool, say a few words like "
    "'let me check'. Summarize results; don't read out every field. Never invent PRs, numbers or "
    "statuses: if a tool returns an error, say what failed. Calendar and Notion aren't connected yet."
)


class Tool(NamedTuple):
    fn: Callable[..., Awaitable[dict]]
    description: str
    parameters: dict  # JSON Schema for the arguments
    needs_approval: bool = False  # write tools: must go through the approval gate (SPEC §5)


TOOLS: dict[str, Tool] = {
    "github_review_queue": Tool(
        github.github_review_queue,
        "List open pull requests where Rohit's review is requested: repo, number, title, author, age, size.",
        {"type": "object", "properties": {
            "repo": {"type": "string", "description": "Optional 'owner/name' to look in one repository only."},
        }},
    ),
    "github_my_prs": Tool(
        github.github_my_prs,
        "List Rohit's own pull requests with CI status, review state and merge conflicts.",
        {"type": "object", "properties": {
            "state": {"type": "string", "enum": ["open", "closed", "merged", "all"],
                      "description": "Which PRs; default 'open'."},
        }},
    ),
}


def _error(code: str, message: str, hint: str) -> dict:
    return {"error": {"code": code, "message": message, "hint": hint}}


def declarations() -> list[dict]:
    """Function declarations in the shape Gemini expects (JSON Schema parameters)."""
    return [{"name": name, "description": t.description, "parameters_json_schema": t.parameters}
            for name, t in TOOLS.items()]


async def run_tool(name: str, args: dict | None) -> dict:
    tool = TOOLS.get(name)
    if tool is None:
        return _error("unknown_tool", f"No tool named {name!r}.", f"Available: {', '.join(TOOLS)}.")
    if tool.needs_approval:
        # Fail closed: write tools only run through the approval gate, which doesn't exist yet.
        return _error("approval_required", f"{name} needs the user's approval first.", "Ask the user to confirm.")
    try:
        return await tool.fn(**(args or {}))
    except TypeError as e:  # the model passed arguments the tool doesn't take
        return _error("bad_args", str(e), "Call the tool again with only its documented arguments.")
    except Exception as e:
        return _error("tool_failed", str(e), "Tell the user it failed; don't guess.")
