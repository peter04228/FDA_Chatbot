import os
import re
from typing import Dict, Any, List, Optional


# --------------------------------------------------
# 기본 유틸
# --------------------------------------------------
def norm(s: Optional[str]) -> str:
    if s is None:
        return ""
    s = s.replace("\u00A0", " ")
    s = s.replace("\ufeff", "")
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


def normalize_reference_text(text: Optional[str]) -> str:
    """
    법령 참조 파싱 전용 정규화.
    - 연결자 뒤 개행 제거
    - 일반 개행은 공백으로 변환
    - 다중 공백 정리
    """
    if text is None:
        return ""

    text = text.replace("\u00A0", " ")
    text = text.replace("\ufeff", "")
    text = text.replace("\r", "\n")

    # 연결자 뒤 개행 제거
    text = re.sub(r"([,ㆍ])\s*\n\s*", r"\1", text)
    text = re.sub(r"(및|또는)\s*\n\s*", r"\1 ", text)

    # 일반 개행은 공백으로
    text = re.sub(r"\s*\n\s*", " ", text)

    # 다중 공백 정리
    text = re.sub(r"[ \t]+", " ", text)

    return text.strip()


# --------------------------------------------------
# 파일명 / 제목 정리
# --------------------------------------------------
RE_FILE_EXT = re.compile(r"\.pdf$", re.IGNORECASE)

RE_TRAILING_META_PARENS = re.compile(
    r"(?:\((?:식품의약품안전처예규|식품의약품안전처고시|식품의약품안전처공고|제\d+호|\d{8})\))+$"
)

RE_DOC_NO = re.compile(r"\(제\s*([0-9]+)\s*호\)")
RE_EFFECTIVE_YYYYMMDD = re.compile(r"\((20\d{2})(\d{2})(\d{2})\)")
RE_ISSUING_BODY = re.compile(
    r"\((식품의약품안전처|보건복지부|총리령|대통령령)(?:예규|고시|공고)?\)"
)


def clean_title_from_filename(file_name: str) -> str:
    base = os.path.basename(file_name)
    base = RE_FILE_EXT.sub("", base)
    title = RE_TRAILING_META_PARENS.sub("", base)
    return norm(title)


def extract_doc_no_from_filename(file_name: str) -> Optional[str]:
    m = RE_DOC_NO.search(file_name)
    if not m:
        return None
    return f"제{m.group(1)}호"


def extract_effective_date_from_filename(file_name: str) -> Optional[str]:
    m = RE_EFFECTIVE_YYYYMMDD.search(file_name)
    if not m:
        return None
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"


def extract_issuing_body_from_filename(file_name: str) -> Optional[str]:
    m = RE_ISSUING_BODY.search(file_name)
    if not m:
        return None
    return norm(m.group(1))


def extract_common_meta(
    file_name: str,
    source_path: str,
    document_type: str,
) -> Dict[str, Any]:
    return {
        "file_name": file_name,
        "source_path": source_path,
        "document_type": document_type,
        "title": clean_title_from_filename(file_name),
        "issuing_body": extract_issuing_body_from_filename(file_name),
        "document_no": extract_doc_no_from_filename(file_name),
        "effective_date": extract_effective_date_from_filename(file_name),
    }


# --------------------------------------------------
# article 탐색
# --------------------------------------------------
def iter_articles(node: Dict[str, Any]):
    if not isinstance(node, dict):
        return
    if node.get("level") == "article":
        yield node
    for ch in node.get("children", []):
        yield from iter_articles(ch)


