import os
import re
import json
from datetime import datetime

from structure_engine import (
    extract_lines,
    preprocess_lines,
)

# --------------------------------------------------
# 경로 설정
# --------------------------------------------------
INPUT_DIR = r"C:\dev\FDA_Chatbot\DATA\o_data\시행규칙\별표"
OUT_DIR = r"C:\dev\FDA_Chatbot\DATA\parser_data\ER_ANNEX"
os.makedirs(OUT_DIR, exist_ok=True)


# --------------------------------------------------
# 기본 유틸
# --------------------------------------------------
def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def normalize_branch_label(text: str) -> str:
    s = (text or "").strip()
    s = re.sub(r"\s+", "", s)
    return s


def split_angle_notes(text: str):
    notes = re.findall(r"<[^>]+>", text or "")
    clean = re.sub(r"<[^>]+>", "", text or "").strip()
    return clean, notes


def make_node(level, label, page, text="", notes=None, auto_created=False):
    return {
        "level": level,
        "label": label,
        "page": page,
        "text": text.strip(),
        "notes": notes or [],
        "children": [],
        "auto_created": auto_created
    }


def append_text(node, line):
    line = (line or "").strip()
    if not line:
        return
    if node["text"]:
        node["text"] += " " + line
    else:
        node["text"] = line


# --------------------------------------------------
# 별표 헤더
# --------------------------------------------------
RE_ANNEX_HEADER = re.compile(
    r"""^\s*
    [■□]?\s*
    .*?
    \[
      \s*(별표\s*\d+(?:\s*의\s*\d+)?)\s*
    \]
    \s*(<[^>]+>)?\s*$
    """,
    re.VERBOSE
)


def normalize_annex_label(raw_label: str) -> str:
    m = re.match(r"별표\s*(\d+)(?:\s*의\s*(\d+))?", raw_label or "")
    if not m:
        return normalize_space(raw_label)
    main_no = m.group(1)
    sub_no = m.group(2)
    if sub_no:
        return f"별표 {main_no}의{sub_no}"
    return f"별표 {main_no}"


def is_annex_header(line: str) -> bool:
    return bool(RE_ANNEX_HEADER.match(line or ""))


def parse_annex_header(line: str):
    m = RE_ANNEX_HEADER.match(line or "")
    if not m:
        return None

    raw_label = m.group(1)
    raw_note = m.group(2) or ""

    notes = []
    if raw_note:
        notes.append(raw_note.strip())

    return {
        "raw_label": raw_label.strip(),
        "label": normalize_annex_label(raw_label),
        "notes": notes,
        "raw_header": (line or "").strip()
    }


# --------------------------------------------------
# 별표 내부 구조 패턴
# --------------------------------------------------

# Ⅰ / Ⅱ / Ⅲ ...
RE_ROMAN = re.compile(
    r"^\s*([ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ]+)[\.\)]?\s*(.*)$"
)

# 1.1 목적 / 1.2.1 세부사항
RE_DECIMAL = re.compile(
    r"^\s*((?:\d+\.)+\d+)\s+(.*)$"
)

# 1. 개요 / 1의2. 기준
RE_ITEM_DOT = re.compile(
    r"^\s*(\d+(?:\s*의\s*\d+)*)\.\s*(.*)$"
)

# 가. 기준 / 가의2. 기준
RE_KOREAN_DOT = re.compile(
    r"^\s*([가-하](?:\s*의\s*\d+)*)\.\s*(.*)$"
)

# 1) 내용 / 1의2) 내용
RE_NUM_PAREN_CLOSE = re.compile(
    r"^\s*(\d+(?:\s*의\s*\d+)*)\)\s*(.*)$"
)

# 가) 내용 / 가의2) 내용
RE_KOR_PAREN_CLOSE = re.compile(
    r"^\s*([가-하](?:\s*의\s*\d+)*)\)\s*(.*)$"
)

# ① 내용
RE_CIRCLED = re.compile(
    r"^\s*([①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳])\s*(.*)$"
)

