import re
from typing import List, Tuple, Optional


# --------------------------------------------------
# 기본 패턴
# --------------------------------------------------
RE_PART = re.compile(r"^\s*제\s*(\d+)\s*편\b")
RE_CHAPTER = re.compile(r"^\s*제\s*(\d+)\s*장\b")
RE_SECTION = re.compile(r"^\s*제\s*(\d+)\s*절\b")

RE_ARTICLE_HEADER = re.compile(
    r"^\s*(제\s*\d+\s*조(?:\s*의\s*\d+)?(?:\s*\([^)]*\))?)(?=\s|$|[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳<\[])\s*(.*)$"
)

RE_ARTICLE_BARE = re.compile(
    r"^\s*제\s*(\d+)\s*조(?:\s*의\s*(\d+))?\s*$"
)

RE_ARTICLE_INLINE_FINDER = re.compile(
    r"(제\s*\d+\s*조(?:\s*의\s*\d+)?(?:\s*\([^)]*\))?)(?=\s|$|[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳<\[])"
)

RE_PAR_CIRCLED = re.compile(
    r"^\s*([①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳])\s*(.*)$"
)
RE_PAR_TEXT = re.compile(r"^\s*(제\s*\d+\s*항)\b\s*(.*)$")

RE_ITEM = re.compile(r"^\s*(\d+)(?:\s*의\s*(\d+))?\s*[\.．]\s*(.+)$")

RE_SUBITEM = re.compile(r"^\s*(\([가-힣]\)|[가-힣][\.\)]|[가-힣]．)\s+(.+)$")
RE_SUBNUM_NUM = re.compile(r"^\s*(\d+)\)\s+(.+)$")
RE_SUBNUM_KOR = re.compile(r"^\s*([가나다라마바사아자차카타파하])\)\s+(.+)$")

RE_NOTE_ONLY = re.compile(r"^\s*(?:<[^>]*>?|\[[^\]]*\]?)\s*$")

CIRCLED_TO_NUM = {
    "①": 1, "②": 2, "③": 3, "④": 4, "⑤": 5,
    "⑥": 6, "⑦": 7, "⑧": 8, "⑨": 9, "⑩": 10,
    "⑪": 11, "⑫": 12, "⑬": 13, "⑭": 14, "⑮": 15,
    "⑯": 16, "⑰": 17, "⑱": 18, "⑲": 19, "⑳": 20,
}

ORDER = [
    "root", "part", "chapter", "section", "article",
    "paragraph", "item", "subitem", "subnum_num", "subnum_kor"
]
IDX = {k: i for i, k in enumerate(ORDER)}

PARENT = {
    "part": "root",
    "chapter": "part",
    "section": "chapter",
    "article": "section",
    "paragraph": "article",
    "item": "paragraph",
    "subitem": "item",
    "subnum_num": "subitem",
    "subnum_kor": "subnum_num",
}

KOR_SEQ = ["가", "나", "다", "라", "마", "바", "사", "아", "자", "차", "카", "타", "파", "하"]
KOR_IDX = {k: i for i, k in enumerate(KOR_SEQ)}

CONTINUATION_ENDINGS = {
    "및", "또는", "그", "다만", ":", ",",
    "의", "에", "에서", "에게", "으로", "로", "중",
    "같은", "해당", "다음", "다음 각"
}

NOTE_KEYWORDS = [
    "신설", "개정", "전문개정", "일부개정", "제목개정",
    "본조신설", "본항신설", "본호신설",
    "삭제", "이동", "종전", "에서 이동", "으로 이동"
]

POSTPOSITION_STARTS = (
    "에 따른", "에 따라", "에 의한", "에 의하여",
    "에", "의", "를", "을", "은", "는", "이", "가",
    "과", "와", "로", "으로", "부터", "까지", "중", "등",
    "및", "또는"
)

DEFAULT_NOISE_PATTERNS = [
    r"^\s*법제처\s*$",
    r"^\s*국가법령정보센터\s*$",
    r"^\s*\d+\s*$",
    r"^\s*법제처\s+\d+\s+국가법령정보센터.*$",
]


# --------------------------------------------------
# 기본 유틸
# --------------------------------------------------
def norm(s: str) -> str:
    s = s.replace("\u00A0", " ")
    s = s.replace("\ufeff", "")
    s = re.sub(r"[ \t]+", " ", s).strip()
    return s


def strip_right_spaces_only(s: str) -> str:
    return s.replace("\u00A0", " ").replace("\ufeff", "").rstrip("\r\n")


def compile_noise_patterns(noise_patterns: Optional[List[str]] = None):
    patterns = noise_patterns or DEFAULT_NOISE_PATTERNS
    return [re.compile(p) for p in patterns]


def is_noise_line(s: str, compiled_noise_patterns) -> bool:
    s2 = norm(s)
    return any(p.match(s2) for p in compiled_noise_patterns)


def new_node(level, label, page, auto=False):
    return {
        "level": level,
        "label": label,
        "page": page,
        "text": "",
        "notes": [],
        "children": [],
        "auto_created": auto,
    }


def starts_with_postposition(s: str) -> bool:
    s = norm(s)
    return any(s.startswith(x) for x in POSTPOSITION_STARTS)


def should_join_without_space(prev_text: str, new_text: str) -> bool:
    prev_text = prev_text.rstrip()
    new_text = new_text.lstrip()

    if not prev_text or not new_text:
        return False

    if re.search(r"제\s*\d+\s*조(?:\s*의\s*\d+)?$", prev_text) and starts_with_postposition(new_text):
        return True

    if re.search(r"제\s*\d+\s*(?:항|호)(?:\s*의\s*\d+)?$", prev_text) and starts_with_postposition(new_text):
        return True

    return False


