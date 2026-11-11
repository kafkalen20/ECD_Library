#!/usr/bin/env python3
"""문서 라우팅 검사 — 엉뚱한 폴더/파일명/누락 표식을 막는다.

근거: docs/ROUTING.md 3절 (엉뚱한 폴더 방지 규칙).
로컬 훅(.claude/settings.json PostToolUse)과 CI(.github/workflows/docs-guard.yml)에서 실행.
표준 라이브러리만 사용. 오류가 있으면 종료코드 1.

사용:
  python3 scripts/check_docs.py            # docs/ 전체 검사
"""
import datetime
import os
import re
import subprocess
import sys

DOCS = "docs"

# 내용 시그니처 → 이 표식이 있으면 이 폴더에만 있어야 한다
SIGNATURES = [
    ("## 5 Whys", "issues", "장애기록(5 Whys) 내용"),
    ("## 기각한 대안", "decisions", "ADR(기각한 대안) 내용"),
]

FILENAME_RULES = {
    "decisions": re.compile(r"^\d{4}-.+\.md$"),
    "issues": re.compile(r"^\d{4}-\d{2}-\d{2}-.+\.md$"),
    "delivery": re.compile(r"^\d{4}-\d{2}-\d{2}-.+\.md$"),
}

REQUIRED_MARKERS = {
    "decisions": ["status:"],
    "issues": ["owner:", "## 5 Whys"],
    "delivery": ["to:", "## 가정한 것"],
}

# 현황(docs/status.md) = "지금 할 일만". 경과 기록으로 변질되는 것을 길이로 막는다.
STATUS_FILE = os.path.join(DOCS, "status.md")
STATUS_WARN_LINES = 20
STATUS_MAX_LINES = 40
STATUS_MAX_LINE_CHARS = 300

# 요구사항 추적표: 번호 체계는 프로젝트마다 달라 형식은 검사하지 않는다 → 빈 번호·중복만 오류, 상태 값은 경고.
TRACE_FILE = os.path.join(DOCS, "requirements", "trace.md")
REQ_STATES = {"요청", "분석", "개발", "시험", "반영", "보류", "취소"}

# 양식 예시 자리표시자 — 그대로 두면 "채운 척" 통과하므로 전달 문서에선 오류
PLACEHOLDER = re.compile(r"<예[:：]?[^>]*>")

# 인계(handoff)는 임시 문서 — 완료됐거나 오래 안 고친 것은 정리 안내(경고).
HANDOFF_STALE_DAYS = 30

# 날짜 꼬리표(date·created·updated)는 반드시 YYYY-MM-DD (docs/CLAUDE.md).
# 6자리 축약(260915)·점표기(2026.09.04) 등을 그 자리서 차단.
DATE_FIELD = re.compile(r"^(date|created|updated):[ \t]*(.+?)[ \t]*$", re.M)
DATE_OK = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# 목차(README) 등록을 확인할 폴더 (handoff=임시·delivery=발송물이라 제외)
INDEX_FOLDERS = ("decisions", "issues", "guides", "project", "design", "requirements")

SKIP_FILES = {"README.md", "CLAUDE.md", "ROUTING.md"}


def top_folder(relpath):
    """docs/<folder>/... → <folder>"""
    parts = relpath.split(os.sep)
    return parts[1] if len(parts) > 2 else None


def section_body(text, heading):
    """'## heading' 아래 다음 '## ' 전까지의 실내용 줄(빈 줄·주석 제외)."""
    m = re.search(rf"^{re.escape(heading)}[ \t]*$", text, re.M)
    if not m:
        return []
    body = re.split(r"^## ", text[m.end():], maxsplit=1, flags=re.M)[0]
    body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    return [ln for ln in body.splitlines() if ln.strip()]


