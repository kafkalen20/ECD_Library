# 에코두비즈 보안 (`edb_security`)

사용자 업무를 **막지 않는** 보안 기능을 모은 모듈. 두 부분으로 되어 있다.

- **A. 접속 이력** — 누가, 언제, 어떤 기기로 접속했는지 영구 기록하고 대시보드로 본다.
- **B. 보안 이벤트·탐지** — 로그인 성공/실패 등 보안 이벤트를 기록하고, 탐지 룰로 이상징후를 찾아 담당자에게 알린다.

막는 기능(2단계 인증 강제, 접속 조건, 연동 차단 등)은 이 모듈에 넣지 않고 `edb_security_auth`·`edb_security_api` 로 분리한다. 전체 구성은 저장소 루트 `README.md` 의 "보안 모듈 구성" 절을 본다.

> 이력: 2026-11 에 기존 `edb_security`(접속 이력)와 HLB 저장소에서 임시 개발하던 `ecodoo_security_monitor`(보안 모니터링)를 통합했다. 모델 `ecodoo.security.*` 는 `edb.security.*` 로, 설정 키 접두어 `ecodoo_security_monitor.` 는 `edb_security.` 로 바뀌었다.

---

## 메뉴 · 권한

메뉴 `보안 모니터링` (앱, `보안 감사자` 그룹만 보임)

| 메뉴 | 내용 |
|---|---|
| 접속 현황 | A 대시보드. "전체 보기"로 접속 내역 목록 |
| 이벤트 | B 보안 이벤트 목록 |
| 발동 이력 | B 탐지 룰 발동 기록 |
| 탐지 룰 | B 룰 설정 |

- 그룹 `보안 감사자`(`edb_security.group_security_monitor`)를 `base.group_system` 이 imply 한다.
- 접속 내역·보안 이벤트·발동 이력은 감사자 **읽기 전용**. 탐지 룰은 감사자가 수정 가능 (B3 참고).
- 접속 현황 대시보드와 엑셀 내보내기는 원시 SQL 집계라 ACL 을 타지 않으므로 `get_access_dashboard_data()` 첫 줄에서 감사자 여부를 검사한다.
- 통합 전에는 접속 내역을 **내부 사용자 전원**이 읽을 수 있었고(RPC·엑셀 경로), 로그인 실패 입력값을 평문으로 저장했다. 통합하면서 둘 다 고쳤다.

---

## A. 접속 이력

Odoo 코어의 `res.device` / `res.device.log` 는 세션·기기별 **마지막** 접속만 유지하고 주기적으로 정리한다. A 는 **접속마다 1행을 남기는 영구 감사 로그**를 추가한다.

### 기록 방식
- `res.device.log._update_device` 오버라이드. `_edb_should_log()` 로 게이팅: 최초 접속, 또는 마지막 동작 후 1시간 이상 쉬었다 재접속할 때만 1행. 로그인 사용자만.
- 동시 요청 중복(같은 세션·기기·분)은 부분 유니크 인덱스 + `ON CONFLICT DO NOTHING` 으로 막는다 (`init()`).
- 별도 writable 커서로 기록해 요청 트랜잭션이 롤백돼도 남는다.
- 원본 User-Agent 로 OS 계열·PC/모바일·브라우저(웨일, 삼성인터넷, 엣지 등)를 보정해 저장한다.
- **로그인 실패는 A 에 기록하지 않는다.** B 의 보안 이벤트(`login_failed`)에만 남고, 대시보드의 로그인 실패 KPI·목록은 보안 이벤트를 읽는다.

### 대시보드
KPI(오늘/WAU/MAU/로그인 실패), 추이·기기·시간대·요일 차트, 사용자별·미접속자 표, 최근 로그인 실패. 주/월/년 토글, 엑셀 내보내기(`GET /edb_security/device_access/export?period=...`, 5개 시트).

### 모델
- `edb.device.access` — 필드: `user_id`, `session_identifier`, `access_datetime`, `device`, `browser`, `access_detail`(원본 UA), `os_family`, `device_type`, `ip_address`, `event_type`(현재 `access` 만)
- `res.device.log`(상속) — `_update_device()` 오버라이드

