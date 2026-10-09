"""Atomic exact replacements against currently displayed source excerpts."""
from __future__ import annotations

import copy
import difflib
import json

SYSTEM = """Repair the Python issue in the CURRENT source excerpts.
Return exactly one edit_source tool call. Choose action='edit' with exact
old_text/new_text replacements, or action='keep' with replacements=[] to preserve
the current source. Empty replacements NEVER restore the original code.
Copy old_text exactly from a displayed excerpt, including indentation. It must
occur exactly once in the current file and fit inside one displayed excerpt.
Edits are incremental: apply each replacement in order to CURRENT code. Preserve
previous corrections unless you identify a specific defect in them. Do not add
line numbers, change tests, or claim to have executed anything. The orchestrator
compiles source and runs checks. Visible passes do not prove complete correctness.
Use keep when no concrete correction is needed; do not rewrite correct code."""

TOOL = {"type": "function", "function": {"name": "edit_source",
    "description": "Edit exact current source text, or keep the current version.",
    "parameters": {"type": "object", "properties": {
        "action": {"type": "string", "enum": ["edit", "keep"]},
        "replacements": {"type": "array", "items": {"type": "object", "properties": {
            "old_text": {"type": "string"}, "new_text": {"type": "string"}},
            "required": ["old_text", "new_text"], "additionalProperties": False}}},
        "required": ["action", "replacements"], "additionalProperties": False}}}


def initial_state(inputs: dict) -> list[dict]:
    lines = inputs["source"].splitlines(keepends=True)
    parts, cursor = [], 0
    for start, end in inputs["ranges"]:
        if start-1 > cursor:
            parts.append({"editable": False, "text": "".join(lines[cursor:start-1])})
        parts.append({"editable": True, "text": "".join(lines[start-1:end])})
        cursor = end
    parts.append({"editable": False, "text": "".join(lines[cursor:])})
    assert source(parts) == inputs["source"]
    return parts


def source(parts: list[dict]) -> str:
    return "".join(p["text"] for p in parts)


def displayed(parts: list[dict]) -> str:
    return "\n\n".join(f"CURRENT EXCERPT {i}:\n```python\n{p['text']}\n```"
                         for i, p in enumerate(parts) if p["editable"])


def apply_edits(parts: list[dict], args: dict) -> list[dict]:
    if not isinstance(args, dict) or set(args) != {"action", "replacements"}:
        raise ValueError("Expected action and replacements")
    edits = args["replacements"]
    if not isinstance(edits, list):
        raise ValueError("replacements must be an array")
    if args["action"] == "keep":
        if edits:
            raise ValueError("keep requires no replacements")
        return copy.deepcopy(parts)
    if args["action"] != "edit" or not edits:
        raise ValueError("edit requires at least one replacement")
    updated = copy.deepcopy(parts)
    for edit in edits:
        if not isinstance(edit, dict) or set(edit) != {"old_text", "new_text"}:
            raise ValueError("Each replacement needs old_text and new_text")
        old, new = edit["old_text"], edit["new_text"]
        if not isinstance(old, str) or not isinstance(new, str) or not old:
            raise ValueError("old_text must be nonempty text and new_text must be text")
        if source(updated).count(old) != 1:
            raise ValueError("old_text must occur exactly once in CURRENT source")
        matches = [i for i,p in enumerate(updated) if p["editable"] and old in p["text"]]
        if len(matches) != 1:
            raise ValueError("Replacement must be inside one displayed excerpt")
        i = matches[0]
        updated[i]["text"] = updated[i]["text"].replace(old, new, 1)
    compile(source(updated), "proposal.py", "exec")
    return updated


def proposal(response: dict, parts: list[dict]) -> tuple[list[dict], dict]:
    calls = response["choices"][0]["message"].get("tool_calls") or []
    if len(calls) != 1 or calls[0]["function"]["name"] != "edit_source":
        raise ValueError("Expected exactly one edit_source call")
    args = json.loads(calls[0]["function"]["arguments"])
    return apply_edits(parts, args), args


def patch(inputs: dict, parts: list[dict]) -> str:
    return "".join(difflib.unified_diff(inputs["source"].splitlines(keepends=True),
        source(parts).splitlines(keepends=True), fromfile="a/"+inputs["path"], tofile="b/"+inputs["path"]))