def check_status(errors, warnings):
    if not os.path.isfile(STATUS_FILE):
        return
    with open(STATUS_FILE, encoding="utf-8") as f:
        lines = f.read().splitlines()
    n = len(lines)
    if n > STATUS_MAX_LINES:
        errors.append(
            f"{STATUS_FILE}: {n}줄 — 상한 {STATUS_MAX_LINES}줄 초과. "
            "지금 할 일만 남기고 경과는 handoff/·PR 로 옮기세요."
        )
    elif n > STATUS_WARN_LINES:
        warnings.append(f"{STATUS_FILE}: {n}줄 — 권장 {STATUS_WARN_LINES}줄 초과 (차단 {STATUS_MAX_LINES}줄).")
    for i, ln in enumerate(lines, 1):
        if len(ln) > STATUS_MAX_LINE_CHARS:
            errors.append(
                f"{STATUS_FILE}:{i}: 한 줄 {len(ln)}자 — 상한 {STATUS_MAX_LINE_CHARS}자 초과. "
                "한 줄 요약 + 링크로 줄이세요."
            )


def check_trace(errors, warnings):
    if not os.path.isfile(TRACE_FILE):
        return
    with open(TRACE_FILE, encoding="utf-8") as f:
        lines = f.read().splitlines()
    seen = {}
    for i, ln in enumerate(lines, 1):
        if not ln.startswith("|"):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        first = cells[0]
        if first == "번호" or (first and set(first) <= set("-: ")):
            continue  # 헤더·구분선
        if not first:
            errors.append(f"{TRACE_FILE}:{i}: 요구 번호가 비어 있음.")
            continue
        if first in seen:
            errors.append(f"{TRACE_FILE}:{i}: 요구 번호 {first} 중복 (첫 줄 {seen[first]}). 번호는 재사용하지 않는다.")
        seen.setdefault(first, i)
        state = cells[-1] if len(cells) >= 7 else ""
        if state not in REQ_STATES:
            warnings.append(
                f"{TRACE_FILE}:{i}: {first} 상태 '{state}' — {'/'.join(sorted(REQ_STATES))} 중 하나로."
            )


def check_handoff_stale(rel, text, warnings):
    if re.search(r"^status:[ \t]*완료", text, re.M):
        warnings.append(f"{rel}: status 완료 인계 — 남은 지식은 decisions/issues/guides/project 로 옮기고 삭제하세요.")
        return
    m = re.search(r"^updated:[ \t]*(\d{4}-\d{2}-\d{2})[ \t]*$", text, re.M)
    if not m:
        return
    try:
        days = (datetime.date.today() - datetime.date.fromisoformat(m.group(1))).days
    except ValueError:
        return
    if days > HANDOFF_STALE_DAYS:
        warnings.append(f"{rel}: {days}일째 안 고친 인계 — 아직 진행 중인지 확인하고, 끝났으면 정리하세요.")


def check_git_tracked(warnings):
    """docs/ 가 git 밖이면 hook·CI 검사가 사실상 안 먹힌다 (공유·버전 비교 불가)."""
    try:
        inside = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"],
                                capture_output=True, text=True).stdout.strip() == "true"
        # 폴더 자체(docs/) 또는 핵심 파일(docs/*.md 처럼 파일 단위로 뺀 경우)이 ignore 되는지
        probes = [DOCS] + [p for p in (os.path.join(DOCS, "README.md"), STATUS_FILE) if os.path.exists(p)]
        ignored = inside and any(
            subprocess.run(["git", "check-ignore", "-q", p]).returncode == 0 for p in probes)
    except OSError:
        return
    if not inside:
        warnings.append(f"{DOCS}/: git 저장소 밖 — 문서 공유·이력·자동검사가 안 됩니다. 레포 안에서 git 으로 관리하세요.")
    elif ignored:
        warnings.append(f"{DOCS}/: .gitignore 로 (일부) 제외됨 — 문서가 공유·검사되지 않습니다.")


