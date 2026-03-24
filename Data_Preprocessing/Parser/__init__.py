"""
parser package

이 패키지는 식약처 법령/행정규칙 PDF를 구조화(JSON)하기 위한 파서 모음임.

[약어]
- ER : Enforcement Rules
    - 시행규칙
- AR : Administrative Rules
    - 행정규칙
  - IN : Instruction
      - 예규
  - PN : Public Notice
      - 고시

[핵심 파일 역할]

1. structure_engine.py
- 본문(main body) 구조 파싱 공통 엔진
- 조/항/호/목 구조를 트리 형태로 파싱
- 부칙은 처리하지 않음
- ER / IN / PN 등 여러 문서 유형에서 공통 사용

2. supplementary_engine.py
- 부칙(supplementary provisions) 전용 파싱 엔진
- '부칙' 이후 내용을 별도 구조로 파싱
- 본문 구조 엔진과 분리하여 독립적으로 사용

3. entity_common.py
- IN / PN 공통 엔티티 추출 로직
- 제1조(목적) 기반 규정 참조 추출
- 목적조에 등장하는 rule references 수집
- primary_rule_reference 선택
- IN / PN의 document_entity 생성에 활용

4. annex_common.py
- 본문에 annex_reference 에서 별표 수집

5. ER.py
- 시행규칙(ER) 전용 실행 파서
- structure_engine + supplementary_engine + annex_common 사용
- ER은 문서 자체가 주요 엔티티이므로 별도 entity extraction이 거의 필요 없음

6. IN.py
- 예규(IN) 전용 실행 파서
- structure_engine + supplementary_engine + entity_common 사용
- 본문/부칙 구조화 후 공통 엔티티 추출 수행

7. PN.py
- 고시(PN) 전용 실행 파서
- structure_engine + supplementary_engine + entity_common 사용
- 본문/부칙 구조화 후 공통 엔티티 추출 수행

8. er_annex.py
- 시행규칙(ER)에서 별표(annex) 문서 실행 파서
- structure_engine + 추가 사항 
- 별표 문서 구조화

[처리 흐름 개요]

1) PDF에서 line 추출
2) 전처리
3) 본문 / 부칙 분리
4) 본문은 structure_engine으로 파싱
5) 부칙은 supplementary_engine으로 파싱
6) IN / PN은 entity_common으로 엔티티 추출
7) 최종 JSON 저장

[엔티티 개념]
- ER:
    - 문서 자체가 주요 엔티티
- IN / PN:
    - 문서 메타정보는 source document 성격
    - 실제 연결 엔티티는 목적조에서 추출한 primary_rule_reference 기준으로 해석

[주의]
- structure_engine은 본문 전용임
- supplementary_engine은 부칙 전용임
- entity 추출 로직은 structure_engine 안에 넣지 않고 별도 모듈에서 관리함
"""