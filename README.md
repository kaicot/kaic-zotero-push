# kaic-zotero-push

문서의 참고문헌을 로컬에서 추출·정규화하고 Zotero 기존 항목과 중복을 확인한 뒤,
사용자가 미리보기를 명시적으로 승인한 경우에만 **Zotero 개인 라이브러리**에 신규
서지 메타데이터를 등록하는 Codex/에이전트 스킬입니다.

## 핵심 안전 원칙

- 요청이 "바로 등록"이어도 먼저 미리보기를 생성합니다.
- 입력 파일, 매니페스트, 개인 라이브러리, 컬렉션 키가 모두 같을 때만 승인이
  유효합니다.
- 기존 항목을 수정·병합·삭제하지 않습니다.
- 원문 문서와 PDF를 Zotero Storage에 업로드하지 않습니다.
- API 키는 Windows Credential Manager에만 저장하며 URL·파일·로그·영수증에
  기록하지 않습니다.
- 생성 응답만으로 성공 처리하지 않고 항목을 다시 조회해 검증합니다.
- 부분 성공 시 성공 항목을 삭제하지 않고 실패·미검증 항목만 안전하게 재개합니다.

## 지원 기능

- `.docx`, `.xlsx`, `.csv`, `.md`, `.txt`, 텍스트형 `.pdf` 추출
- 문단·목록·표·페이지/블록 단위 원문 위치 추적
- APA/Vancouver 계열 문장과 구조화된 표 우선 파싱
- DOI, PMID, ISBN, URL 및 제목·연도·제1저자 기반 중복 탐지
- 등록 예정 / 중복 제외 / 검토 필요 / 파싱 실패 미리보기
- Zotero Web API v3 개인 라이브러리 신규 항목 생성
- live Zotero 항목 템플릿 기반 필드 매핑
- 50건 이하 배치, 쓰기 토큰, 항목별 부분 실패 처리
- 생성 항목 재조회 검증과 JSON 영수증
- 검증 완료 항목을 다시 만들지 않는 안전 재개

## 요구 환경

