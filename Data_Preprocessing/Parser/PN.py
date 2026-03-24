import os
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

# --------------------------------------------------
# 경로 설정
# --------------------------------------------------
INPUT_DIR = r"C:\dev\FDA_Chatbot\DATA\o_data\행정규칙\고시"
OUT_DIR = r"C:\dev\FDA_Chatbot\DATA\parser_data\PN"
os.makedirs(OUT_DIR, exist_ok=True)


# --------------------------------------------------
# PN 문서 메타 생성
# --------------------------------------------------
def build_pn_metadata(file_name, source_path):
    return {
        "document_group": None,
        "document_type_code": "PN",
        "document_type_name_ko": "고시",
        "document_type_name_en": "Public Notice",
        "file_name": file_name,
        "source_path": source_path,
        "processed_at": datetime.now().isoformat(timespec="seconds")
    }


# --------------------------------------------------
# 본문 / 부칙 분리
# --------------------------------------------------
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


# --------------------------------------------------
# 단일 PDF 처리
# --------------------------------------------------
def process_one_pdf(pdf_path):

    file_name = os.path.basename(pdf_path)

    # ---------- line 추출 ----------
    lines = extract_lines(pdf_path)

    # ---------- 공통 전처리 ----------
    lines = preprocess_lines(lines)

    # ---------- 본문 / 부칙 분리 ----------
    main_lines, supp_lines = split_main_and_supplementary_lines(lines)

    # ---------- 본문 파싱 ----------
    main_tree, main_warnings = parse_main(main_lines)
    repair_split_notes_in_tree(main_tree)
    prune_empty_auto_nodes(main_tree)

    # ---------- 부칙 파싱 ----------
    supplementary = parse_supplementary(supp_lines) if supp_lines else []

    # ---------- 엔티티 추출 ----------
    entity_payload = extract_common_document_entity(
        file_name=file_name,
        source_path=pdf_path,
        document_type="고시",
        main_tree=main_tree,
        supplementary=supplementary,
    )

    # ---------- warning ----------
    warnings = main_warnings
    warning_summary = summarize_warnings(warnings)

    # ---------- 메타 ----------
    metadata = build_pn_metadata(file_name, pdf_path)

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

    # ---------- 저장 ----------
    out_path = os.path.join(
        OUT_DIR,
        os.path.splitext(file_name)[0] + ".pn.struct.json"
    )

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("saved:", out_path, f"(warnings={len(warnings)})", warning_summary)


# --------------------------------------------------
# 전체 처리
# --------------------------------------------------
def process_all():

    pdfs = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith(".pdf")]

    if not pdfs:
        print("no pdf:", INPUT_DIR)
        return

    pdfs.sort()

    print(f"[PN parsing start] total={len(pdfs)}")

    for fn in pdfs:
        try:
            process_one_pdf(os.path.join(INPUT_DIR, fn))
        except Exception as e:
            print("[ERROR]", fn, e)

    print("[PN parsing done]")


# --------------------------------------------------
# 실행
# --------------------------------------------------
if __name__ == "__main__":
    process_all()