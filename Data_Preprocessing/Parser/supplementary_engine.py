import re

# --------------------------------------------------
# 패턴
# --------------------------------------------------
RE_SUPPLEMENTARY_HEADER = re.compile(
    r"^\s*부칙(?:\s*(<[^>]*>))?(?:\s*\(([^)]*)\))?\s*$"
)

RE_ARTICLE = re.compile(
    r"^\s*(제\s*\d+\s*조(?:\s*의\s*\d+)?(?:\s*\([^)]*\))?)\s*(.*)$"
)

RE_PARAGRAPH = re.compile(
    r"^\s*([①②③④⑤⑥⑦⑧⑨⑩])\s*(.*)$"
)

RE_RANGE_OMISSION = re.compile(
    r"^\s*(제\s*\d+\s*조\s*부터\s*제\s*\d+\s*조\s*까지)\s*(생략)\s*$"
)

RE_ANGLE_ONLY = re.compile(r"^\s*<[^>]*>\s*$")
RE_PAREN_ONLY = re.compile(r"^\s*\([^)]*\)\s*$")

CIRCLED = {
    "①": 1, "②": 2, "③": 3, "④": 4, "⑤": 5,
    "⑥": 6, "⑦": 7, "⑧": 8, "⑨": 9, "⑩": 10
}

# --------------------------------------------------
# util
# --------------------------------------------------
def norm(s):
    return re.sub(r"\s+", " ", s).strip()

def is_supplementary_header(line: str) -> bool:
    return RE_SUPPLEMENTARY_HEADER.match(norm(line)) is not None

def new_article(label, page):
    return {
        "level": "article",
        "label": label,
        "page": page,
        "text": "",
        "notes": [],
        "children": [],
        "auto_created": False
    }

def new_paragraph(label, page):
    return {
        "level": "paragraph",
        "label": label,
        "page": page,
        "text": "",
        "notes": [],
        "children": [],
        "auto_created": False
    }

# --------------------------------------------------
# 부칙 그룹 분리
# --------------------------------------------------
def split_supplementary(lines):
    groups = []
    current = None
    i = 0

    while i < len(lines):
        page, line = lines[i]
        line = norm(line)

        m = RE_SUPPLEMENTARY_HEADER.match(line)
        if m:
            current = {
                "page": page,
                "promulgation_note": norm(m.group(1) or ""),
                "title": norm(m.group(2) or ""),
                "lines": []
            }
            groups.append(current)

            if i + 1 < len(lines):
                _, nxt = lines[i + 1]
                nxt = norm(nxt)
                if not current["promulgation_note"] and RE_ANGLE_ONLY.match(nxt):
                    current["promulgation_note"] = nxt
                    i += 1

            if i + 1 < len(lines):
                _, nxt = lines[i + 1]
                nxt = norm(nxt)
                if not current["title"] and RE_PAREN_ONLY.match(nxt):
                    current["title"] = nxt[1:-1].strip()
                    i += 1

            i += 1
            continue

        if current is not None:
            current["lines"].append((page, line))

        i += 1

    return groups

# --------------------------------------------------
# 부칙 1개 파싱
# --------------------------------------------------
def parse_supplementary_group(group):
    result = {
        "type": "부칙",
        "label": "부칙",
        "page": group["page"],
        "promulgation_note": group["promulgation_note"],
        "title": group["title"],
        "notes": [],
        "articles": []
    }

    current_article = None
    current_paragraph = None

    for page, line in group["lines"]:
        if not line:
            continue

        m = RE_RANGE_OMISSION.match(line)
        if m:
            result["articles"].append({
                "level": "range_omission",
                "label": norm(m.group(1)),
                "page": page,
                "text": norm(m.group(2)),
                "notes": [],
                "children": [],
                "auto_created": False
            })
            current_article = None
            current_paragraph = None
            continue

        m = RE_ARTICLE.match(line)
        if m:
            current_article = new_article(norm(m.group(1)), page)
            result["articles"].append(current_article)

            rest = norm(m.group(2))
            if rest:
                current_article["text"] = rest

            current_paragraph = None
            continue

        m = RE_PARAGRAPH.match(line)
        if m and current_article:
            no = CIRCLED.get(m.group(1))
            label = f"제{no}항"

            current_paragraph = new_paragraph(label, page)
            current_article["children"].append(current_paragraph)
            current_paragraph["text"] = norm(m.group(2))
            continue

        if current_paragraph:
            current_paragraph["text"] = norm(current_paragraph["text"] + " " + line)
        elif current_article:
            current_article["text"] = norm(current_article["text"] + " " + line)
        else:
            result["notes"].append(line)

    return result

# --------------------------------------------------
# 전체 부칙 파싱
# --------------------------------------------------
def parse_supplementary(lines):
    groups = split_supplementary(lines)
    return [parse_supplementary_group(g) for g in groups]