- Windows 10/11
- Python 3.12 이상
- [uv](https://docs.astral.sh/uv/)
- Zotero 계정과 전용 Web API 키
- Zotero 조회·등록 시 인터넷 연결

## 설치

```powershell
git clone https://github.com/kaicot/kaic-zotero-push.git
cd kaic-zotero-push
uv sync
uv run kaic-zotero-push --help
```

에이전트 스킬 디렉터리에 설치할 때는 이 저장소 전체를 복제하거나 `SKILL.md`,
`agents/`, `references/`, Python 프로젝트 파일을 함께 복사해야 합니다.

## Zotero API 키 설정

1. Zotero 계정의 **Settings → Feeds/API → Create new private key**에서 이 스킬 전용
   키를 만듭니다.
2. 개인 라이브러리 읽기·쓰기만 허용합니다.
3. 파일 및 그룹 라이브러리 권한은 부여하지 않는 것을 권장합니다.
4. 아래 명령을 실행하고 숨김 프롬프트에 키를 붙여넣습니다.

```powershell
uv run kaic-zotero-push configure
```

API 키를 입력하거나 붙여넣는 동안에는 보안을 위해 글자나 별표가 화면에 표시되지
않습니다. 그대로 키를 입력한 뒤 `Enter`를 누르세요. PowerShell에서 `Ctrl+V`가
동작하지 않으면 마우스 오른쪽 버튼 또는 `Shift+Insert`로 붙여넣을 수 있습니다.
입력이 완료되면 "API 키와 권한을 확인하는 중"이라는 메시지가 표시됩니다.

명령은 먼저 `GET /keys/current`로 계정과 권한을 확인한 뒤 Windows Credential
Manager에 저장합니다. 키 자체는 출력하지 않으며 명령줄 인자로도 받지 않습니다.

## 에이전트 자연어 사용법

파일을 첨부하거나 로컬 경로를 알려주고 다음처럼 요청합니다.

- "이 문서에 있는 논문들을 Zotero에 넣어줘."
- "이 참고문헌 목록을 `작업치료 연구` 컬렉션에 등록해줘."
- "중복은 빼고 Zotero에 추가해줘."
- "우선 무엇이 등록될지 확인만 해줘."
- "이전 실행에서 실패한 항목만 다시 처리해줘."

에이전트는 `SKILL.md`의 절차에 따라 미리보기를 보여주고 멈춥니다. 사용자가 그
미리보기를 승인한 뒤에만 승인 기록과 실제 쓰기를 수행합니다.

## CLI 사용법

### 미리보기

```powershell
uv run kaic-zotero-push preview "D:\문서\references.docx"

uv run kaic-zotero-push preview "D:\문서\references.xlsx" `
  --collection "작업치료 연구"
```

Zotero 연결 없이 로컬 추출·파싱만 확인하려면:

```powershell
uv run kaic-zotero-push preview "D:\문서\references.txt" --offline
```

오프라인 미리보기는 원격 중복 상태와 Zotero 사용자가 결합되지 않으므로 실제 등록
승인을 만들 수 없습니다.

### 승인과 등록

미리보기에 표시된 실행 폴더를 사용합니다.

```powershell
uv run kaic-zotero-push approve ".runs\20260820T010203.000000Z"
uv run kaic-zotero-push commit ".runs\20260820T010203.000000Z"
```

`approve`는 표시된 계획을 사용자가 실제로 승인한 뒤에만 실행해야 합니다.
`commit`은 유효한 `approval.json`이 없거나 대상이 바뀌면 중단됩니다.

### 부분 실행 재개

```powershell
uv run kaic-zotero-push resume ".runs\20260820T010203.000000Z"
```

재개는 이미 `created_verified`인 항목을 다시 만들지 않습니다. 생성 키는 받았지만
검증되지 않은 항목은 먼저 같은 키를 다시 조회하며, 실패 항목은 최신 중복 상태를
확인한 뒤에만 재평가합니다.

## 미리보기와 실행 아티팩트

기본 실행 경로는 `.runs/<run-id>/`입니다.

```text
.runs/<run-id>/
├── run.json
├── extracted.json
├── manifest.json
├── preview.md
├── approval.json
├── batches/
│   ├── batch-001.state.json
│   ├── batch-001.request.json
│   └── batch-001.response.redacted.json
└── receipt.json
```

`.runs/`에는 참고문헌 원문이 포함될 수 있어 Git에서 제외됩니다. 원본 파일 복사본과
HTTP 헤더는 저장하지 않습니다.

## 결과 상태

| 상태 | 의미 |
|---|---|
| `created_verified` | 생성 후 재조회 검증 완료 |
| `created_unverified` | 생성 응답은 받았으나 재조회 검증 미완료 |
| `duplicate_skipped` | 확정 중복으로 제외 |
| `needs_review` | 파싱 또는 중복 판정이 불확실 |
| `parse_failed` | 참고문헌 파싱 실패 |
| `write_failed` | Zotero 쓰기 실패 |
| `not_attempted` | 앞선 차단 오류로 미시도 |

최종 성공 수는 `created_verified` 수와 같습니다. 타임아웃과 응답 손실은 성공으로
간주하지 않습니다.

## 중복 정책

1. 정규화된 DOI 완전 일치
2. PMID 또는 ISBN 완전 일치
3. 정규화된 제목 + 발행연도 + 제1저자 일치
4. 높은 제목 유사도와 연도 또는 저자 근거

확정 중복은 자동 제외합니다. 의심 중복은 `needs_review`로 보내며 자동 등록하지
않습니다. 같은 입력을 재실행할 때도 최신 Zotero 항목을 다시 조회합니다.

## v0.1 제한

- `.hwp`, `.hwpx`, 스캔 PDF, 이미지 OCR 미지원
- 그룹 라이브러리 쓰기 미지원
- 기존 Zotero 항목 수정·병합·삭제 미지원
- 원문·PDF·첨부파일 업로드 미지원
- 누락 메타데이터의 생성형 추측 미지원
- 제목 검색 기반 외부 메타데이터 보강 미지원
- 동명 컬렉션 자동 선택 및 새 컬렉션 자동 생성 미지원

## 개발과 검증

```powershell
uv sync --dev
uv run ruff format --check .
uv run ruff check .
uv run basedpyright
uv run pytest
uv build
```

실제 Zotero 통합 검증은 별도 테스트 컬렉션과 전용 API 키를 사용하세요. 테스트가
만든 항목의 자동 삭제는 제공하지 않으며, 일반 실행은 Zotero 삭제 API를 호출하지
않습니다.

## 문서

- 에이전트 실행 계약: [`SKILL.md`](SKILL.md)
- 보안 정책: [`references/security-policy.md`](references/security-policy.md)
- Zotero API 계약:
  [`references/zotero-api-contract.md`](references/zotero-api-contract.md)
- 서지 매핑과 중복 정책:
  [`references/citation-mapping.md`](references/citation-mapping.md)
- 원 개발 명세:
  [`Zotero_문서레퍼런스_등록_스킬_개발명세서_v0.1.md`](Zotero_문서레퍼런스_등록_스킬_개발명세서_v0.1.md)

## 라이선스

MIT License