def add_text(node, t: str):
    t = norm(t)
    if not t:
        return
    if not node["text"]:
        node["text"] = t
    else:
        if should_join_without_space(node["text"], t):
            node["text"] += t
        else:
            node["text"] += " " + t


def add_note(node, t: str):
    t = norm(t)
    if not t:
        return
    if t not in node["notes"]:
        node["notes"].append(t)


def attach_text_and_notes(node, text, notes):
    if text:
        add_text(node, text)
    for nt in notes:
        add_note(node, nt)


# --------------------------------------------------
# note / 줄복원 유틸
# --------------------------------------------------
def looks_like_date_tail_line(s: str) -> bool:
    s = norm(s)

    if re.match(r"^\d{1,4}\.\s*\d{1,2}\.\s*\d{1,2}\.?>?$", s):
        return True

    if re.match(r"^\d{1,2}\.\s*\d{1,2}\.?>?$", s):
        return True

    if re.match(
        r"^(?:\d{1,4}\.\s*\d{1,2}\.\s*\d{1,2}\.?\s*,\s*)+\d{1,4}\.\s*\d{1,2}\.\s*\d{1,2}\.?>?$",
        s
    ):
        return True

    if re.match(
        r"^\d{1,2}\.\s*\d{1,2}\.\s*,\s*\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.?>?$",
        s
    ):
        return True

    tmp = re.sub(r"\d{1,4}\.\s*\d{1,2}\.\s*\d{1,2}\.?", "", s)
    tmp = re.sub(r"\d{1,2}\.\s*\d{1,2}\.?", "", tmp)
    tmp = re.sub(r"[,\s>\]]+", "", tmp)
    if tmp == "" and ("," in s or s.endswith(">") or s.endswith("]")):
        return True

    return False


def looks_like_non_item_numeric_line(s: str) -> bool:
    s = norm(s)
    if looks_like_date_tail_line(s):
        return True
    if re.match(r"^\d+\.\d+\b", s):
        return True
    return False


def looks_like_note_tail_fragment(s: str) -> bool:
    s = norm(s)
    if not s:
        return False
    if looks_like_date_tail_line(s):
        return True
    if re.match(r"^[^<>\[\]]*[>\]]$", s):
        return True
    return False


def is_note_like_line(s: str) -> bool:
    s2 = norm(s)

    if not s2:
        return False

    if RE_NOTE_ONLY.match(s2):
        return True

    if looks_like_date_tail_line(s2):
        return True

    if re.match(r"^\[[^\]]*\]$", s2):
        return True

    if s2.startswith("[") and any(k in s2 for k in NOTE_KEYWORDS):
        return True

    if s2.startswith("<") and ">" in s2:
        if any(k in s2 for k in NOTE_KEYWORDS):
            return True

    if s2.startswith("<"):
        if any(k in s2 for k in NOTE_KEYWORDS):
            return True

    if re.match(r"^삭제\s*<[^>]+>$", s2):
        return True

    if any(k in s2 for k in ["종전", "이동"]):
        if "<" in s2 or "[" in s2 or ">" in s2 or "]" in s2:
            return True

    return False


def extract_inline_notes(line: str):
    s = line
    notes = []

    pattern = re.compile(r"<[^>]*>|\[[^\]]*\]")
    parts = []
    last = 0

    for m in pattern.finditer(s):
        chunk = m.group(0)
        chunk_n = norm(chunk)

        if is_note_like_line(chunk_n):
            if m.start() > last:
                parts.append(s[last:m.start()])
            notes.append(chunk_n)
            last = m.end()

    parts.append(s[last:])
    remaining = norm(" ".join(p for p in parts if p and norm(p)))

    loose_patterns = [
        r"삭제\s*<[^>]+>",
        r"종전\s+[^[]*?이동\s*<[^>]+>",
        r"제\d+조(?:의\d+)?에서 이동\s*<[^>]+>",
        r"\[[^\]]*(?:전문개정|일부개정|제목개정|본조신설|본항신설|본호신설|신설|개정)[^\]]*\]",
    ]

    for lp in loose_patterns:
        mm = re.search(lp, remaining)
        if mm:
            chunk = norm(mm.group(0))
            if is_note_like_line(chunk):
                notes.append(chunk)
                remaining = norm(remaining[:mm.start()] + " " + remaining[mm.end():])

    dangling_angle = re.search(r"<[^>]*$", remaining)
    if dangling_angle:
        chunk = norm(dangling_angle.group(0))
        if any(k in chunk for k in NOTE_KEYWORDS):
            notes.append(chunk)
            remaining = norm(remaining[:dangling_angle.start()])

    dangling_square = re.search(r"\[[^\]]*$", remaining)
    if dangling_square:
        chunk = norm(dangling_square.group(0))
        if any(k in chunk for k in NOTE_KEYWORDS):
            notes.append(chunk)
            remaining = norm(remaining[:dangling_square.start()])

    dedup = []
    seen = set()
    for n in notes:
        if n not in seen:
            seen.add(n)
            dedup.append(n)

    return remaining, dedup