# (1) 내용
RE_PAREN_NUM = re.compile(
    r"^\s*\((\d+)\)\s*(.*)$"
)


def get_decimal_depth(label: str) -> int:
    return len((label or "").split("."))


def get_node_rank(level: str, label: str) -> int:
    if level == "roman":
        return 1
    if level == "item":
        return 2
    if level == "decimal":
        return 10 + get_decimal_depth(label)
    if level == "subitem":
        return 30
    if level == "subsubitem":
        return 40
    if level == "detail":
        return 50
    if level == "paren_num":
        return 60
    return 999


def classify_annex_line(line: str):
    """
    우선순위 중요:
      roman
      > decimal
      > korean_dot
      > num_paren_close
      > kor_paren_close
      > item_dot
      > circled
      > paren_num

    이유:
    - 가. 아래 1) 구조를 먼저 잡아야 함
    - 1) 가 1. 로 오인식되면 안 됨
    """
    s = (line or "").strip()
    if not s:
        return None

    # Ⅰ
    m = RE_ROMAN.match(s)
    if m:
        label = normalize_branch_label(m.group(1))
        rest = m.group(2).strip()
        return ("roman", label, rest)

    # 1.1 / 1.2.1
    m = RE_DECIMAL.match(s)
    if m:
        label = normalize_branch_label(m.group(1))
        rest = m.group(2).strip()
        if not rest:
            return None
        return ("decimal", label, rest)

    # 가. / 가의2.
    m = RE_KOREAN_DOT.match(s)
    if m:
        label = normalize_branch_label(m.group(1))
        rest = m.group(2).strip()
        if not rest:
            return None
        return ("subitem", f"{label}.", rest)

    # 1) / 1의2)
    m = RE_NUM_PAREN_CLOSE.match(s)
    if m:
        label = normalize_branch_label(m.group(1))
        rest = m.group(2).strip()
        if not rest:
            return None
        return ("subsubitem", f"{label})", rest)

    # 가) / 가의2)
    m = RE_KOR_PAREN_CLOSE.match(s)
    if m:
        label = normalize_branch_label(m.group(1))
        rest = m.group(2).strip()
        if not rest:
            return None
        return ("detail", f"{label})", rest)

    # 1. / 1의2.
    m = RE_ITEM_DOT.match(s)
    if m:
        label = normalize_branch_label(m.group(1))
        rest = m.group(2).strip()
        if not rest:
            return None
        return ("item", f"{label}.", rest)

    # ①
    m = RE_CIRCLED.match(s)
    if m:
        label = normalize_branch_label(m.group(1))
        rest = m.group(2).strip()
        if not rest:
            return None
        return ("detail", label, rest)

    # (1)
    m = RE_PAREN_NUM.match(s)
    if m:
        label = f"({normalize_branch_label(m.group(1))})"
        rest = m.group(2).strip()
        if not rest:
            return None
        return ("paren_num", label, rest)

    return None


# --------------------------------------------------
# 별표 블록 분리
# --------------------------------------------------
def split_annex_blocks(lines):
    blocks = []
    current = []

    for page, line in lines:
        if is_annex_header(line):
            if current:
                blocks.append(current)
            current = [(page, line)]
        else:
            if current:
                current.append((page, line))

    if current:
        blocks.append(current)

    return blocks


# --------------------------------------------------
# 제목 추출
# --------------------------------------------------
def extract_title_and_body(block_lines):
    if len(block_lines) <= 1:
        return "", None, []

    title = ""
    title_page = None
    body_start_idx = 1

    for i in range(1, len(block_lines)):
        page, line = block_lines[i]
        s = normalize_space(line)

        if not s:
            continue

        clean, notes = split_angle_notes(s)
        if not clean and notes:
            continue

        title = clean
        title_page = page
        body_start_idx = i + 1
        break

    body_lines = block_lines[body_start_idx:] if body_start_idx < len(block_lines) else []
    return title, title_page, body_lines