### 보관 기간
시스템 매개변수 `edb_security.device_access_retention_days`(기본 365, `0` 이면 삭제 안 함). `@api.autovacuum` 이 매일 삭제한다. B 의 보안 이벤트 보관 기간(설정 화면 `보관 개월`)과는 별개다.

---

## B. 보안 이벤트 · 탐지

### B1. 무엇을 하는가

- 로그인 성공/실패를 `edb.security.event` 에 기록한다. 실패는 요청 트랜잭션이 롤백돼도 남도록 별도 커넥션으로 커밋한다 (`core/conn.py`).
- 1분 주기 cron(`_cron_evaluate`)이 탐지 룰을 평가해 `edb.security.rule.hit` 을 만든다.
- 심각도 `치명` 히트는 즉시 `mail.activity` 를 만든다 (담당자에게 메일 발송). 수신자는 룰의 `알림 대상`, 비어 있으면 보안 감사자 그룹 전원이다.
- 메뉴 `보안 모니터링` (접속 현황 / 이벤트 / 발동 이력 / 탐지 룰), 설정 화면에 수집 토글과 프리셋이 있다.
- 이벤트의 `detail`·`field_names` 는 저장 전에 개인정보 패턴(주민번호·이메일·전화·계좌)을 마스킹한다. 이름·주소는 패턴이 없어 걸러지지 않는다.
- 로그인 실패 문자열(`login`)은 실존 계정이면 평문, 아니면 `unknown:<12자>` 로 저장한다. ID 칸에 잘못 친 비밀번호가 평문으로 남지 않게 하려는 것이다. 12자는 `database.secret` 으로 만든 HMAC 이라 같은 입력은 같은 값이다 (R-01 집계 유지). `database.secret` 을 바꾸면 이후 값이 달라진다.

### B2. Phase 1 이 탐지하는 것과 탐지하지 않는 것

#### 탐지하는 것 (기본 룰 4개)

| 코드 | 내용 | 조건 | 심각도 | 통보 |
|---|---|---|---|---|
| R-01 | 계정별 로그인 실패 반복 | 같은 login 10분 내 5회 | 높음 | **없음 (아래 참고)** |
| R-01B | IP별 로그인 실패 반복 | 같은 IP 10분 내 30회 | 치명 | 즉시 활동 |
| R-02 | 관리자 신규 IP 로그인 | `base.group_system` 사용자가 이전에 본 적 없는 IP 로 성공 | 치명 | 즉시 활동 |
| R-03 | 관리자 업무시간 외 로그인 | 관리자 로그인이 업무시간(기본 KST 평일 09~19) 밖 | 치명 | 즉시 활동 |

#### 탐지하지 않는 것 (알려진 공백)

- **R-01 은 Phase 1 에서 능동 통보가 없다.** 심각도가 `높음` 이라 일일 다이제스트 대상인데 다이제스트가 Phase 2 다. 히트는 쌓이지만 누가 메뉴를 열어보기 전에는 아무도 모른다.
- **업무시간 내에 기존 IP 로 이뤄지는 계정 탈취는 4개 룰 중 어느 것도 탐지하지 않는다.** 실패 이벤트가 없으면 R-01/R-01B 가 침묵하고, 기존 IP 면 R-02 가, 업무시간 내면 R-03 이 침묵한다. "실패 N건 직후 성공" 상관 룰은 아직 없다.
- 사용자 변경(H-2)·모델 변경(H-5) 훅이 없어 **대량 비밀번호 변경, 계정 활성화, 메일 대기열 급증은 탐지되지 않는다.** 이벤트 유형 정의는 있지만 이를 기록하는 코드가 없다 (Phase 1 이 기록하는 유형은 로그인 성공/실패와 설정 변경뿐이다).
- **저강도 지속 공격은 탐지되지 않는다.** 임계가 10분당 5회인데 10분당 1회씩 며칠에 걸쳐 시도하면 히트 0건이다.
- 발동 이력의 확인/종결(`action_ack`/`action_close`)이 화면에 노출돼 있지 않다. 코드로만 상태를 바꿀 수 있어 히트는 사실상 `신규` 로 남는다.
- R-02·R-03 은 관리자만 본다. 일반 직원 계정 탈취는 R-01/R-01B 로만 걸린다.
- 보안 이벤트 파기 cron 이 없다. 보안 이벤트는 무기한 쌓인다 (Phase 2). 접속 이력(`edb.device.access`)은 A 의 보관 기간에 따라 삭제된다.
- 이벤트는 그 시점의 값만 담는다. 프록시 설정이 틀린 상태에서 쌓인 IP 는 사후에 바로잡을 수 없다 (`ip_trusted=False` 로 표시만 된다).