# --------------------------------------------------
# PDF / 라인 추출
# --------------------------------------------------
def extract_lines(pdf_path: str, noise_patterns: Optional[List[str]] = None) -> List[Tuple[int, str]]:
    import pdfplumber

    compiled_noise_patterns = compile_noise_patterns(noise_patterns)
    out = []

    with pdfplumber.open(pdf_path) as pdf:
        for pageno, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if not text:
                continue

            for raw in text.split("\n"):
                raw = strip_right_spaces_only(raw)
                if not raw.strip():
                    continue
                if is_noise_line(raw, compiled_noise_patterns):
                    continue
                out.append((pageno, raw))

    return out


def find_earliest_opener(s: str):
    pos_angle = s.find("<")
    pos_square = s.find("[")

    candidates = []
    if pos_angle != -1:
        candidates.append((pos_angle, "<", ">"))
    if pos_square != -1:
        candidates.append((pos_square, "[", "]"))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0])
    return candidates[0]


def merge_broken_notes(lines):
    merged = []
    in_note = False
    note_buffer = []
    note_start_page = None
    note_closer = None

    for page, raw in lines:
        s = strip_right_spaces_only(raw)

        if not in_note:
            found = find_earliest_opener(s)
            if not found:
                merged.append((page, s))
                continue

            start_pos, opener, closer = found
            prefix = s[:start_pos].rstrip()
            candidate = s[start_pos:].lstrip()

            close_idx = candidate.find(closer)
            if close_idx != -1:
                note_text = candidate[:close_idx + 1].strip()
                tail = candidate[close_idx + 1:].strip()

                if prefix:
                    merged.append((page, prefix))
                if note_text:
                    merged.append((page, note_text))
                if tail:
                    merged.append((page, tail))
                continue

            if prefix:
                merged.append((page, prefix))

            in_note = True
            note_start_page = page
            note_closer = closer
            note_buffer = [candidate]

        else:
            note_buffer.append(s)
            joined = norm(" ".join(note_buffer))
            close_idx = joined.find(note_closer)

            if close_idx != -1:
                note_text = joined[:close_idx + 1].strip()
                tail = joined[close_idx + 1:].strip()

                if note_text:
                    merged.append((note_start_page, note_text))
                if tail:
                    merged.append((page, tail))

                in_note = False
                note_buffer = []
                note_start_page = None
                note_closer = None

    if in_note and note_buffer:
        merged.append((note_start_page or 1, norm(" ".join(note_buffer))))

    return merged


def repair_split_note_tails(lines):
    repaired = []
    i = 0

    while i < len(lines):
        page, s = lines[i]
        s_n = strip_right_spaces_only(s)

        if i + 1 < len(lines):
            _next_page, nxt = lines[i + 1]
            nxt_n = norm(nxt)

            angle_open = re.search(r"<[^>]*$", s_n)
            square_open = re.search(r"\[[^\]]*$", s_n)

            if angle_open and looks_like_date_tail_line(nxt_n):
                combined = s_n + " " + nxt_n
                repaired.append((page, norm(combined)))
                i += 2
                continue

            if square_open and looks_like_date_tail_line(nxt_n):
                combined = s_n + " " + nxt_n
                repaired.append((page, norm(combined)))
                i += 2
                continue

        repaired.append((page, s_n))
        i += 1

    return repaired


def looks_like_sentence_continuation(prev_line: str) -> bool:
    prev_line = norm(prev_line)
    if not prev_line:
        return False

    if prev_line.endswith(",") or prev_line.endswith(":"):
        return True

    for e in CONTINUATION_ENDINGS:
        if prev_line.endswith(e):
            return True

    if re.search(r"(에 따른|에 따라|에 의한|에 의하여|중|다음 각)\s*$", prev_line):
        return True

    if re.search(r"(의|에|에서|에게|으로|로)\s*$", prev_line):
        return True

    return False


def merge_reference_article_lines(lines):
    out = []
    i = 0

    while i < len(lines):
        page, cur = lines[i]
        cur_n = norm(cur)

        if i + 2 < len(lines):
            p1, line1 = lines[i]
            p2, line2 = lines[i + 1]
            p3, line3 = lines[i + 2]

            line1_n = norm(line1)
            line2_n = norm(line2)
            line3_n = norm(line3)

            if (
                looks_like_sentence_continuation(line1_n)
                and RE_ARTICLE_BARE.match(line2_n)
                and starts_with_postposition(line3_n)
            ):
                merged = f"{line1_n} {line2_n}{line3_n}"
                out.append((p1, norm(merged)))
                i += 3
                continue

        if i + 1 < len(lines):
            p1, line1 = lines[i]
            p2, line2 = lines[i + 1]

            line1_n = norm(line1)
            line2_n = norm(line2)

            if looks_like_sentence_continuation(line1_n):
                m = re.match(r"^(제\s*\d+\s*조(?:\s*의\s*\d+)?)(.+)$", line2_n)
                if m:
                    ref = norm(m.group(1))
                    tail = norm(m.group(2))
                    if starts_with_postposition(tail):
                        merged = f"{line1_n} {ref}{tail}"
                        out.append((p1, norm(merged)))
                        i += 2
                        continue

        out.append((page, cur_n))
        i += 1

    return out


