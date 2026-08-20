# 변경 이력

이 프로젝트는 [Semantic Versioning](https://semver.org/lang/ko/)을 따릅니다.

## [0.1.1] - 2026-08-20

### 수정

- `configure`가 숨김 입력 전에 무표시 동작과 PowerShell 붙여넣기 방법을 안내합니다.
- API 키 입력 직후 Zotero 검증이 진행 중임을 표시해 정지 상태로 오해하지 않게 합니다.
- API 키를 명령줄 인자로 받지 않아 셸 기록 노출 경로를 제거했습니다.

## [0.1.0] - 2026-08-20

### 추가

- DOCX, XLSX, CSV, Markdown, TXT, 텍스트형 PDF 추출
- 보수적 참고문헌 파싱과 원문 위치 추적
- DOI, PMID, ISBN, 제목·연도·제1저자 기반 중복 탐지
- 입력·매니페스트·개인 라이브러리·컬렉션 결합 승인
- Windows Credential Manager 기반 Zotero API 키 보관
- Zotero live 템플릿 기반 메타데이터 매핑
- 최대 50건 배치, 안정적인 쓰기 토큰, 부분 성공 처리
- 생성 항목 재조회 검증과 JSON 영수증
- 검증 완료 항목의 재생성을 막는 재개 흐름
- 영문 에이전트 스킬 지침과 한국어 README
