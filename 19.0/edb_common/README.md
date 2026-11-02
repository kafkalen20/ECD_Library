# 에코두비즈 공통 (edb_common)

에코두비즈 내부 모듈들이 공유하는 **회사 공통 베이스** 모듈. 자체 업무 로직은 없고,
다른 EDB 모듈(`edb_helpdesk`, `edb_security` 등)이 깔고 쓰는 **공통 인프라**를 제공한다.

- **상태 색상 시스템**(디자인 토큰 + 배지 클래스) 단일 정의처
- **백오피스 UX 개선** 2종(리스트 세로 구분선, 엑셀식 방향키 이동)
- 설정 앱에 **"Ecodoobiz" 공통 설정 카테고리**(향후 공통 옵션 자리)

> 표준 Odoo(`base`, `web`)에만 의존하는 가볍고 도메인 중립적인 모듈이라, 어떤 EDB
> 모듈이든 이것을 `depends`로 깔 수 있다.

---

## 제공 기능

### 1. 상태 색상 시스템 — `static/src/css/status_colors.css`
EDB 전 모듈에서 쓰는 상태 배지/라벨 색을 **한 곳에서 정의**한다(여기만 바꾸면 전체 반영).
- `:root`에 **12색** CSS 변수 정의 — 시스템 6색(aubergine/teal/green/yellow/red/gray) +
  커스텀 6색(blue/navy/violet/orange/coral/lightgray). 색마다 base/`-on`(글자)/`-weak`(약배경)/
  `-emphasis`(강조글자)/`-line`(테두리) 변수 세트 제공.
- 색마다 **3가지 배지 변형** 유틸 클래스(Odoo `.badge`와 함께 사용):
  - STRONG `.edb-c-<색>` (진한 배경+대비 글자)
  - WEAK `.edb-c-<색>-weak` (연한 배경+진한 글자)
  - OUTLINE `.edb-c-<색>-outline` (흰 배경+색 테두리)
  - 예: `<span class="badge edb-c-blue">...</span>`

### 2. 리스트 세로 구분선 — `static/src/css/list_vertical_lines.css`
백오피스 리스트 테이블의 각 셀에 오른쪽 `1px` 경계선을 넣어 **엑셀 같은 세로 격자**를
만든다. 첫 열(선택 체크박스)과 마지막 열(옵션 토글)은 경계선 제외.

### 3. 엑셀식 방향키 이동 — `static/src/js/list_arrow_nav.js`
`ListRenderer`를 패치해 **모든 편집 가능 리스트**(o2m 라인 등)에서:
- **↑ / ↓** : 같은 열의 위/아래 편집행으로 이동(섹션/메모행은 건너뜀)
- **← / →** : 같은 행의 이전/다음 셀로 이동(Tab 대용). 단 입력 텍스트 **커서가 맨 앞(←)/
  맨 끝(→)** 일 때만 이동 — 그 외엔 셀 안에서 커서만 움직임.
- textarea·Tab·m2o 자동완성 드롭다운 열림 상태는 기존 동작 보존.

---

## 모델 / 설정

- **`res.config.settings`**(상속) — 현재 **필드 없음**. 설정 앱에 `Ecodoobiz > 공통 설정`
  카테고리만 등록하는 **빈 플레이스홀더**(향후 공통 `config_parameter` 옵션을 여기에 추가).
  - 뷰: `views/res_config_settings_views.xml` — `base.res_config_settings_view_form` 상속,
    `<app name="edb_common">` 패널 추가.

---

## 구조

```
edb_common/
├── __manifest__.py                 # depends: base, web / application: False
├── models/res_config_settings.py   # 설정 카테고리 플레이스홀더(필드 없음)
├── views/res_config_settings_views.xml
└── static/src/
    ├── css/status_colors.css        # 12색 상태 배지 시스템(단일 정의처)
    ├── css/list_vertical_lines.css  # 리스트 세로 구분선
    └── js/list_arrow_nav.js         # 엑셀식 방향키 셀 이동
```

---

## 의존성 / 라이선스

- Odoo: `base`, `web`
- OEEL-1
