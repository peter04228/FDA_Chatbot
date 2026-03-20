import os
import re
from typing import Dict, Any, List, Optional


# --------------------------------------------------
# 기본 유틸
# --------------------------------------------------
def norm(s: str) -> str:
    if s is None:
        return ""
    s = s.replace("\u00A0", " ")
    s = s.replace("\ufeff", "")
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


# --------------------------------------------------
# 파일명 / 제목 정리
# --------------------------------------------------
RE_FILE_EXT = re.compile(r"\.pdf$", re.IGNORECASE)
RE_TRAILING_META_PARENS = re.compile(
    r"(?:\((?:식품의약품안전처예규|식품의약품안전처고시|제\d+호|\d{8})\))+$"
)
RE_DOC_NO = re.compile(r"\(제\s*([0-9]+)\s*호\)")
RE_EFFECTIVE_YYYYMMDD = re.compile(r"\((20\d{2})(\d{2})(\d{2})\)")
RE_ISSUING_BODY = re.compile(r"\((식품의약품안전처)(?:예규|고시)\)")


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


# --------------------------------------------------
# 규정 참조 파싱
# --------------------------------------------------
RE_LAW_BLOCK = re.compile(r"「([^」]+)」\s*([^「」]*)")

RE_SINGLE_REF = re.compile(
    r"제\s*(\d+)\s*조"
    r"(?:\s*의\s*(\d+))?"
    r"(?:\s*제\s*(\d+)\s*항)?"
    r"(?:\s*제\s*(\d+)\s*호)?"
)

RE_RANGE_REF = re.compile(
    r"제\s*(\d+)\s*조"
    r"(?:\s*의\s*(\d+))?"
    r"(?:\s*제\s*(\d+)\s*항)?"
    r"\s*부터\s*"
    r"제\s*(\d+)\s*조"
    r"(?:\s*의\s*(\d+))?"
    r"(?:\s*제\s*(\d+)\s*항)?"
    r"\s*까지"
)

RE_CONNECTOR_SPLIT = re.compile(r"\s*(?:,|및|또는|및\s+제|또는\s+제)\s*")
RE_TRAILING_PURPOSE_END = re.compile(
    r"(에\s*따라.*|에\s*의해.*|에\s*의하여.*|에\s*관한.*|을\s*위한.*|을\s*목적으로.*)$"
)

EXCLUDE_LAW_NAMES = {
    "같은 법",
    "이 법",
    "동법",
    "같은 영",
    "이 영",
    "동영",
    "같은 규칙",
    "이 규칙",
    "같은 고시",
    "이 고시",
    "같은 예규",
    "이 예규",
    "같은 규정",
    "이 규정",
}


def build_rule_entity_id(
    law_name: str,
    article_no: Optional[str],
    paragraph_no: Optional[str],
    item_no: Optional[str],
    subitem_no: Optional[str],
) -> str:
    parts = ["rule"]

    if article_no:
        parts.append(str(article_no))
    if paragraph_no:
        parts.append(str(paragraph_no))
    if item_no:
        parts.append(str(item_no))
    if subitem_no:
        parts.append(str(subitem_no))

    return "_".join(parts)


def build_single_ref(
    law_name: str,
    article_no: Optional[str],
    article_sub_no: Optional[str],
    paragraph_no: Optional[str],
    item_no: Optional[str],
    raw: str,
) -> Dict[str, Any]:
    full_article_no = article_no
    if article_no and article_sub_no:
        full_article_no = f"{article_no}의{article_sub_no}"

    return {
        "type": "single",
        "law_name": law_name,
        "article_no": full_article_no,
        "paragraph_no": paragraph_no,
        "item_no": item_no,
        "subitem_no": None,
        "raw": norm(raw),
        "entity_id": build_rule_entity_id(
            law_name=law_name,
            article_no=full_article_no,
            paragraph_no=paragraph_no,
            item_no=item_no,
            subitem_no=None,
        ),
    }


def cleanup_tail_for_reference_parsing(tail: str) -> str:
    tail = norm(tail)
    tail = RE_TRAILING_PURPOSE_END.sub("", tail)
    tail = norm(tail)
    return tail


def parse_single_ref_text(law_name: str, ref_text: str) -> Optional[Dict[str, Any]]:
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
        raw=ref_text,
    )


def parse_range_refs(law_name: str, tail: str) -> List[Dict[str, Any]]:
    results = []

    for m in RE_RANGE_REF.finditer(tail):
        start_article = m.group(1)
        start_article_sub = m.group(2)
        start_paragraph = m.group(3)

        end_article = m.group(4)
        end_article_sub = m.group(5)
        end_paragraph = m.group(6)

        start_full = start_article
        if start_article_sub:
            start_full = f"{start_article}의{start_article_sub}"

        end_full = end_article
        if end_article_sub:
            end_full = f"{end_article}의{end_article_sub}"

        results.append({
            "type": "range",
            "law_name": law_name,
            "raw": norm(m.group(0)),
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
        })

    return results


def remove_range_texts(tail: str) -> str:
    return norm(RE_RANGE_REF.sub(" ", tail))


