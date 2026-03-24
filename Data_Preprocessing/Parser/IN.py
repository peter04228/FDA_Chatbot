import os
import re
import json
from datetime import datetime

from structure_engine import (
    extract_lines,
    preprocess_lines,
    parse_main,
    repair_split_notes_in_tree,
    prune_empty_auto_nodes,
    summarize_warnings,
)

from supplementary_engine import (
    parse_supplementary,
    is_supplementary_header,
)

from entity_common import (
    extract_common_document_entity,
)

INPUT_DIR = r"C:\dev\FDA_Chatbot\DATA\o_data\행정규칙\예규"
OUT_DIR = r"C:\dev\FDA_Chatbot\DATA\parser_data\IN"
os.makedirs(OUT_DIR, exist_ok=True)


def build_in_metadata(file_name, source_path):
    return {
        "document_group": None,
        "document_type_code": "IN",
        "document_type_name_ko": "예규",
        "document_type_name_en": "Instruction",
        "file_name": file_name,
        "source_path": source_path,
        "processed_at": datetime.now().isoformat(timespec="seconds")
    }


KNOWN_LAW_PATTERNS = [
    (
        re.compile(r"식품\s*ㆍ\s*의약품분야\s*시험\s*ㆍ\s*검사\s*등에\s*관한\s*법률"),
        "식품ㆍ의약품분야 시험ㆍ검사 등에 관한 법률",
    ),
    (
        re.compile(r"의약품\s*등의\s*안\s*전\s*에\s*관한\s*규칙"),
        "의약품 등의 안전에 관한 규칙",
    ),
    (
        re.compile(r"마약류\s*관리\s*에\s*관한\s*법률"),
        "마약류 관리에 관한 법률",
    ),
    (
        re.compile(r"첨단재생의료\s*및\s*첨단바이오의약품\s*안전\s*및\s*지원\s*에\s*관한\s*법률"),
        "첨단재생의료 및 첨단바이오의약품 안전 및 지원에 관한 법률",
    ),
]


def normalize_known_law_names_in_text(text):
    if not isinstance(text, str) or not text:
        return text

    out = text
    for pattern, replacement in KNOWN_LAW_PATTERNS:
        out = pattern.sub(replacement, out)
    return out


def normalize_quoted_law_spans(text):
    if not isinstance(text, str) or not text:
        return text

    def repl(m):
        inner = m.group(1)
        inner = re.sub(r"\s+", " ", inner).strip()
        inner = normalize_known_law_names_in_text(inner)
        return f"「{inner}」"

    return re.sub(r"「(.*?)」", repl, text, flags=re.DOTALL)


def merge_broken_quoted_law_lines(lines):
    merged = []
    i = 0

    while i < len(lines):
        page, line = lines[i]
        line = line.strip() if isinstance(line, str) else line

        if not line:
            i += 1
            continue

        if "「" in line and "」" not in line:
            combined = line
            j = i + 1
            found_close = False

            while j < len(lines):
                _, next_line = lines[j]
                next_line = next_line.strip() if isinstance(next_line, str) else next_line

                if next_line:
                    combined += next_line

                if isinstance(next_line, str) and "」" in next_line:
                    found_close = True
                    break

                j += 1

            if found_close:
                combined = normalize_quoted_law_spans(combined)
                combined = normalize_known_law_names_in_text(combined)
                merged.append((page, combined))
                i = j + 1
                continue

        line = normalize_quoted_law_spans(line)
        line = normalize_known_law_names_in_text(line)
        merged.append((page, line))
        i += 1

    return merged


def normalize_tree_texts(nodes):
    if not isinstance(nodes, list):
        return

    for node in nodes:
        if not isinstance(node, dict):
            continue

        if isinstance(node.get("label"), str):
            node["label"] = normalize_quoted_law_spans(node["label"])
            node["label"] = normalize_known_law_names_in_text(node["label"])

        if isinstance(node.get("text"), str):
            node["text"] = normalize_quoted_law_spans(node["text"])
            node["text"] = normalize_known_law_names_in_text(node["text"])

        notes = node.get("notes")
        if isinstance(notes, list):
            new_notes = []
            for note in notes:
                if isinstance(note, str):
                    note = normalize_quoted_law_spans(note)
                    note = normalize_known_law_names_in_text(note)
                new_notes.append(note)
            node["notes"] = new_notes

        children = node.get("children")
        if isinstance(children, list):
            normalize_tree_texts(children)


def normalize_supplementary_texts(supplementary):
    if not isinstance(supplementary, list):
        return

    for block in supplementary:
        if not isinstance(block, dict):
            continue

        if isinstance(block.get("label"), str):
            block["label"] = normalize_quoted_law_spans(block["label"])
            block["label"] = normalize_known_law_names_in_text(block["label"])

        if isinstance(block.get("title"), str):
            block["title"] = normalize_quoted_law_spans(block["title"])
            block["title"] = normalize_known_law_names_in_text(block["title"])

        if isinstance(block.get("promulgation_note"), str):
            block["promulgation_note"] = normalize_quoted_law_spans(block["promulgation_note"])
            block["promulgation_note"] = normalize_known_law_names_in_text(block["promulgation_note"])

        notes = block.get("notes")
        if isinstance(notes, list):
            new_notes = []
            for note in notes:
                if isinstance(note, str):
                    note = normalize_quoted_law_spans(note)
                    note = normalize_known_law_names_in_text(note)
                new_notes.append(note)
            block["notes"] = new_notes

        articles = block.get("articles")
        if isinstance(articles, list):
            normalize_tree_texts(articles)