### B3. 직무 분리 한계

`base.group_system` 이 `보안 감사자` 그룹을 imply 한다. 따라서 **설정 권한 관리자가 곧 보안 감사자**다. Odoo 권한 모델상 루트 권한자는 어차피 자기에게 그룹을 부여할 수 있어, 열람 권한만 좁혀도 실효가 없다. 관리자를 감시 대상에서 분리해야 하는 고객사는 이 모듈과 별개의 감사자 체계(별도 시스템·별도 권한자)를 따로 두어야 한다. 이 모듈이 그 역할을 하지는 않는다.

**룰 수정 권한도 같은 그룹에 있다.** `security/ir.model.access.csv` 에서 `보안 감사자` 그룹은 `edb.security.rule` 에 `perm_write=1`, `perm_create=1` 이다 (이벤트·발동 이력은 읽기 전용). 따라서 이 그룹 보유자는 관리자 권한 없이도 룰을 비활성화하거나, `threshold_count` 를 크게 올리거나, `condition_domain` 을 바꿔 탐지를 무력화할 수 있다. **Phase 1 에서는 룰 레코드의 변경이 이벤트로 기록되지 않는다.** `models/security_rule.py` 에 `create`/`write`/`unlink` 오버라이드가 없고, 설계서가 요구한 "`edb.security.rule` 변경은 항상 기록"은 구현되지 않았다. 설정 화면의 수집 토글 변경만 `_log_toggle_change` 로 기록된다. 즉 탐지를 끈 흔적이 남지 않는다. Phase 2 선행 조건 6번이다. 그때까지의 완화책은 **`base.group_system` 보유자를 최소 인원으로 유지하는 것**뿐이다 — 감사자 그룹은 그것이 imply 하므로 별도로 통제할 수 없다. 룰 변경 이력이 필요하면 DB 수준 로그(`write_uid`/`write_date`, 서버 로그)에 의존한다. `write_uid`/`write_date` 는 마지막 변경만 보여 주므로 이력 대체로는 약하다.

### B4. 배포 체크리스트

#### B4.1 HLB (`common_hlb` 설치 DB): 메뉴 가시성

`common_hlb` 가 메뉴 노출 규칙을 통째로 바꾼다. 이 조치 없이 배포하면 **admin 을 포함해 아무에게도 `보안 모니터링` 메뉴가 보이지 않는다** (오류도 나지 않는다).

`config/addons_hlb/common_hlb/models/ir_ui_menu.py` 의 동작:

- `get_user_roots()` 를 오버라이드한다. 코어의 `그룹 기반 가시성` 대신, `user.access.role` 에 이 사용자로 `access_level in ('view','edit')` 인 행이 있는 메뉴와 그 **모든 상위 메뉴**(`parent_path` 로 계산)만 루트로 돌려준다.
- `_load_menus_blacklist()` 를 오버라이드한다. 전체 메뉴에서 위 집합을 뺀 나머지를 전부 숨긴다. 즉 **자식 메뉴도 각각 `user.access.role` 행이 있어야 한다.**
- 슈퍼유저·`base.group_system` 예외가 없다. `access_level='none'` 은 없는 것과 같다.
- `user.access.role` 행은 사용자의 `role_id`(`access.role`)를 지정하거나 바꿀 때, 또는 그 롤에 `access.role.line` 이 추가될 때만 만들어진다. 새 모듈을 설치해도 기존 사용자에게는 자동으로 생기지 않는다.

HLB 운영 복제본(2026-09 기준)에 모듈을 설치해 직접 확인한 결과 (그룹 설정 권한 + 롤 `ERP개발자` 사용자):