def split_inline_item_lines(lines):
    out = []

    pat = re.compile(r"^(.*?\S)\s+(\d+(?:\s*의\s*\d+)?\s*[\.．]\s*.+)$")

    good_left_endings = (
        "품목", "의약품", "서류", "사항", "자료", "경우", "단서",
        "제외한", "동일한", "받은", "한다", "하여", "으로", "에서"
    )

    for page, raw in lines:
        s = norm(raw)

        m = pat.match(s)
        if not m:
            out.append((page, s))
            continue

        left = norm(m.group(1))
        right = norm(m.group(2))

        if not RE_ITEM.match(right):
            out.append((page, s))
            continue

        if not re.match(r"^\d+(?:\s*의\s*\d+)?\s*[\.．]\s*[가-힣A-Za-z\"'“‘(]", right):
            out.append((page, s))
            continue

        if left.endswith("<") or left.endswith("["):
            out.append((page, s))
            continue

        if len(left) < 12:
            out.append((page, s))
            continue

        if not any(left.endswith(x) for x in good_left_endings):
            out.append((page, s))
            continue

        out.append((page, left))
        out.append((page, right))

    return out


def split_after_notes(lines):
    out = []

    structural_pat = (
        r"(제\s*\d+\s*조(?:\s*의\s*\d+)?(?:\s*\([^)]*\))?"
        r"|[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]"
        r"|제\s*\d+\s*항"
        r"|\d+(?:\s*의\s*\d+)?\s*[\.．]"
        r"|\([가-힣]\)"
        r"|[가-힣][\.\)．]"
        r"|\d+\)"
        r"|[가나다라마바사아자차카타파하]\))"
    )

    pat_spaces2 = re.compile(
        rf"^(.*?(?:<[^>]*>|\[[^\]]*\]))[ \t]{{2,}}({structural_pat}.*)$"
    )

    pat_closed_then_struct = re.compile(
        rf"^(.*?(?:<[^>]*>|\[[^\]]*\]))\s*({structural_pat}.*)$"
    )

    for page, raw in lines:
        s = strip_right_spaces_only(raw)

        if ("<" in s and ">" not in s) or ("[" in s and "]" not in s):
            out.append((page, s))
            continue

        m = pat_spaces2.match(s)
        if m:
            left = norm(m.group(1))
            right = norm(m.group(2))
            if left:
                out.append((page, left))
            if right:
                out.append((page, right))
            continue

        m = pat_closed_then_struct.match(s)
        if m:
            left = norm(m.group(1))
            right = norm(m.group(2))
            if left != norm(s):
                if left:
                    out.append((page, left))
                if right:
                    out.append((page, right))
                continue

        out.append((page, s))

    return out


def is_likely_front_matter_prefix(prefix: str) -> bool:
    p = norm(prefix)
    if not p:
        return False

    strong_keywords = [
        "약칭", "식품의약품안전처", "법제처", "국가법령정보센터",
        "대표전화", "담당부서", "의약품관리과", "의약품품질과",
        "의약품안전평가과", "바이오의약품정책과", "임상정책과",
        "한약정책과", "의약외품정책과"
    ]
    if any(k in p for k in strong_keywords):
        return True

    if len(p) >= 40 and not looks_like_sentence_continuation(p):
        return True

    return False


def split_embedded_article_headers(lines):
    out = []

    for page, raw in lines:
        s = norm(raw)
        if not s:
            continue

        if RE_ARTICLE_HEADER.match(s):
            out.append((page, s))
            continue

        matches = list(RE_ARTICLE_INLINE_FINDER.finditer(s))
        if not matches:
            out.append((page, s))
            continue

        split_done = False
        for m in matches:
            start = m.start()
            if start <= 0:
                continue

            article_label = norm(m.group(1))
            prefix = norm(s[:start])
            suffix = norm(s[start:])

            if not prefix or not suffix:
                continue

            if looks_like_article_reference_line(suffix):
                continue

            if article_label.startswith("제1조") and is_likely_front_matter_prefix(prefix):
                out.append((page, prefix))
                out.append((page, suffix))
                split_done = True
                break

        if not split_done:
            out.append((page, s))

    return out


# --------------------------------------------------
# 구조 판정 보조
# --------------------------------------------------
def looks_like_article_reference_line(s: str) -> bool:
    s = norm(s)

    if re.match(r"^제\s*\d+\s*조(?:\s*의\s*\d+)?제\s*\d+\s*항", s):
        return True
    if re.match(r"^제\s*\d+\s*조(?:\s*의\s*\d+)?제\s*\d+\s*호", s):
        return True
    if re.match(r"^제\s*\d+\s*조(?:\s*의\s*\d+)?제\s*\d+\s*항제\s*\d+\s*호", s):
        return True

    return False


def should_force_continuation(prev_line: str, current_line: str) -> bool:
    if not prev_line:
        return False

    prev_line_n = norm(prev_line)
    current_line_n = norm(current_line)

    if not prev_line_n:
        return False

    if (
        RE_PART.match(current_line_n)
        or RE_CHAPTER.match(current_line_n)
        or RE_SECTION.match(current_line_n)
        or RE_ARTICLE_HEADER.match(current_line_n)
    ):
        return False

    if looks_like_sentence_continuation(prev_line_n):
        if (
            RE_PAR_CIRCLED.match(current_line_n)
            or RE_PAR_TEXT.match(current_line_n)
            or RE_ITEM.match(current_line_n)
            or RE_SUBITEM.match(current_line_n)
            or RE_SUBNUM_NUM.match(current_line_n)
            or RE_SUBNUM_KOR.match(current_line_n)
        ):
            return True

    return False