RE_SINGLE_REF = re.compile(
    r"제(?P<article>\d+)조"
    r"(?:의(?P<article_sub>\d+))?"
    r"(?:제(?P<paragraph>\d+)항)?"
    r"(?:제(?P<item>\d+)호)?"
    r"(?:제(?P<subitem>\d+)목)?"
)


def parse_single_ref(ref_text, law_name):
    ref_text = ref_text.strip()
    m = RE_SINGLE_REF.fullmatch(ref_text)

    if not m:
        return {
            "type": "single",
            "law_name": law_name,
            "raw": ref_text,
        }

    out = {
        "type": "single",
        "law_name": law_name,
        "raw": ref_text,
        "article": f"제{m.group('article')}조",
    }

    if m.group("article_sub"):
        out["article_sub"] = f"의{m.group('article_sub')}"
    if m.group("paragraph"):
        out["paragraph"] = f"제{m.group('paragraph')}항"
    if m.group("item"):
        out["item"] = f"제{m.group('item')}호"
    if m.group("subitem"):
        out["subitem"] = f"제{m.group('subitem')}목"

    return out


def extract_only_er_reference(article_text):
    if not isinstance(article_text, str) or not article_text.strip():
        return []

    text = normalize_quoted_law_spans(article_text)
    text = normalize_known_law_names_in_text(text)

    target_law = "의약품 등의 안전에 관한 규칙"

    pattern = re.compile(
        r"「의약품 등의 안전에 관한 규칙」\s*"
        r"(?P<ref>제\d+조(?:의\d+)?(?:제\d+항)?(?:제\d+호)?(?:제\d+목)?)"
    )

    m = pattern.search(text)
    if not m:
        return []

    ref_text = m.group("ref").strip()
    item = parse_single_ref(ref_text, target_law)
    item["source_style"] = "quoted"
    return [item]


def split_main_and_supplementary_lines(lines):
    main_lines = []
    supp_lines = []

    in_supplementary = False

    for page, line in lines:
        if not in_supplementary and is_supplementary_header(line):
            in_supplementary = True

        if in_supplementary:
            supp_lines.append((page, line))
        else:
            main_lines.append((page, line))

    return main_lines, supp_lines


def process_one_pdf(pdf_path):
    file_name = os.path.basename(pdf_path)

    lines = extract_lines(pdf_path)
    lines = merge_broken_quoted_law_lines(lines)
    lines = preprocess_lines(lines)

    normalized_lines = []
    for p, t in lines:
        if isinstance(t, str):
            t = normalize_quoted_law_spans(t)
            t = normalize_known_law_names_in_text(t)
        normalized_lines.append((p, t))
    lines = normalized_lines

    main_lines, supp_lines = split_main_and_supplementary_lines(lines)

    main_tree, main_warnings = parse_main(main_lines)
    repair_split_notes_in_tree(main_tree)
    prune_empty_auto_nodes(main_tree)
    normalize_tree_texts(main_tree)

    supplementary = parse_supplementary(supp_lines) if supp_lines else []
    normalize_supplementary_texts(supplementary)

    entity_payload = extract_common_document_entity(
        file_name=file_name,
        source_path=pdf_path,
        document_type="예규",
        main_tree=main_tree,
        supplementary=supplementary,
    )

    if isinstance(entity_payload.get("title"), str):
        entity_payload["title"] = normalize_known_law_names_in_text(
            normalize_quoted_law_spans(entity_payload["title"])
        )

    purpose_link = entity_payload.get("purpose_link")
    if isinstance(purpose_link, dict):
        if isinstance(purpose_link.get("article_label"), str):
            purpose_link["article_label"] = normalize_known_law_names_in_text(
                normalize_quoted_law_spans(purpose_link["article_label"])
            )
        if isinstance(purpose_link.get("article_text"), str):
            article_text = normalize_known_law_names_in_text(
                normalize_quoted_law_spans(purpose_link["article_text"])
            )
            purpose_link["article_text"] = article_text
            purpose_link["rule_references"] = extract_only_er_reference(article_text)

    warnings = main_warnings
    warning_summary = summarize_warnings(warnings)
    metadata = build_in_metadata(file_name, pdf_path)

    result = {
        **metadata,
        "title": entity_payload.get("title"),
        "issuing_body": entity_payload.get("issuing_body"),
        "document_no": entity_payload.get("document_no"),
        "effective_date": entity_payload.get("effective_date"),
        "document_entity": entity_payload.get("document_entity"),
        "purpose_link": entity_payload.get("purpose_link"),
        "main_tree": main_tree,
        "supplementary": supplementary,
        "warnings": warnings,
        "warning_summary": warning_summary,
    }

    out_path = os.path.join(
        OUT_DIR,
        os.path.splitext(file_name)[0] + ".in.struct.json"
    )

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("saved:", out_path, f"(warnings={len(warnings)})", warning_summary)


def process_all():
    pdfs = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith(".pdf")]

    if not pdfs:
        print("no pdf:", INPUT_DIR)
        return

    pdfs.sort()

    print(f"[IN parsing start] total={len(pdfs)}")

    for fn in pdfs:
        try:
            process_one_pdf(os.path.join(INPUT_DIR, fn))
        except Exception as e:
            print("[ERROR]", fn, e)

    print("[IN parsing done]")


if __name__ == "__main__":
    process_all()