| 추가한 `user.access.role` 행 | 루트 `보안 모니터링` | 자식 메뉴 3개 |
|---|---|---|
| 없음 | 안 보임 | 숨김 |
| 루트 메뉴 1행만 | 보임 | **전부 숨김 (빈 앱)** |
| 자식 1행만 | 보임 | 그 1개만 보임 |
| 자식 3행 (이벤트, 발동 이력, 탐지 룰) | 보임 (루트는 상위 메뉴로 자동 포함) | 모두 보임 |

따라서 "행 1개 추가"로는 부족하다. **자식 메뉴마다** 행이 필요하다. 위 표는 통합 전(자식 3개) 기준이며, 통합 후에는 `접속 현황` 이 추가돼 **4개**(`접속 현황`, `이벤트`, `발동 이력`, `탐지 룰`)다.

조치 절차:

1. 보안 감사자가 속한 `access.role` 에 `access.role.line` 4개를 추가한다 (메뉴: 접속 현황 / 이벤트 / 발동 이력 / 탐지 룰). 롤에 추가하면 그 롤의 모든 사용자에게 자동 전파된다 (복제본에서 사용자 1명 기준 +3행 확인).
2. 접근 수준은 이벤트·발동 이력은 `view`, 탐지 룰은 룰을 직접 편집·추가해야 하면 `edit`. (`common_hlb` 의 form 컨트롤러는 `edit` 가 아니면 생성·삭제·복제·보관과 액션 메뉴를 숨긴다.)
3. 롤이 없거나 개인 예외가 있는 사용자는 사용자 폼의 `User Access Role` 탭에서 같은 4행을 추가한다.
4. 대상 사용자로 로그인해 메뉴가 보이는지, 브라우저를 새로고침해도 유지되는지 확인한다 (메뉴는 `load_menus` 가 ormcache 되므로 반영 전에 로그아웃/로그인이 필요할 수 있다).
5. 모듈을 업그레이드해도 메뉴 xmlid 는 유지되므로 1회만 하면 된다.

#### B4.2 알림 대상과 실제 활동 확인

`치명` 히트는 룰의 `알림 대상` 사용자에게, 비어 있으면 `보안 감사자` 그룹 전원(설정 권한 관리자 포함)에게 `mail.activity` 를 만든다. 활동 생성이 담당자에게 메일을 보내므로 **발신 메일 서버가 설정돼 있어야** 통보가 도달한다. 설치 후 다음으로 확인한다.

1. 설정 화면의 `보안 모니터링` 앱에서 수집 토글(`hook_login`, `detect_engine`, `notify_critical`)이 켜져 있는지 본다.
2. `탐지 룰` 에서 임시 룰을 만든다: 종류 `임계 집계`, 대상 `로그인 실패`, 그룹 `전역`, 임계 1, 심각도 `치명`, 알림 대상 = 확인할 담당자.
3. 로그아웃 후 틀린 비밀번호로 로그인을 1회 시도한다.
4. `보안 이벤트` 에 `로그인 실패` 행이 생겼는지, 1분 안에 `발동 이력` 에 히트가 생겼는지, 담당자의 활동/메일이 도착했는지 본다.
5. 확인 후 임시 룰을 삭제(또는 비활성화)한다.

히트가 안 생기면 순서대로 본다: `ir.cron` "보안 모니터링: 이상징후 탐지" 활성 여부 → `detect_engine` 토글 → 이벤트가 실제로 쌓이는지(`hook_login`).

#### B4.3 `--proxy-mode` 와 `X-Forwarded-Host`

이 모듈은 코어와 같은 기준으로 IP 를 신뢰한다. **`--proxy-mode`(`proxy_mode = True`)와 요청의 `X-Forwarded-Host` 헤더가 모두 있어야** 코어가 `REMOTE_ADDR` 을 실제 클라이언트 IP 로 치환한다. 리버스 프록시(nginx 등)가 `X-Forwarded-For`·`X-Forwarded-Host` 를 넘기지 않으면 모든 요청이 프록시 IP 로 기록되어 **IP 기반 룰(R-01B, R-02)이 무의미해진다.** 히트의 `IP 신뢰` 가 꺼져 있으면 이 설정을 의심한다. Phase 1 은 이를 감지해 룰을 끄지 않는다 (Phase 2 선행 조건 2). 특히 R-02 는 전 사용자의 IP 가 같아지면 최초 1회 발동 후 영구히 침묵한다.