# --------------------------------------------------
# 본문 파싱
# --------------------------------------------------
def parse_main(lines):
    root = new_node("root", "root", page=1)
    stack = [root]
    warnings = []
    prev_line = ""

    def cur():
        return stack[-1]

    def current_level():
        return cur()["level"]

    def push(level, label, page, auto=False):
        node = new_node(level, label, page, auto=auto)
        cur()["children"].append(node)
        stack.append(node)
        return node

    def pop_one():
        if len(stack) > 1:
            stack.pop()

    def warn(code, page, line, extra=None):
        row = {
            "code": code,
            "page": page,
            "line": norm(line),
            "current_level": current_level()
        }
        if extra:
            row.update(extra)
        warnings.append(row)

    def get_last_child_by_level(node, level):
        for child in reversed(node["children"]):
            if child["level"] == level:
                return child
        return None

    def get_last_child_item_key(node):
        child = get_last_child_by_level(node, "item")
        if not child:
            return None
        m = re.match(r"제\s*(\d+)\s*호(?:의\s*(\d+))?", child["label"])
        if not m:
            return None
        main_no = int(m.group(1))
        sub_no = int(m.group(2)) if m.group(2) else 0
        return (main_no, sub_no)

    def get_last_child_subitem_letter(node):
        child = get_last_child_by_level(node, "subitem")
        if not child:
            return None
        m = re.match(r"([가-힣])목", child["label"])
        return m.group(1) if m else None

    def get_last_child_subnum_num(node):
        child = get_last_child_by_level(node, "subnum_num")
        if not child:
            return None
        m = re.match(r"(\d+)\)", child["label"])
        return int(m.group(1)) if m else None

    def get_last_child_subnum_kor(node):
        child = get_last_child_by_level(node, "subnum_kor")
        if not child:
            return None
        m = re.match(r"([가-힣])\)", child["label"])
        return m.group(1) if m else None

    def move_to_article_parent():
        while current_level() not in ["root", "part", "chapter", "section"]:
            pop_one()

    def move_to_parent_for(target_level):
        parent_level = PARENT[target_level]

        while True:
            cl = current_level()

            if cl == parent_level:
                return True

            if cl == target_level:
                pop_one()
                continue

            if IDX[cl] > IDX[parent_level]:
                pop_one()
                continue

            return False

    def ensure_article(page):
        if current_level() == "article":
            return cur()

        while current_level() not in ["root", "part", "chapter", "section", "article"]:
            pop_one()

        if current_level() == "article":
            return cur()

        return push("article", "제0조", page, auto=True)

    def ensure_paragraph(page):
        if current_level() == "paragraph":
            return cur()
        if current_level() == "article":
            return push("paragraph", "제1항", page, auto=True)
        art = ensure_article(page)
        if art and current_level() == "article":
            return push("paragraph", "제1항", page, auto=True)
        return None

    def ensure_item(page):
        if current_level() == "item":
            return cur()
        if current_level() == "paragraph":
            return push("item", "제1호", page, auto=True)
        para = ensure_paragraph(page)
        if para and current_level() == "paragraph":
            return push("item", "제1호", page, auto=True)
        return None

    def ensure_subitem(page):
        if current_level() == "subitem":
            return cur()
        if current_level() == "item":
            return push("subitem", "가목", page, auto=True)
        item = ensure_item(page)
        if item and current_level() == "item":
            return push("subitem", "가목", page, auto=True)
        return None

    def ensure_subnum_num(page):
        if current_level() == "subnum_num":
            return cur()
        if current_level() == "subitem":
            return push("subnum_num", "1)", page, auto=True)
        subitem = ensure_subitem(page)
        if subitem and current_level() == "subitem":
            return push("subnum_num", "1)", page, auto=True)
        return None

    def is_valid_next_item_key(parent_paragraph, new_main, new_sub):
        last_key = get_last_child_item_key(parent_paragraph)

        if last_key is None:
            return True

        last_main, last_sub = last_key

        if new_main == last_main:
            if last_sub == 0 and new_sub >= 1:
                return True
            if new_sub >= last_sub + 1 and new_sub >= 1:
                return True

        if new_main > last_main:
            return True

        return False

    def is_valid_next_subnum_num(parent_subitem, new_no):
        last_no = get_last_child_subnum_num(parent_subitem)
        if last_no is None:
            return new_no == 1
        return new_no == last_no + 1

    def is_valid_next_subnum_kor(parent_subnum_num, new_letter):
        if new_letter not in KOR_IDX:
            return False
        last_letter = get_last_child_subnum_kor(parent_subnum_num)
        if last_letter is None:
            return new_letter == "가"
        if last_letter not in KOR_IDX:
            return False
        return KOR_IDX[new_letter] == KOR_IDX[last_letter] + 1

    def auto_fill_items_until(parent_paragraph, target_main, target_sub, page):
        last_key = get_last_child_item_key(parent_paragraph)

        if last_key is None:
            if target_sub == 0 and 1 < target_main <= 3:
                for n in range(1, target_main):
                    parent_paragraph["children"].append(
                        new_node("item", f"제{n}호", page, auto=True)
                    )
                return True
            return False

        last_main, last_sub = last_key

        if target_main == last_main and target_sub > 0:
            start_sub = 1 if last_sub == 0 else last_sub + 1
            if start_sub < target_sub and (target_sub - start_sub) <= 3:
                for sn in range(start_sub, target_sub):
                    parent_paragraph["children"].append(
                        new_node("item", f"제{target_main}호의{sn}", page, auto=True)
                    )
                return True

        if target_sub == 0 and target_main > last_main + 1 and (target_main - last_main) <= 3:
            for n in range(last_main + 1, target_main):
                parent_paragraph["children"].append(
                    new_node("item", f"제{n}호", page, auto=True)
                )
            return True

        return False

    def auto_fill_subnum_num_until(parent_subitem, target_no, page):
        last_no = get_last_child_subnum_num(parent_subitem)
        if last_no is None:
            if 1 < target_no <= 3:
                for n in range(1, target_no):
                    parent_subitem["children"].append(
                        new_node("subnum_num", f"{n})", page, auto=True)
                    )
                return True
            return False

        gap = target_no - last_no
        if 1 < gap <= 3:
            for n in range(last_no + 1, target_no):
                parent_subitem["children"].append(
                    new_node("subnum_num", f"{n})", page, auto=True)
                )
            return True
        return False

    def auto_fill_subnum_kor_until(parent_subnum_num, target_letter, page):
        last_letter = get_last_child_subnum_kor(parent_subnum_num)
        if target_letter not in KOR_IDX:
            return False

        if last_letter is None:
            target_idx = KOR_IDX[target_letter]
            if 0 < target_idx <= 2:
                for i in range(0, target_idx):
                    parent_subnum_num["children"].append(
                        new_node("subnum_kor", f"{KOR_SEQ[i]})", page, auto=True)
                    )
                return True
            return False

        last_idx = KOR_IDX.get(last_letter, -1)
        target_idx = KOR_IDX[target_letter]
        gap = target_idx - last_idx
        if 1 < gap <= 3:
            for i in range(last_idx + 1, target_idx):
                parent_subnum_num["children"].append(
                    new_node("subnum_kor", f"{KOR_SEQ[i]})", page, auto=True)
                )
            return True
        return False

    def can_restart_item_sequence(parent_paragraph, new_main):
        last_key = get_last_child_item_key(parent_paragraph)
        if last_key is None:
            return False
        return new_main in {1, 2}

    def restart_item_sequence(page):
        while current_level() not in ["article", "paragraph"]:
            pop_one()

        if current_level() == "paragraph":
            pop_one()

        if current_level() == "article":
            return push("paragraph", "제1항", page, auto=True)

        return None

    def can_start_first_subitem_in_item(letter: str) -> bool:
        return letter == "가"

    def can_continue_subitem_in_item(item_node, letter: str) -> bool:
        last_letter = get_last_child_subitem_letter(item_node)
        if last_letter is None:
            return letter == "가"
        if letter not in KOR_IDX or last_letter not in KOR_IDX:
            return False
        return KOR_IDX[letter] > KOR_IDX[last_letter]

    for page, line in lines:
        line_n = norm(line)

        if not line_n:
            prev_line = line_n
            continue

        if is_note_like_line(line_n):
            add_note(cur(), line_n)
            prev_line = line_n
            continue

        m = RE_PART.match(line_n)
        if m:
            move_to_parent_for("part")
            push("part", f"제{m.group(1)}편", page)
            prev_line = line_n
            continue

        m = RE_CHAPTER.match(line_n)
        if m:
            move_to_parent_for("chapter")
            push("chapter", f"제{m.group(1)}장", page)
            prev_line = line_n
            continue

        m = RE_SECTION.match(line_n)
        if m:
            move_to_parent_for("section")
            push("section", f"제{m.group(1)}절", page)
            prev_line = line_n
            continue

        m = RE_ARTICLE_HEADER.match(line_n)
        if m:
            if looks_like_article_reference_line(line_n):
                txt, nts = extract_inline_notes(line_n)
                attach_text_and_notes(cur(), txt, nts)
                prev_line = line_n
                continue

            move_to_article_parent()

            label = norm(m.group(1))
            rest = norm(m.group(2) or "")
            rest_text, rest_notes = extract_inline_notes(rest)

            art = push("article", label, page)
            for nt in rest_notes:
                add_note(art, nt)

            if rest_text:
                mpc = RE_PAR_CIRCLED.match(rest_text)
                if mpc:
                    no = CIRCLED_TO_NUM.get(mpc.group(1))
                    plabel = f"제{no}항" if no else mpc.group(1)
                    p = push("paragraph", plabel, page)
                    add_text(p, mpc.group(2) or "")
                else:
                    mpt = RE_PAR_TEXT.match(rest_text)
                    if mpt:
                        p = push("paragraph", norm(mpt.group(1)), page)
                        add_text(p, mpt.group(2) or "")
                    else:
                        add_text(art, rest_text)

            prev_line = line_n
            continue

        if should_force_continuation(prev_line, line_n):
            txt, nts = extract_inline_notes(line_n)
            attach_text_and_notes(cur(), txt, nts)
            prev_line = line_n
            continue

        m = RE_PAR_CIRCLED.match(line_n)
        if m:
            ok = move_to_parent_for("paragraph")
            if not ok and current_level() != "article":
                ensure_article(page)

            if current_level() != "article":
                warn("paragraph_parent_autofix_failed", page, line_n)
                txt, nts = extract_inline_notes(line_n)
                attach_text_and_notes(cur(), txt, nts)
                prev_line = line_n
                continue

            txt, nts = extract_inline_notes(m.group(2) or "")
            no = CIRCLED_TO_NUM.get(m.group(1))
            plabel = f"제{no}항" if no else m.group(1)
            p = push("paragraph", plabel, page)
            attach_text_and_notes(p, txt, nts)
            prev_line = line_n
            continue

        m = RE_PAR_TEXT.match(line_n)
        if m:
            ok = move_to_parent_for("paragraph")
            if not ok and current_level() != "article":
                ensure_article(page)

            if current_level() != "article":
                warn("paragraph_parent_autofix_failed", page, line_n)
                txt, nts = extract_inline_notes(line_n)
                attach_text_and_notes(cur(), txt, nts)
                prev_line = line_n
                continue

            txt, nts = extract_inline_notes(m.group(2) or "")
            p = push("paragraph", norm(m.group(1)), page)
            attach_text_and_notes(p, txt, nts)
            prev_line = line_n
            continue

        m = RE_SUBNUM_NUM.match(line_n)
        if m and current_level() in ["paragraph", "item", "subitem", "subnum_num", "subnum_kor"]:
            ok = move_to_parent_for("subnum_num")
            if not ok:
                ensure_subitem(page)

            if current_level() != "subitem":
                warn("orphan_subnum_num_unresolved", page, line_n)
                txt, nts = extract_inline_notes(line_n)
                attach_text_and_notes(cur(), txt, nts)
                prev_line = line_n
                continue

            num = int(m.group(1))
            txt, nts = extract_inline_notes(m.group(2) or "")

            if not is_valid_next_subnum_num(cur(), num):
                repaired = auto_fill_subnum_num_until(cur(), num, page)
                if not repaired and get_last_child_subnum_num(cur()) is None and num == 1:
                    repaired = True

                if not repaired and not is_valid_next_subnum_num(cur(), num):
                    warn("invalid_subnum_num_sequence", page, line_n, {"candidate_subnum_num": num})
                    attach_text_and_notes(cur(), line_n, [])
                    prev_line = line_n
                    continue

            sn = push("subnum_num", f"{num})", page)
            attach_text_and_notes(sn, txt, nts)
            prev_line = line_n
            continue

        m = RE_SUBNUM_KOR.match(line_n)
        if m and current_level() in ["paragraph", "item", "subitem", "subnum_num", "subnum_kor"]:
            ok = move_to_parent_for("subnum_kor")
            if not ok:
                ensure_subnum_num(page)

            if current_level() != "subnum_num":
                warn("orphan_subnum_kor_unresolved", page, line_n)
                txt, nts = extract_inline_notes(line_n)
                attach_text_and_notes(cur(), txt, nts)
                prev_line = line_n
                continue

            letter = m.group(1)
            txt, nts = extract_inline_notes(m.group(2) or "")

            if not is_valid_next_subnum_kor(cur(), letter):
                repaired = auto_fill_subnum_kor_until(cur(), letter, page)
                if not repaired and not is_valid_next_subnum_kor(cur(), letter):
                    warn("invalid_subnum_kor_sequence", page, line_n, {"candidate_subnum_kor": letter})
                    attach_text_and_notes(cur(), line_n, [])
                    prev_line = line_n
                    continue

            sn = push("subnum_kor", f"{letter})", page)
            attach_text_and_notes(sn, txt, nts)
            prev_line = line_n
            continue

        m = RE_ITEM.match(line_n)
        if m and current_level() in ["article", "paragraph", "item", "subitem", "subnum_num", "subnum_kor"]:
            if looks_like_non_item_numeric_line(line_n):
                add_note(cur(), line_n)
                prev_line = line_n
                continue

            ok = move_to_parent_for("item")
            if not ok:
                ensure_paragraph(page)

            if current_level() != "paragraph":
                warn("orphan_item_unresolved", page, line_n)
                txt, nts = extract_inline_notes(line_n)
                attach_text_and_notes(cur(), txt, nts)
                prev_line = line_n
                continue

            main_no = int(m.group(1))
            sub_no = int(m.group(2)) if m.group(2) else 0
            txt, nts = extract_inline_notes(m.group(3) or "")

            if not is_valid_next_item_key(cur(), main_no, sub_no):
                if sub_no == 0 and can_restart_item_sequence(cur(), main_no):
                    new_para = restart_item_sequence(page)
                    if new_para is None:
                        warn("item_sequence_restart_failed", page, line_n, {
                            "candidate_item_main": main_no,
                            "candidate_item_sub": sub_no,
                            "last_item_key": get_last_child_item_key(cur())
                        })
                        attach_text_and_notes(cur(), line_n, [])
                        prev_line = line_n
                        continue
                else:
                    repaired = auto_fill_items_until(cur(), main_no, sub_no, page)
                    if not repaired and not is_valid_next_item_key(cur(), main_no, sub_no):
                        warn("invalid_item_sequence", page, line_n, {
                            "candidate_item_main": main_no,
                            "candidate_item_sub": sub_no,
                            "last_item_key": get_last_child_item_key(cur())
                        })
                        attach_text_and_notes(cur(), line_n, [])
                        prev_line = line_n
                        continue

            label = f"제{main_no}호" if sub_no == 0 else f"제{main_no}호의{sub_no}"
            it = push("item", label, page)
            attach_text_and_notes(it, txt, nts)
            prev_line = line_n
            continue

        m = RE_SUBITEM.match(line_n)
        if m:
            token = norm(m.group(1))
            letter = re.sub(r"[\(\)\.\)．\s]", "", token)
            txt, nts = extract_inline_notes(m.group(2) or "")

            if current_level() == "item":
                item_node = cur()

                if can_start_first_subitem_in_item(letter) and get_last_child_subitem_letter(item_node) is None:
                    s = push("subitem", f"{letter}목", page)
                    attach_text_and_notes(s, txt, nts)
                    prev_line = line_n
                    continue

                if letter == "가":
                    s = push("subitem", f"{letter}목", page)
                    attach_text_and_notes(s, txt, nts)
                    prev_line = line_n
                    continue

                if can_continue_subitem_in_item(item_node, letter):
                    s = push("subitem", f"{letter}목", page)
                    attach_text_and_notes(s, txt, nts)
                    prev_line = line_n
                    continue

                warn("invalid_subitem_sequence", page, line_n, {"candidate_subitem_letter": letter})
                attach_text_and_notes(cur(), line_n, [])
                prev_line = line_n
                continue

            if current_level() in ["subitem", "subnum_num", "subnum_kor"]:
                while current_level() in ["subitem", "subnum_num", "subnum_kor"]:
                    pop_one()

                if current_level() == "item":
                    item_node = cur()

                    if can_start_first_subitem_in_item(letter) and get_last_child_subitem_letter(item_node) is None:
                        s = push("subitem", f"{letter}목", page)
                        attach_text_and_notes(s, txt, nts)
                        prev_line = line_n
                        continue

                    if letter == "가":
                        s = push("subitem", f"{letter}목", page)
                        attach_text_and_notes(s, txt, nts)
                        prev_line = line_n
                        continue

                    if can_continue_subitem_in_item(item_node, letter):
                        s = push("subitem", f"{letter}목", page)
                        attach_text_and_notes(s, txt, nts)
                        prev_line = line_n
                        continue

                    warn("invalid_subitem_sequence", page, line_n, {"candidate_subitem_letter": letter})
                    attach_text_and_notes(cur(), line_n, [])
                    prev_line = line_n
                    continue

            if current_level() == "paragraph":
                if letter == "가":
                    ensure_item(page)
                    if current_level() == "item":
                        s = push("subitem", f"{letter}목", page)
                        attach_text_and_notes(s, txt, nts)
                        prev_line = line_n
                        continue

                attach_text_and_notes(cur(), line_n, [])
                prev_line = line_n
                continue

            attach_text_and_notes(cur(), line_n, [])
            prev_line = line_n
            continue

        txt, nts = extract_inline_notes(line_n)
        attach_text_and_notes(cur(), txt, nts)
        prev_line = line_n

    return root, warnings