def parse_multi_or_single_refs(law_name: str, tail: str) -> List[Dict[str, Any]]:
    tail = cleanup_tail_for_reference_parsing(tail)
    if not tail:
        return []

    parts = RE_CONNECTOR_SPLIT.split(tail)
    parts = [norm(p) for p in parts if norm(p)]

    singles = []
    seen = set()

    for part in parts:
        # 연결어 split 결과가 "44조"처럼 깨지는 경우 방지용 보정은 하지 않고,
        # 현재 문서 패턴 기준 "제44조" 형태를 가정
        single = parse_single_ref_text(law_name, part)
        if not single:
            # fullmatch 실패 시 내부에 single ref가 하나라도 있으면 부분 매칭 허용
            m = RE_SINGLE_REF.search(part)
            if not m:
                continue
            single = build_single_ref(
                law_name=law_name,
                article_no=m.group(1),
                article_sub_no=m.group(2),
                paragraph_no=m.group(3),
                item_no=m.group(4),
                raw=m.group(0),
            )

        key = (
            single["law_name"],
            single["article_no"],
            single["paragraph_no"],
            single["item_no"],
        )
        if key in seen:
            continue
        seen.add(key)
        singles.append(single)

    if not singles:
        return []

    if len(singles) == 1:
        return singles

    return [{
        "type": "multi",
        "law_name": law_name,
        "raw": tail,
        "children": singles,
        "entity_id": build_rule_entity_id(
            law_name=law_name,
            article_no="multi",
            paragraph_no=None,
            item_no=None,
            subitem_no=None,
        ),
    }]


def extract_rule_references_from_text(text: str) -> List[Dict[str, Any]]:
    text = norm(text)
    refs = []
    seen_serialized = set()

    for m in RE_LAW_BLOCK.finditer(text):
        law_name = norm(m.group(1))
        if not law_name or law_name in EXCLUDE_LAW_NAMES:
            continue

        tail = norm(m.group(2))
        if not tail.startswith("제"):
            continue

        # 1) range 먼저
        range_refs = parse_range_refs(law_name, tail)
        for ref in range_refs:
            key = (
                ref["type"],
                ref["law_name"],
                ref.get("start_article_no"),
                ref.get("end_article_no"),
                ref.get("start_paragraph_no"),
                ref.get("end_paragraph_no"),
            )
            if key not in seen_serialized:
                seen_serialized.add(key)
                refs.append(ref)

        # 2) range 제거 후 single/multi
        tail_wo_range = remove_range_texts(tail)
        single_multi_refs = parse_multi_or_single_refs(law_name, tail_wo_range)

        for ref in single_multi_refs:
            if ref["type"] == "single":
                key = (
                    ref["type"],
                    ref["law_name"],
                    ref.get("article_no"),
                    ref.get("paragraph_no"),
                    ref.get("item_no"),
                )
            else:
                child_keys = tuple(
                    (
                        ch.get("article_no"),
                        ch.get("paragraph_no"),
                        ch.get("item_no"),
                    )
                    for ch in ref.get("children", [])
                )
                key = (ref["type"], ref["law_name"], child_keys)

            if key not in seen_serialized:
                seen_serialized.add(key)
                refs.append(ref)

    return refs


def choose_primary_rule_reference(rule_references: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not rule_references:
        return None

    def score(ref: Dict[str, Any]) -> int:
        law_name = norm(ref.get("law_name", ""))
        ref_type = ref.get("type")
        s = 0

        if "의약품 등의 안전에 관한 규칙" in law_name:
            s += 100

        if law_name.endswith(("규칙", "고시", "예규", "규정", "지침", "기준")):
            s += 20
        elif law_name.endswith(("법", "시행령")):
            s += 5

        if ref_type == "single":
            s += 10
        elif ref_type == "multi":
            s += 7
        elif ref_type == "range":
            s += 6

        if ref.get("article_no"):
            s += 3
        if ref.get("paragraph_no"):
            s += 1

        if ref_type == "multi":
            s += min(len(ref.get("children", [])), 5)

        return s

    return sorted(rule_references, key=score, reverse=True)[0]


# --------------------------------------------------
# 문서 엔티티 생성
# --------------------------------------------------
def build_document_entity(
    document_type_name: str,
    title: str,
    anchor_basis: Optional[str],
    anchor_confidence: str = "high",
) -> Dict[str, Any]:
    entity_type_map = {
        "예규": "administrative_rule",
        "고시": "public_notice",
        "행정규칙": "administrative_rule",
        "공고": "public_notice",
    }

    return {
        "entity_type": entity_type_map.get(document_type_name, "document"),
        "name": norm(title),
        "anchor_basis": anchor_basis,
        "anchor_confidence": anchor_confidence,
    }


# --------------------------------------------------
# 공통 엔티티 추출 메인
# --------------------------------------------------
def extract_common_document_entity(
    *,
    file_name: str,
    source_path: str,
    document_type: str,
    main_tree: Dict[str, Any],
    supplementary: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    title = clean_title_from_filename(file_name)
    issuing_body = extract_issuing_body_from_filename(file_name)
    document_no = extract_doc_no_from_filename(file_name)
    effective_date = extract_effective_date_from_filename(file_name)

    article1 = find_article1(main_tree)

    purpose_link = None
    document_entity = build_document_entity(
        document_type_name=document_type,
        title=title,
        anchor_basis=article1.get("label") if article1 else None,
        anchor_confidence="high" if article1 else "low",
    )

    if article1:
        article_label = norm(article1.get("label", ""))
        article_text = norm(article1.get("text", ""))
        rule_references = extract_rule_references_from_text(article_text)
        primary_rule_reference = choose_primary_rule_reference(rule_references)

        purpose_link = {
            "article_label": article_label,
            "article_text": article_text,
            "rule_references": rule_references,
            "primary_rule_reference": primary_rule_reference,
        }

    return {
        "file_name": file_name,
        "source_path": source_path,
        "document_type": document_type,
        "title": title,
        "issuing_body": issuing_body,
        "document_no": document_no,
        "effective_date": effective_date,
        "document_entity": document_entity,
        "purpose_link": purpose_link,
    }