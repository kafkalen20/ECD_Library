---
owner: park-jihee
created: 2026-11-11
updated: 2026-11-11
---
# 로컬 개발 환경

## 목적
ECD_Library 모듈을 로컬 Odoo 19 EE에서 설치·수정·시험한다.

## 사전 조건
- Odoo 19.0 Enterprise 소스 (EE 애드온 포함 — `edb_helpdesk`가 `helpdesk` 필요)
- Python 가상환경: `.python-version`(pyenv) = `odoo19-ecd-library`
- 추가 패키지: `pip install zeep pytz`
- 바로빌 CERTKEY·사업자번호·ID·FTP 비번은 **비밀번호 관리자**에서 조회해 설정 화면에 입력 — 파일에 쓰지 않는다. [❓확인 필요: 비밀번호 관리자 항목 위치]

## 절차
1. 레포 루트에 개인용 `.odoorc` 작성 (`.git/info/exclude`로 커밋 제외됨). 확인된 값:
   - `addons_path = <Odoo19 EE>/odoo/addons,<이 레포>/19.0` ← 루트가 아니라 **Odoo 버전과 같은 폴더**
   - `dbfilter = ^ecd19` · `http_port = 8170`
2. 실행·모듈 반영: `<Odoo19 EE>/odoo-bin -c .odoorc -d <db> -u <module>`
3. 테스트: `<Odoo19 EE>/odoo-bin -c .odoorc -d <db> --test-enable --test-tags /<module> --stop-after-init`
4. 바로빌은 설정 > 바로빌에서 `barobill.mode = test` 로 두고 시험한다.

## 주의 / 함정
- 바로빌 `prod` 모드로 시험하면 실제 문자·팩스·세금계산서가 나가고 포인트가 차감된다.
- 알림톡은 사전 승인 템플릿과 본문이 다르면 거부된다.
- [❓확인 필요: 공용 dev DB·샘플 데이터 준비 방법이 따로 있는지]

## 변경 이력
| 날짜 | 작성자 | 내용 |
|------|--------|------|
| 2026-11-11 | park-jihee | claude-brain 적용 시 `.odoorc`·README 기준 최초 작성 |