# --------------------------------------------------
# 후처리
# --------------------------------------------------
def repair_split_notes_in_tree(node):
    text = node.get("text", "") or ""
    notes = node.get("notes", []) or []

    angle_match = re.search(r"\s*(<[^>]*)$", text)
    if angle_match and notes:
        dangling = norm(angle_match.group(1))
        first_note = norm(notes[0])

        if any(k in dangling for k in NOTE_KEYWORDS) and looks_like_note_tail_fragment(first_note):
            combined = norm(dangling + " " + first_note)
            node["text"] = norm(text[:angle_match.start()])
            node["notes"] = [combined] + notes[1:]

    text = node.get("text", "") or ""
    notes = node.get("notes", []) or []

    square_match = re.search(r"\s*(\[[^\]]*)$", text)
    if square_match and notes:
        dangling = norm(square_match.group(1))
        first_note = norm(notes[0])

        if any(k in dangling for k in NOTE_KEYWORDS) and looks_like_note_tail_fragment(first_note):
            combined = norm(dangling + " " + first_note)
            node["text"] = norm(text[:square_match.start()])
            node["notes"] = [combined] + notes[1:]

    for ch in node.get("children", []):
        repair_split_notes_in_tree(ch)


def prune_empty_auto_nodes(node):
    kept = []
    for ch in node.get("children", []):
        if isinstance(ch, dict) and "children" in ch:
            prune_empty_auto_nodes(ch)
            if ch.get("auto_created"):
                if not ch.get("text") and not ch.get("notes") and not ch.get("children"):
                    continue
        kept.append(ch)
    node["children"] = kept