#### B4.4 업그레이드 검증

고객사 검증은 운영 복제본에서 `-u edb_security --test-enable --test-tags /edb_security` 로 한다. 테스트는 업무시간 설정을 스스로 고정하고 자기 이벤트만 세도록 만들어져, 이벤트가 쌓인 DB·튜닝된 DB 에서도 통과한다. `branch_hlb` 처럼 사용자 생성을 제약하는 모듈이 있어도 `tests/common.py` 가 처리한다. 다른 고객사에서 사용자 생성이 막히면 이 헬퍼를 확장한다. 현재 헬퍼(`create_user`)의 가정은 다음과 같다: `res.users` 에 `branch_id` 필드가 있으면 모델 **`res.branch`** 의 첫 레코드를 `branch_id` 로, 같은 값을 **`branch_ids`** (다대다)에도 넣는다. `branch_id` 가 있는데 대상 모델 이름이 `res.branch` 가 아니거나 `branch_ids` 가 없으면 테스트 setUp 에서 바로 실패한다. 테스트 전용 헬퍼라 운영 코드에는 영향이 없고, 실패는 즉시 드러난다.

#### B4.5 설치 직후 R-02 초기 알림

`base.group_system` 이 감사자 그룹을 imply 하므로 모든 관리자가 R-02 대상이다. **설치 직후 각 관리자의 첫 로그인마다 R-02(신규 IP)가 치명 활동을 하나씩 만든다.** 관리자가 3명이면 활동 3건이다 (수신자는 감사자 그룹 전원이라 각자 여러 건을 받는다). 버그가 아니라 정상 동작이다. 각 관리자의 IP 가 한 번 기록되면 이후 같은 IP 에서는 침묵한다. 알림을 처음 받은 담당자에게 미리 알려 두고, 본인 로그인이 맞는지 확인한 뒤 종결한다.

#### B4.6 로그인 실패 폭주

**측정 조건과 한계.** 아래 수치는 `odoo shell` 에서 `res.users._login` 을 단일 프로세스로 반복 호출해 얻었다. **로컬 DB 이고 HTTP 계층(werkzeug·세션·프록시)은 제외**했다. 원격 DB 에서는 실패 1건의 flush 가 왕복 여러 번(SET / SAVEPOINT / INSERT / RELEASE / COMMIT)이라 지연이 훨씬 커진다. 수치를 그대로 운영 기대치로 쓰지 말고, 운영과 같은 DB 위치에서 다시 재야 한다. 이 측정은 요청 처리량이 아니라 훅 자체의 비용만 보여 준다.

실측(전용 로컬 DB, 실패 800건 동시 16~40 스레드 포함): 실패 1건당 훅 오버헤드는 약 0.3~0.4ms, 풀 고갈·드롭 없음. 풀이 가득 찬 극단 상황에서도 예외는 호출자로 전파되지 않고 5초 백오프 후 큐에서 복구된다. 순차 300건(존재하지 않는 login)은 토글 끔 0.98ms/건, 켬 1.25ms/건이었다. 존재하는 계정에 틀린 비밀번호를 넣는 스프레이는 비밀번호 해시 검증이 건당 약 310ms 라 훅 비용이 묻힌다.

### B5. Odoo 17/18 백포트 작업지시서

아래는 통합 전 보안 모니터링 코드 기준으로 로컬의 17(`bauschlomb/odoo17-ee-bl`)·18(`odoo-18.0+e.20250109`) 코어 소스와 대조해 확인한 항목이다. **A 의 접속 이력 코드(`res.device.log` 훅, OWL 대시보드)는 대조하지 않았다** (`res.device.log` 는 17 에 없다 `[확인 필요]`). 1~8 은 교차 검증에서 확정된 8개이고, 9~10 은 이번에 코드를 대조하다 추가로 발견했다.