# --------------------------------------------------
# 별표 본문 파싱
# --------------------------------------------------
def parse_annex_body(body_lines):
    tree = []
    stack = []
    intro_lines = []

    for page, raw_line in body_lines:
        line = normalize_space(raw_line)
        if not line:
            continue

        clean_line, inline_notes = split_angle_notes(line)
        parsed = classify_annex_line(clean_line)

        if parsed is None:
            if stack:
                append_text(stack[-1], clean_line)
                if inline_notes:
                    stack[-1]["notes"].extend(inline_notes)
            else:
                intro_lines.append(clean_line)
            continue

        level, label, rest = parsed
        new_node = make_node(
            level=level,
            label=label,
            page=page,
            text=rest,
            notes=inline_notes,
            auto_created=False,
        )

        new_rank = get_node_rank(level, label)

        while stack and get_node_rank(stack[-1]["level"], stack[-1]["label"]) >= new_rank:
            stack.pop()

        if stack:
            stack[-1]["children"].append(new_node)
        else:
            tree.append(new_node)

        stack.append(new_node)

    intro_text = " ".join(intro_lines).strip()

    return {
        "intro_text": intro_text,
        "tree": tree
    }


# --------------------------------------------------
# 단일 별표 block 파싱
# --------------------------------------------------
def parse_one_annex_block(block_lines):
    if not block_lines:
        return None

    header_page, header_line = block_lines[0]
    header_info = parse_annex_header(header_line)
    if not header_info:
        return None

    title, title_page, body_lines = extract_title_and_body(block_lines)
    parsed_body = parse_annex_body(body_lines)

    last_page = block_lines[-1][0]

    return {
        "label": header_info["label"],
        "raw_label": header_info["raw_label"],
        "raw_header": header_info["raw_header"],
        "header_notes": header_info["notes"],
        "title": title,
        "title_page": title_page,
        "page_start": header_page,
        "page_end": last_page,
        "intro_text": parsed_body["intro_text"],
        "body_tree": parsed_body["tree"]
    }


# --------------------------------------------------
# PDF 전체에서 별표 파싱
# --------------------------------------------------
def parse_annexes_from_pdf(pdf_path):
    lines = extract_lines(pdf_path)
    lines = preprocess_lines(lines)

    blocks = split_annex_blocks(lines)

    annexes = []
    for block in blocks:
        parsed = parse_one_annex_block(block)
        if parsed:
            annexes.append(parsed)

    return annexes


# --------------------------------------------------
# 메타
# --------------------------------------------------
def build_annex_metadata(file_name, source_path):
    return {
        "document_group": None,
        "document_type_code": "ER",
        "document_type_name_ko": "시행규칙",
        "document_type_name_en": "Enforcement Rules",
        "file_name": file_name,
        "source_path": source_path,
        "processed_at": now_iso()
    }


# --------------------------------------------------
# 단일 PDF 처리
# --------------------------------------------------
def process_one_pdf(pdf_path):
    file_name = os.path.basename(pdf_path)

    metadata = build_annex_metadata(file_name, pdf_path)
    annexes = parse_annexes_from_pdf(pdf_path)

    result = {
        **metadata,
        "annex_tables": annexes
    }

    out_path = os.path.join(
        OUT_DIR,
        os.path.splitext(file_name)[0] + ".er.annex.json"
    )

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"saved: {out_path} (annexes={len(annexes)})")


# --------------------------------------------------
# 전체 처리
# --------------------------------------------------
def process_all():
    pdfs = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith(".pdf")]

    if not pdfs:
        print("no pdf:", INPUT_DIR)
        return

    pdfs.sort()
    print(f"[ER annex parsing start] total={len(pdfs)}")

    for fn in pdfs:
        try:
            process_one_pdf(os.path.join(INPUT_DIR, fn))
        except Exception as e:
            print("[ERROR]", fn, e)

    print("[ER annex parsing done]")


# --------------------------------------------------
# 실행
# --------------------------------------------------
if __name__ == "__main__":
    process_all()