def summarize_warnings(warnings):
    stat = {}
    for w in warnings:
        code = w["code"]
        stat[code] = stat.get(code, 0) + 1
    return stat


# --------------------------------------------------
# 공통 파이프라인
# --------------------------------------------------
def preprocess_lines(lines):
    lines = merge_broken_notes(lines)
    lines = repair_split_note_tails(lines)
    lines = merge_reference_article_lines(lines)
    lines = split_inline_item_lines(lines)
    lines = split_after_notes(lines)
    lines = split_embedded_article_headers(lines)
    return lines


def parse_document_structure_from_lines(lines):
    lines = preprocess_lines(lines)

    main_tree, warnings = parse_main(lines)
    repair_split_notes_in_tree(main_tree)
    prune_empty_auto_nodes(main_tree)

    warning_summary = summarize_warnings(warnings)

    return {
        "main_tree": main_tree,
        "warnings": warnings,
        "warning_summary": warning_summary
    }


def parse_document_structure(pdf_path: str, noise_patterns: Optional[List[str]] = None):
    lines = extract_lines(pdf_path, noise_patterns=noise_patterns)
    return parse_document_structure_from_lines(lines)


# --------------------------------------------------
# 디버그 유틸
# --------------------------------------------------
def print_warning_samples(warnings, code, limit=20):
    n = 0
    print(f"\n[warning samples] {code}")
    for w in warnings:
        if w["code"] == code:
            print(f'- p{w["page"]}: {w["line"]}')
            n += 1
            if n >= limit:
                break


def print_lines_debug(lines, keyword=None, limit=50):
    print("\n[lines debug]")
    cnt = 0
    for page, s in lines:
        if keyword and keyword not in s:
            continue
        print(f"p{page}: {s}")
        cnt += 1
        if cnt >= limit:
            break