---
paths:
  - "**/security/*"
  - "**/*.env"
  - "**/settings*.json"
---
# 보안 · 비밀정보 규칙

- 비밀번호 · API 키 · Secret · SSH Private Key · 인증 Token · 서버 IP를
  **코드/문서/커밋에 절대 넣지 않는다.** → 비밀번호 관리자(1Password 등)에.
- 접속 "방법·순서"만 `docs/guides/`에 적고, 실제 값은 "관리자에서 조회" 라고 위치만 가리킨다.
- ACL/보안그룹 변경은 그 이유를 PR 설명 또는 ADR에 남긴다.
- `.env` · `*.local.*` · secrets 파일은 `.gitignore` 되어 있는지 확인한다.