def find_article1(main_tree: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    article1 = None

    for art in iter_articles(main_tree):
        label = norm(art.get("label", ""))
        if label.startswith("제1조"):
            return art
        if "목적" in label and article1 is None:
            article1 = art

    return article1


def collect_full_article_text(article_node: Dict[str, Any]) -> str:
    """
    목적조 문장 복원용.
    article.text + article 바로 아래 paragraph.label/text를 이어붙임.
    """
    parts: List[str] = []

    article_text = article_node.get("text")
    if article_text:
        parts.append(str(article_text))

    for ch in article_node.get("children", []):
        if ch.get("level") == "paragraph":
            p_label = ch.get("label")
            p_text = ch.get("text")

            chunk = ""
            if p_label:
                chunk += str(p_label)
            if p_text:
                if chunk:
                    chunk += " "
                chunk += str(p_text)

            if chunk:
                parts.append(chunk)

    return normalize_reference_text(" ".join(parts))


# --------------------------------------------------
# 대상 법령명 정규화
# --------------------------------------------------
TARGET_LAW_NAME = "의약품 등의 안전에 관한 규칙"
TARGET_LAW_NAME_PATTERN = r"의약품\s*등의\s*안전에\s*관한\s*규칙"


def canonicalize_law_name(law_name: str) -> str:
    compact = re.sub(r"\s+", "", norm(law_name))
    if compact == "의약품등의안전에관한규칙":
        return TARGET_LAW_NAME
    return norm(law_name)


# --------------------------------------------------
# 규정 참조 파싱
# --------------------------------------------------
RE_TARGET_LAW_BLOCK = re.compile(
    rf"「({TARGET_LAW_NAME_PATTERN})」"
    rf"(?:\s*\((?:[^()]|\([^()]*\))*\))?"
    rf"\s*([^「」]*)"
)

RE_TARGET_LAW_INLINE_HEAD = re.compile(
    rf"(?:(?:^|[\s,(])(?:및|또는)?\s*)"
    rf"({TARGET_LAW_NAME_PATTERN})\s+"
)

RE_SINGLE_REF = re.compile(
    r"제\s*(\d+)\s*조"
    r"(?:\s*의\s*(\d+))?"
    r"(?:\s*제\s*(\d+)\s*항)?"
    r"(?:\s*제\s*(\d+)\s*호(?:\s*의\s*(\d+))?)?"
    r"(?:\s*([가-하])\s*목)?"
)

RE_PARAGRAPH_ITEM_ONLY_REF = re.compile(
    r"제\s*(\d+)\s*항\s*제\s*(\d+)\s*호(?:\s*의\s*(\d+))?(?:\s*([가-하])\s*목)?"
)

RE_PARAGRAPH_ONLY_REF = re.compile(
    r"제\s*(\d+)\s*항"
)

RE_ITEM_ONLY_REF = re.compile(
    r"제\s*(\d+)\s*호(?:\s*의\s*(\d+))?(?:\s*([가-하])\s*목)?"
)

RE_SUBITEM_ONLY_REF = re.compile(
    r"([가-하])\s*목"
)

RE_ARTICLE_RANGE_REF = re.compile(
    r"제\s*(\d+)\s*조"
    r"(?:\s*의\s*(\d+))?"
    r"(?:\s*제\s*(\d+)\s*항)?"
    r"\s*부터\s*"
    r"제\s*(\d+)\s*조"
    r"(?:\s*의\s*(\d+))?"
    r"(?:\s*제\s*(\d+)\s*항)?"
    r"\s*까지"
)

RE_SAME_ARTICLE_PARAGRAPH_RANGE_REF = re.compile(
    r"제\s*(\d+)\s*조"
    r"(?:\s*의\s*(\d+))?"
    r"\s*제\s*(\d+)\s*항"
    r"\s*부터\s*"
    r"(?:제\s*)?(\d+)\s*항"
    r"\s*까지"
)

RE_SAME_ITEM_SUBITEM_RANGE_REF = re.compile(
    r"제\s*(\d+)\s*조"
    r"(?:\s*의\s*(\d+))?"
    r"(?:\s*제\s*(\d+)\s*항)?"
    r"\s*제\s*(\d+)\s*호(?:\s*의\s*(\d+))?"
    r"\s*([가-하])\s*목"
    r"\s*부터\s*"
    r"([가-하])\s*목"
    r"\s*까지"
)

RE_SAME_ARTICLE_PREFIX = re.compile(r"^같은\s*조\b")
RE_SAME_PARAGRAPH_PREFIX = re.compile(r"^같은\s*항\b")

RE_ATTACHED_TABLE_WITH_ARTICLE = re.compile(
    r"제\s*(\d+)\s*조"
    r"(?:\s*의\s*(\d+))?"
    r"\s*별표\s*(\d+(?:\s*의\s*\d+)?)"
    r"\s*제\s*([0-9]+(?:\.[0-9]+)*)\s*호"
    r"(?:\s*([가-하])\s*목)?"
)

RE_ATTACHED_TABLE_ONLY = re.compile(
    r"별표\s*(\d+(?:\s*의\s*\d+)?)"
    r"\s*제\s*([0-9]+(?:\.[0-9]+)*)\s*호"
    r"(?:\s*([가-하])\s*목)?"
)

RE_CONNECTOR_SPLIT = re.compile(r"\s*(?:,|ㆍ|및|또는)\s*")

RE_TRAILING_PURPOSE_END = re.compile(
    r"(에\s*따라.*|에\s*의해.*|에\s*의하여.*|에\s*관한.*|을\s*위한.*|을\s*목적으로.*)$"
)

RE_INLINE_TAIL_STOP = re.compile(
    r"(에\s*따라|에\s*의해|에\s*의하여|에\s*관한|을\s*위한|을\s*목적으로|에\s*대하여|에\s*대해)"
)


# --------------------------------------------------
# 공통 builder
# --------------------------------------------------
def build_rule_entity_id(
    law_name: str,
    article_no: Optional[str],
    paragraph_no: Optional[str],
    item_no: Optional[str],
    subitem_no: Optional[str],
) -> str:
    parts = ["rule", norm(law_name)]

    if article_no:
        parts.append(str(article_no))
    if paragraph_no:
        parts.append(str(paragraph_no))
    if item_no:
        parts.append(str(item_no))
    if subitem_no:
        parts.append(str(subitem_no))

    return "_".join(parts)


def infer_anchor_confidence(ref: Dict[str, Any]) -> str:
    source_style = ref.get("source_style")
    ref_type = ref.get("type")

    if source_style == "quoted" and ref_type in {"single", "multi", "range", "attached_table"}:
        return "high"

    if source_style == "inline" and ref_type in {"single", "multi", "range", "attached_table"}:
        return "medium"

    return "low"


def normalize_item_no(item_main: Optional[str], item_sub: Optional[str]) -> Optional[str]:
    if not item_main:
        return None
    if item_sub:
        return f"{item_main}의{item_sub}"
    return item_main


def build_single_ref(
    law_name: str,
    article_no: Optional[str],
    article_sub_no: Optional[str],
    paragraph_no: Optional[str],
    item_no: Optional[str],
    item_sub_no: Optional[str],
    subitem_no: Optional[str],
    raw: str,
    source_style: str,
) -> Dict[str, Any]:
    full_article_no = article_no
    if article_no and article_sub_no:
        full_article_no = f"{article_no}의{article_sub_no}"

    full_item_no = normalize_item_no(item_no, item_sub_no)

    ref = {
        "type": "single",
        "law_name": norm(law_name),
        "article_no": full_article_no,
        "paragraph_no": paragraph_no,
        "item_no": full_item_no,
        "subitem_no": subitem_no,
        "raw": norm(raw),
        "source_style": source_style,
        "entity_id": build_rule_entity_id(
            law_name=law_name,
            article_no=full_article_no,
            paragraph_no=paragraph_no,
            item_no=full_item_no,
            subitem_no=subitem_no,
        ),
    }
    ref["anchor_confidence"] = infer_anchor_confidence(ref)
    return ref


def build_attached_table_ref(
    law_name: str,
    article_no: Optional[str],
    article_sub_no: Optional[str],
    attached_no: str,
    item_no: str,
    subitem_no: Optional[str],
    raw: str,
    source_style: str,
) -> Dict[str, Any]:
    full_article_no = article_no
    if article_no and article_sub_no:
        full_article_no = f"{article_no}의{article_sub_no}"

    attached_no = norm(attached_no).replace(" ", "")
    ref = {
        "type": "attached_table",
        "law_name": norm(law_name),
        "article_no": full_article_no,
        "attached_type": "별표",
        "attached_no": attached_no,
        "item_no": norm(item_no),
        "subitem_no": subitem_no,
        "raw": norm(raw),
        "source_style": source_style,
        "entity_id": build_rule_entity_id(
            law_name=law_name,
            article_no=full_article_no if full_article_no else f"별표{attached_no}",
            paragraph_no=None,
            item_no=item_no,
            subitem_no=subitem_no,
        ),
    }
    ref["anchor_confidence"] = infer_anchor_confidence(ref)
    return ref


# --------------------------------------------------
# 전처리
# --------------------------------------------------
def cleanup_tail_for_reference_parsing(tail: str) -> str:
    tail = norm(tail)
    tail = RE_TRAILING_PURPOSE_END.sub("", tail)
    return norm(tail)


def extract_inline_tail(text: str, start_pos: int) -> str:
    tail = text[start_pos:]
    stop = RE_INLINE_TAIL_STOP.search(tail)
    if stop:
        tail = tail[:stop.start()]
    return norm(tail)


# --------------------------------------------------
# 단일 ref 파서
# --------------------------------------------------
def parse_single_ref_text(
    law_name: str,
    ref_text: str,
    source_style: str,
) -> Optional[Dict[str, Any]]:
    ref_text = norm(ref_text)
    m = RE_SINGLE_REF.fullmatch(ref_text)
    if not m:
        return None

    return build_single_ref(
        law_name=law_name,
        article_no=m.group(1),
        article_sub_no=m.group(2),
        paragraph_no=m.group(3),
        item_no=m.group(4),
        item_sub_no=m.group(5),
        subitem_no=m.group(6),
        raw=ref_text,
        source_style=source_style,
    )


def parse_same_context_ref_with_context(
    law_name: str,
    ref_text: str,
    source_style: str,
    current_article_no: Optional[str],
    current_paragraph_no: Optional[str],
) -> Optional[Dict[str, Any]]:
    ref_text = norm(ref_text)

    if RE_SAME_ARTICLE_PREFIX.match(ref_text):
        rest = RE_SAME_ARTICLE_PREFIX.sub("", ref_text, count=1).strip()
        if not current_article_no:
            return None

        single = parse_abbreviated_ref_with_context(
            law_name=law_name,
            ref_text=rest,
            source_style=source_style,
            current_article_no=current_article_no,
            current_paragraph_no=current_paragraph_no,
        )
        if single:
            return single

        m = RE_SINGLE_REF.search(rest)
        if m:
            return build_single_ref(
                law_name=law_name,
                article_no=current_article_no,
                article_sub_no=None,
                paragraph_no=m.group(3),
                item_no=m.group(4),
                item_sub_no=m.group(5),
                subitem_no=m.group(6),
                raw=ref_text,
                source_style=source_style,
            )

    if RE_SAME_PARAGRAPH_PREFIX.match(ref_text):
        rest = RE_SAME_PARAGRAPH_PREFIX.sub("", ref_text, count=1).strip()
        if not current_article_no or current_paragraph_no is None:
            return None

        m_item = RE_ITEM_ONLY_REF.fullmatch(rest)
        if m_item:
            return build_single_ref(
                law_name=law_name,
                article_no=current_article_no,
                article_sub_no=None,
                paragraph_no=current_paragraph_no,
                item_no=m_item.group(1),
                item_sub_no=m_item.group(2),
                subitem_no=m_item.group(3),
                raw=ref_text,
                source_style=source_style,
            )

    return None


def parse_abbreviated_ref_with_context(
    law_name: str,
    ref_text: str,
    source_style: str,
    current_article_no: Optional[str],
    current_paragraph_no: Optional[str],
) -> Optional[Dict[str, Any]]:
    ref_text = norm(ref_text)

    m_par_item = RE_PARAGRAPH_ITEM_ONLY_REF.fullmatch(ref_text)
    if m_par_item and current_article_no:
        return build_single_ref(
            law_name=law_name,
            article_no=current_article_no,
            article_sub_no=None,
            paragraph_no=m_par_item.group(1),
            item_no=m_par_item.group(2),
            item_sub_no=m_par_item.group(3),
            subitem_no=m_par_item.group(4),
            raw=ref_text,
            source_style=source_style,
        )

    m_par = RE_PARAGRAPH_ONLY_REF.fullmatch(ref_text)
    if m_par and current_article_no:
        return build_single_ref(
            law_name=law_name,
            article_no=current_article_no,
            article_sub_no=None,
            paragraph_no=m_par.group(1),
            item_no=None,
            item_sub_no=None,
            subitem_no=None,
            raw=ref_text,
            source_style=source_style,
        )

    m_item = RE_ITEM_ONLY_REF.fullmatch(ref_text)
    if m_item and current_article_no:
        return build_single_ref(
            law_name=law_name,
            article_no=current_article_no,
            article_sub_no=None,
            paragraph_no=current_paragraph_no,
            item_no=m_item.group(1),
            item_sub_no=m_item.group(2),
            subitem_no=m_item.group(3),
            raw=ref_text,
            source_style=source_style,
        )

    m_subitem = RE_SUBITEM_ONLY_REF.fullmatch(ref_text)
    if m_subitem and current_article_no:
        return build_single_ref(
            law_name=law_name,
            article_no=current_article_no,
            article_sub_no=None,
            paragraph_no=current_paragraph_no,
            item_no=None,
            item_sub_no=None,
            subitem_no=m_subitem.group(1),
            raw=ref_text,
            source_style=source_style,
        )

    return None


# --------------------------------------------------
# range 파서
# --------------------------------------------------
def parse_article_range_refs(
    law_name: str,
    tail: str,
    source_style: str,
) -> List[Dict[str, Any]]:
    results = []

    for m in RE_ARTICLE_RANGE_REF.finditer(tail):
        start_article = m.group(1)
        start_article_sub = m.group(2)
        start_paragraph = m.group(3)

        end_article = m.group(4)
        end_article_sub = m.group(5)
        end_paragraph = m.group(6)

        start_full = start_article if not start_article_sub else f"{start_article}의{start_article_sub}"
        end_full = end_article if not end_article_sub else f"{end_article}의{end_article_sub}"

        ref = {
            "type": "range",
            "range_kind": "article_range",
            "law_name": norm(law_name),
            "raw": norm(m.group(0)),
            "source_style": source_style,
            "start_article_no": start_full,
            "end_article_no": end_full,
            "start_paragraph_no": start_paragraph,
            "end_paragraph_no": end_paragraph,
            "item_no": None,
            "subitem_no": None,
            "entity_id": build_rule_entity_id(
                law_name=law_name,
                article_no=f"{start_full}_{end_full}",
                paragraph_no=None,
                item_no=None,
                subitem_no=None,
            ),
        }
        ref["anchor_confidence"] = infer_anchor_confidence(ref)
        results.append(ref)

    return results


def parse_same_article_paragraph_range_refs(
    law_name: str,
    tail: str,
    source_style: str,
) -> List[Dict[str, Any]]:
    results = []

    for m in RE_SAME_ARTICLE_PARAGRAPH_RANGE_REF.finditer(tail):
        article_no = m.group(1)
        article_sub_no = m.group(2)
        start_paragraph = m.group(3)
        end_paragraph = m.group(4)

        full_article_no = article_no if not article_sub_no else f"{article_no}의{article_sub_no}"

        ref = {
            "type": "range",
            "range_kind": "same_article_paragraph",
            "law_name": norm(law_name),
            "raw": norm(m.group(0)),
            "source_style": source_style,
            "article_no": full_article_no,
            "start_article_no": full_article_no,
            "end_article_no": full_article_no,
            "start_paragraph_no": start_paragraph,
            "end_paragraph_no": end_paragraph,
            "item_no": None,
            "subitem_no": None,
            "entity_id": build_rule_entity_id(
                law_name=law_name,
                article_no=f"{full_article_no}_{start_paragraph}_{end_paragraph}",
                paragraph_no=None,
                item_no=None,
                subitem_no=None,
            ),
        }
        ref["anchor_confidence"] = infer_anchor_confidence(ref)
        results.append(ref)

    return results


def parse_same_item_subitem_range_refs(
    law_name: str,
    tail: str,
    source_style: str,
) -> List[Dict[str, Any]]:
    results = []

    for m in RE_SAME_ITEM_SUBITEM_RANGE_REF.finditer(tail):
        article_no = m.group(1)
        article_sub_no = m.group(2)
        paragraph_no = m.group(3)
        item_no = m.group(4)
        item_sub_no = m.group(5)
        start_subitem_no = m.group(6)
        end_subitem_no = m.group(7)

        full_article_no = article_no if not article_sub_no else f"{article_no}의{article_sub_no}"
        full_item_no = normalize_item_no(item_no, item_sub_no)

        ref = {
            "type": "range",
            "range_kind": "same_item_subitem",
            "law_name": norm(law_name),
            "raw": norm(m.group(0)),
            "source_style": source_style,
            "article_no": full_article_no,
            "paragraph_no": paragraph_no,
            "item_no": full_item_no,
            "start_subitem_no": start_subitem_no,
            "end_subitem_no": end_subitem_no,
            "entity_id": build_rule_entity_id(
                law_name=law_name,
                article_no=full_article_no,
                paragraph_no=paragraph_no,
                item_no=full_item_no,
                subitem_no=f"{start_subitem_no}_{end_subitem_no}",
            ),
        }
        ref["anchor_confidence"] = infer_anchor_confidence(ref)
        results.append(ref)

    return results


def remove_range_texts(tail: str) -> str:
    tail = RE_SAME_ITEM_SUBITEM_RANGE_REF.sub(" ", tail)
    tail = RE_SAME_ARTICLE_PARAGRAPH_RANGE_REF.sub(" ", tail)
    tail = RE_ARTICLE_RANGE_REF.sub(" ", tail)
    return norm(tail)


# --------------------------------------------------
# 별표 파서
# --------------------------------------------------
def parse_attached_table_refs(
    law_name: str,
    tail: str,
    source_style: str,
) -> List[Dict[str, Any]]:
    results = []

    for m in RE_ATTACHED_TABLE_WITH_ARTICLE.finditer(tail):
        ref = build_attached_table_ref(
            law_name=law_name,
            article_no=m.group(1),
            article_sub_no=m.group(2),
            attached_no=m.group(3),
            item_no=m.group(4),
            subitem_no=m.group(5),
            raw=m.group(0),
            source_style=source_style,
        )
        results.append(ref)

    for m in RE_ATTACHED_TABLE_ONLY.finditer(tail):
        ref = build_attached_table_ref(
            law_name=law_name,
            article_no=None,
            article_sub_no=None,
            attached_no=m.group(1),
            item_no=m.group(2),
            subitem_no=m.group(3),
            raw=m.group(0),
            source_style=source_style,
        )
        results.append(ref)

    return results


def remove_attached_table_texts(tail: str) -> str:
    tail = RE_ATTACHED_TABLE_WITH_ARTICLE.sub(" ", tail)
    tail = RE_ATTACHED_TABLE_ONLY.sub(" ", tail)
    return norm(tail)


# --------------------------------------------------
# multi / single 파서
# --------------------------------------------------
def parse_multi_or_single_refs(
    law_name: str,
    tail: str,
    source_style: str,
) -> List[Dict[str, Any]]:
    tail = cleanup_tail_for_reference_parsing(tail)
    if not tail:
        return []

    parts = RE_CONNECTOR_SPLIT.split(tail)
    parts = [norm(p) for p in parts if norm(p)]

    singles = []
    seen = set()

    current_article_no = None
    current_paragraph_no = None

    for part in parts:
        single = parse_single_ref_text(
            law_name=law_name,
            ref_text=part,
            source_style=source_style,
        )

        if not single:
            single = parse_same_context_ref_with_context(
                law_name=law_name,
                ref_text=part,
                source_style=source_style,
                current_article_no=current_article_no,
                current_paragraph_no=current_paragraph_no,
            )

        if not single:
            single = parse_abbreviated_ref_with_context(
                law_name=law_name,
                ref_text=part,
                source_style=source_style,
                current_article_no=current_article_no,
                current_paragraph_no=current_paragraph_no,
            )

        if not single:
            m = RE_SINGLE_REF.search(part)
            if m:
                single = build_single_ref(
                    law_name=law_name,
                    article_no=m.group(1),
                    article_sub_no=m.group(2),
                    paragraph_no=m.group(3),
                    item_no=m.group(4),
                    item_sub_no=m.group(5),
                    subitem_no=m.group(6),
                    raw=m.group(0),
                    source_style=source_style,
                )

        if not single:
            continue

        if single.get("article_no"):
            current_article_no = single["article_no"]
        if single.get("paragraph_no") is not None:
            current_paragraph_no = single["paragraph_no"]

        key = (
            single["law_name"],
            single["article_no"],
            single["paragraph_no"],
            single["item_no"],
            single["subitem_no"],
        )
        if key in seen:
            continue

        seen.add(key)
        singles.append(single)

    if not singles:
        return []

    if len(singles) == 1:
        return singles

    multi = {
        "type": "multi",
        "law_name": norm(law_name),
        "raw": tail,
        "source_style": source_style,
        "children": singles,
        "entity_id": build_rule_entity_id(
            law_name=law_name,
            article_no="multi",
            paragraph_no=None,
            item_no=None,
            subitem_no=None,
        ),
    }
    multi["anchor_confidence"] = infer_anchor_confidence(multi)
    return [multi]


# --------------------------------------------------
# dedupe
# --------------------------------------------------
def _append_ref_if_new(
    refs: List[Dict[str, Any]],
    seen_serialized: set,
    ref: Dict[str, Any],
):
    if ref["type"] == "single":
        key = (
            ref["type"],
            ref["law_name"],
            ref.get("article_no"),
            ref.get("paragraph_no"),
            ref.get("item_no"),
            ref.get("subitem_no"),
        )
    elif ref["type"] == "range":
        key = (
            ref["type"],
            ref["law_name"],
            ref.get("range_kind"),
            ref.get("article_no"),
            ref.get("paragraph_no"),
            ref.get("item_no"),
            ref.get("start_article_no"),
            ref.get("end_article_no"),
            ref.get("start_paragraph_no"),
            ref.get("end_paragraph_no"),
            ref.get("start_subitem_no"),
            ref.get("end_subitem_no"),
        )
    elif ref["type"] == "attached_table":
        key = (
            ref["type"],
            ref["law_name"],
            ref.get("article_no"),
            ref.get("attached_no"),
            ref.get("item_no"),
            ref.get("subitem_no"),
        )
    else:
        child_keys = tuple(
            (
                ch.get("article_no"),
                ch.get("paragraph_no"),
                ch.get("item_no"),
                ch.get("subitem_no"),
            )
            for ch in ref.get("children", [])
        )
        key = (ref["type"], ref["law_name"], child_keys)

    if key in seen_serialized:
        return

    seen_serialized.add(key)
    refs.append(ref)


# --------------------------------------------------
# tail 처리
# --------------------------------------------------
def _process_tail(
    refs: List[Dict[str, Any]],
    seen_serialized: set,
    law_name: str,
    tail: str,
    source_style: str,
):
    if not tail:
        return

    tail = norm(tail)
    if "제" not in tail and "별표" not in tail and "같은 조" not in tail:
        return

    attached_refs = parse_attached_table_refs(
        law_name=law_name,
        tail=tail,
        source_style=source_style,
    )
    for ref in attached_refs:
        _append_ref_if_new(refs, seen_serialized, ref)

    tail_wo_attached = remove_attached_table_texts(tail)

    same_item_subitem_ranges = parse_same_item_subitem_range_refs(
        law_name=law_name,
        tail=tail_wo_attached,
        source_style=source_style,
    )
    for ref in same_item_subitem_ranges:
        _append_ref_if_new(refs, seen_serialized, ref)

    same_article_par_ranges = parse_same_article_paragraph_range_refs(
        law_name=law_name,
        tail=tail_wo_attached,
        source_style=source_style,
    )
    for ref in same_article_par_ranges:
        _append_ref_if_new(refs, seen_serialized, ref)

    article_ranges = parse_article_range_refs(
        law_name=law_name,
        tail=tail_wo_attached,
        source_style=source_style,
    )
    for ref in article_ranges:
        _append_ref_if_new(refs, seen_serialized, ref)

    tail_wo_range = remove_range_texts(tail_wo_attached)
    single_multi_refs = parse_multi_or_single_refs(
        law_name=law_name,
        tail=tail_wo_range,
        source_style=source_style,
    )
    for ref in single_multi_refs:
        _append_ref_if_new(refs, seen_serialized, ref)


# --------------------------------------------------
# 메인 ref 추출
# --------------------------------------------------
def extract_rule_references_from_text(text: str) -> List[Dict[str, Any]]:
    text = normalize_reference_text(text)
    refs: List[Dict[str, Any]] = []
    seen_serialized = set()

    for m in RE_TARGET_LAW_BLOCK.finditer(text):
        law_name = canonicalize_law_name(m.group(1))
        tail = norm(m.group(2))

        if law_name != TARGET_LAW_NAME:
            continue

        _process_tail(
            refs=refs,
            seen_serialized=seen_serialized,
            law_name=law_name,
            tail=tail,
            source_style="quoted",
        )

    for m in RE_TARGET_LAW_INLINE_HEAD.finditer(text):
        law_name = canonicalize_law_name(m.group(1))
        if law_name != TARGET_LAW_NAME:
            continue

        tail = extract_inline_tail(text, m.end())

        _process_tail(
            refs=refs,
            seen_serialized=seen_serialized,
            law_name=law_name,
            tail=tail,
            source_style="inline",
        )

    return refs


# --------------------------------------------------
# 목적조 보조 정보 생성
# --------------------------------------------------
def build_purpose_link(main_tree: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    article1 = find_article1(main_tree)
    if not article1:
        return None

    article_label = norm(article1.get("label", ""))
    article_text = collect_full_article_text(article1)

    return {
        "article_label": article_label,
        "article_text": article_text,
        "rule_references": extract_rule_references_from_text(article_text),
    }


# --------------------------------------------------
# 공통 payload 생성
# --------------------------------------------------
def extract_common_document_entity(
    *,
    file_name: str,
    source_path: str,
    document_type: str,
    main_tree: Dict[str, Any],
    supplementary: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    meta = extract_common_meta(
        file_name=file_name,
        source_path=source_path,
        document_type=document_type,
    )

    return {
        **meta,
        "main_tree": main_tree,
        "supplementary": supplementary or [],
        "purpose_link": build_purpose_link(main_tree),
    }