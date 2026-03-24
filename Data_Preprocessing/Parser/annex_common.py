import re
from typing import Any, Dict, List, Optional

RE_ANNEX_TABLE = re.compile(
    r"별표\s*(\d+)(?:\s*의\s*(\d+))?"
)


def normalize_annex_label(main_no: str, sub_no: Optional[str] = None) -> str:
    if sub_no:
        return f"별표 {main_no}의{sub_no}"
    return f"별표 {main_no}"


def extract_annex_references(text: str) -> List[Dict]:
    if not text:
        return []

    results = []
    seen = set()

    for m in RE_ANNEX_TABLE.finditer(text):
        main_no = m.group(1)
        sub_no = m.group(2)
        raw = m.group(0)

        label = normalize_annex_label(main_no, sub_no)

        if label in seen:
            continue
        seen.add(label)

        results.append({
            "label": label,
            "raw": raw
        })

    return results


def attach_annex_references_to_tree(node: Any) -> None:
    if isinstance(node, dict):
        text = node.get("text", "") or ""
        node["annex_references"] = extract_annex_references(text)

        children = node.get("children", [])
        if isinstance(children, list):
            for child in children:
                attach_annex_references_to_tree(child)

    elif isinstance(node, list):
        for item in node:
            attach_annex_references_to_tree(item)