| # | 위치 | 19 | 17 / 18 | 할 일 |
|---|---|---|---|---|
| 1 | `__manifest__.py` `version` | `19.0.2.0.0` | 17: `17.0.2.0.0`, 18: `18.0.2.0.0` | `adapt_version()` 이 `<시리즈>.` 로 시작하지 않는 값을 `<시리즈>.19.0.2.0.0` 으로 이어 붙이고 정규식(`x.y[.z]`)에서 `ValueError` 로 거부한다. 모듈이 그래프에 못 들어간다. |
| 2 | `security/groups.xml` | `res.groups.privilege` 모델 + 그룹의 `privilege_id` | `res.groups.category_id` (`ir.module.category`) | `privilege_security_monitor` 레코드를 삭제하고 그룹에 `<field name="category_id" ref="module_category_security_monitor"/>` 를 준다. 17/18 코어에 `privilege_id` 가 없다. |
| 3 | `views/*.xml`, `models/security_event.py` | `<list>`, `view_mode` `list` | 17: `<tree>`, `view_mode` `tree`. **18 은 `<list>` 그대로** | 17 만 해당. `security_event_views.xml`·`security_rule_views.xml` 의 `<list>`/`</list>` 와 `view_mode`, `security_event.py` 의 `action_trace_user`/`action_trace_ip` 의 `'view_mode': 'list'` 를 바꾼다. |
| 4 | `core/collector.py:80` `env.cr.readonly` | 있음 | **17 없음** (`sql_db.py` 에 속성 없음), 18 있음 | 17 에서는 `AttributeError` 가 나 `record()` 의 `except` 가 삼켜 **비분리 경로 이벤트가 전부 조용히 사라진다.** `getattr(env.cr, 'readonly', False)` 로 바꾼다. |
| 5 | `data/ir_cron_data.xml` | `numbercall` 없음 | 17: `numbercall` 필드 존재, 기본값 1. 18: 필드 없음 | 17 은 `<field name="numbercall">-1</field>` 를 추가한다. 없으면 탐지 cron 이 **1회 실행 후 멈춘다.** 18 에 넣으면 알 수 없는 필드 오류다. |
| 6 | `data/security_rule_data.xml` R-02/R-03 `condition_domain`, 테스트의 `group_ids` | `user_id.all_group_ids`, `group_ids` | `groups_id` | 도메인을 `user_id.groups_id` 로, `tests/test_rules.py`·`test_settings.py` 의 `'group_ids'` 를 `'groups_id'` 로. 17/18 은 `groups_id` 에 implied 그룹이 실체화되어 저장되므로 의미는 같다. |
| 7 | `models/security_rule_hit.py:75`, `tests/test_settings.py:117` | `res.groups.all_user_ids` | `res.groups.users` | 이름만 바꾼다. 알림 수신자 폴백이 설정 권한 관리자를 포함하는지 `test_group_system_implies_monitor_group` 으로 재확인한다. |
| 8 | `tests/test_install.py` | `group.privilege_id.category_id.name` | `group.category_id.name` | 2번 구조 변경에 맞춘다. |
| 9 | `models/security_rule.py:57` `models.Constraint('unique (code)', ...)` | 있음 | **17/18 없음** | `_sql_constraints = [('code_uniq', 'unique (code)', '...')]` 로 되돌린다. 안 바꾸면 모듈 임포트 단계에서 실패한다. |
| 10 | `models/res_users.py` `_login` 오버라이드 | 인스턴스 메서드 `_login(self, credential, user_agent_env)`, 반환 `auth_info` dict | **classmethod.** 17: `_login(cls, db, login, password, user_agent_env)` 반환 `user.id`. 18: `_login(cls, db, credential, user_agent_env)` 반환 `auth_info` | 훅을 통째로 다시 써야 한다. `cls` 에는 env 가 없어 `self.env` 를 쓸 수 없다. 실패 기록·`_secmon_failed_login_value` 는 `registry.cursor()` 로 env 를 직접 열어야 한다 (코어 `_login` 이 그렇게 한다). 17 은 `login`/`password` 를 인자로 받고 성공 시 uid 를 반환값에서 얻는다. 이 항목이 백포트에서 가장 크다. |