def main():
    if not os.path.isdir(DOCS):
        print(f"(skip) {DOCS}/ 없음")
        return 0

    errors, warnings = [], []
    index_path = os.path.join(DOCS, "README.md")
    index_text = ""
    if os.path.isfile(index_path):
        with open(index_path, encoding="utf-8") as f:
            index_text = f.read()

    for root, _, files in os.walk(DOCS):
        if "_templates" in root.split(os.sep):
            continue
        for name in files:
            if not name.endswith(".md"):
                continue
            path = os.path.join(root, name)
            rel = os.path.relpath(path, ".")
            folder = top_folder(os.path.relpath(path, "."))
            with open(path, encoding="utf-8") as f:
                text = f.read()

            # 1) 내용 시그니처가 엉뚱한 폴더에 있는지
            for marker, must_folder, label in SIGNATURES:
                if marker in text and folder != must_folder and name not in SKIP_FILES:
                    errors.append(
                        f"{rel}: {label}이(가) '{folder or '루트'}'에 있음 → "
                        f"'{must_folder}/'로 옮기세요."
                    )

            if name in SKIP_FILES:
                continue

            # 2) 파일명 규칙
            rule = FILENAME_RULES.get(folder)
            if rule and not rule.match(name):
                hint = "NNNN-제목.md" if folder == "decisions" else "YYYY-MM-DD-무엇.md"
                errors.append(f"{rel}: 파일명 규칙 위반 → '{hint}' 형식이어야 함.")

            # 3) 필수 표식
            for marker in REQUIRED_MARKERS.get(folder, []):
                if marker not in text:
                    errors.append(f"{rel}: 필수 표식 누락 → '{marker}' 이(가) 있어야 함.")

            # 3.5) 날짜 형식 (YYYY-MM-DD 강제)
            #   숫자 없는 값(미상·yyyy-mm-dd·<담당자>·TBD)은 자리표시로 보고 통과.
            #   숫자가 있으면(260915·2026.09.04 등) 반드시 YYYY-MM-DD여야 함.
            for m in DATE_FIELD.finditer(text):
                field, val = m.group(1), m.group(2)
                if not any(c.isdigit() for c in val):
                    continue
                if not DATE_OK.match(val):
                    errors.append(
                        f"{rel}: '{field}: {val}' 날짜 형식 위반 → 'YYYY-MM-DD' 여야 함 (docs/CLAUDE.md)."
                    )

            # 3.6) 전달 문서: '## 가정한 것' 이 비었거나 양식 예시(<예: ...>)가 그대로면 안 됨 (없으면 "없음")
            if folder == "delivery":
                assumed = section_body(text, "## 가정한 것")
                if "## 가정한 것" in text and not assumed:
                    errors.append(f"{rel}: '## 가정한 것' 이 비어 있음 → 가정을 적거나 '없음' 이라고 쓰세요.")
                elif any(PLACEHOLDER.search(ln) for ln in assumed):
                    errors.append(f"{rel}: '## 가정한 것' 에 양식 예시(<예: ...>)가 그대로 있음 → 실제 가정으로 바꾸세요.")
                if re.search(r"^to:[ \t]*(<.*>)?[ \t]*(#.*)?$", text, re.M):
                    errors.append(f"{rel}: 'to:' 받는 사람이 비었거나 자리표시자(<...>) 그대로임.")

            # 3.7) 인계 정리 안내 (경고)
            if folder == "handoff":
                check_handoff_stale(rel, text, warnings)

            # 4) 목차 등록 (경고)
            if folder in INDEX_FOLDERS and name not in index_text:
                warnings.append(f"{rel}: docs/README.md 목차에 등록되지 않음.")

    check_status(errors, warnings)
    check_trace(errors, warnings)
    check_git_tracked(warnings)

    for w in warnings:
        print(f"⚠️  {w}")
    for e in errors:
        print(f"❌ {e}")

    if errors:
        print(f"\n검사 실패: {len(errors)}건. docs/ROUTING.md 3절 참고.")
        return 1
    print(f"✅ 문서 배치 OK{' (경고 %d건)' % len(warnings) if warnings else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
