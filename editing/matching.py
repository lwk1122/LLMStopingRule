"""Exact editor with an optional, pinned Aider matcher on permitted excerpts."""
import ast
import copy
import re
from pathlib import Path

from .exact import apply_edits, source

VENDOR = Path(__file__).with_name("vendor") / "editblock_coder.py"
FUNCTIONS = {"prep", "perfect_or_whitespace", "perfect_replace",
             "replace_most_similar_chunk", "try_dotdotdots",
             "replace_part_with_missing_leading_whitespace", "match_but_for_leading_whitespace"}
tree = ast.parse(VENDOR.read_text())
nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in FUNCTIONS]
assert {node.name for node in nodes} == FUNCTIONS
namespace = {"re": re}
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(VENDOR), "exec"), namespace)
MATCH = namespace["replace_most_similar_chunk"]


def apply_with_fallback(parts, args):
    try:
        return apply_edits(parts, args)
    except ValueError as original_error:
        if str(original_error) not in {"old_text must occur exactly once in CURRENT source",
                                       "Replacement must be inside one displayed excerpt"}:
            raise
    updated = copy.deepcopy(parts)
    for edit in args["replacements"]:
        if not isinstance(edit, dict) or set(edit) != {"old_text", "new_text"}:
            raise ValueError("Each replacement needs old_text and new_text")
        old, new = edit["old_text"], edit["new_text"]
        if not isinstance(old, str) or not isinstance(new, str) or not old.strip():
            raise ValueError("Nonblank search text required")
        if source(updated).count(old) > 1:
            raise ValueError("Ambiguous exact search text")
        exact = [i for i, part in enumerate(updated) if part["editable"] and old in part["text"]]
        if len(exact) == 1:
            i = exact[0]
            updated[i]["text"] = updated[i]["text"].replace(old, new, 1)
            continue
        candidates = [(i, MATCH(part["text"], old, new))
                      for i, part in enumerate(updated) if part["editable"]]
        candidates = [(i, value) for i, value in candidates if value is not None]
        if len(candidates) != 1:
            raise ValueError("Aider matcher needs exactly one editable excerpt target")
        i, value = candidates[0]
        updated[i]["text"] = value
    compile(source(updated), "proposal.py", "exec")
    return updated