권장: 10번 때문에 Phase 3 계획의 `core/compat.py` 로 버전 분기를 모으는 편이 낫다. 백포트 후에는 각 버전에서 `-i edb_security --test-enable` 로 전체 테스트를 돌린다. 이 목록은 소스 대조 결과일 뿐 17/18 에서 실행해 본 것이 아니다.

### B6. Phase 2 선행 조건

Phase 2(프리셋 '표준') 착수 전에 끝내야 하는 6건이다. 1~5번은 Phase 1 설계 단계에서 정해졌고, 6번은 이번 점검에서 추가했다.

1. 마스킹 ACCOUNT 패턴 보강. 4그룹 카드번호는 뒷자리가 노출되고, 공백 구분 카드번호와 3자리 중간그룹 국제전화는 미탐지다. H-8(로깅 핸들러)·H-2·H-5 중 무엇이든 착수하기 전에 먼저 고친다. H-8 이 스택트레이스를 마스킹으로 흘리는 순간 실제 유출 경로가 열린다.
2. IP 신뢰 불가 시 룰 자동 비활성 (설계서 §3.5). `--proxy-mode` 미설정·`X-Forwarded-Host` 부재를 감지해 R-01B·R-02·R-09 를 끄고 히트에 "IP 신뢰 불가" 플래그를 단다. 없으면 R-02 가 최초 1회 후 영구 침묵한다.
3. `field_names` 문자열 규약 확정. 리스트를 넘기면 `str(list)` 로 뭉개져 저장된다. H-2/H-5 가 첫 생산자다.
4. `_log_toggle_change()` 에 세이브포인트. 지금은 vals 가 하드코딩이라 위험이 낮지만 필드가 늘면 위험해진다.
5. Integer/Char `config_parameter` 센티널 변종. `secmon_business_start` 를 0(자정)으로 처음 설정하면 코어 `set_values()` 의 `current_value == value` 충돌로 반영되지 않는다.
6. 룰 레코드 변경 기록 (설계서 §3.9). `edb.security.rule` 의 `create`/`write`/`unlink`(특히 `active`, `threshold_count`, `condition_domain`)를 이벤트로 남긴다. B3 참고. 감사자 그룹이 룰을 고칠 수 있는데 그 흔적이 없는 현재 상태를 해소한다.

이번 배포 전 점검에서 Phase 2 로 넘긴 항목: `conn.enqueue()` 가 INSERT 마다 동기 flush 하는 구조(B4.6 참조), 위 B2 의 탐지 공백(R-01 통보, 성공 직전 실패 상관 룰, 저강도 공격).

---

## 구조

```
edb_security/
├── __manifest__.py              # depends: edb_common, base, web, mail
├── core/                        # B: 수집기·분리 커넥션·토글 게이트·마스킹
├── models/
│   ├── edb_device_access.py     # A: edb.device.access + res.device.log 훅 + 대시보드 집계
│   ├── security_event.py        # B: edb.security.event
│   ├── security_rule.py         # B: edb.security.rule + 탐지 cron
│   ├── security_rule_hit.py     # B: edb.security.rule.hit + 알림
│   ├── res_users.py             # B: _login 훅 (성공·실패)
│   └── res_config_settings.py   # B: 수집 토글·프리셋·업무시간
├── controllers/device_access.py # A: 엑셀 내보내기
├── data/                        # B: 기본 룰 4개, 탐지 cron
├── security/                    # 보안 감사자 그룹, ACL
├── views/                       # 메뉴, A 목록·폼·대시보드 액션, B 화면, 설정
├── static/src/dashboard/        # A: OWL 대시보드
├── static/src/scss/             # B: 심각도 배지 색
└── tests/                       # A·B 테스트
```

## 테스트

```bash
odoo-bin -c .odoorc -d <테스트DB> -i edb_security --test-tags /edb_security --stop-after-init
```

## 의존성 / 라이선스

- Odoo: `edb_common`, `base`, `web`, `mail` · Python: `xlsxwriter`(엑셀 내보내기), `pytz`
- OEEL-1
