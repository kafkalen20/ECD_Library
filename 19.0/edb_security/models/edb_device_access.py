# -*- coding: utf-8 -*-

from datetime import datetime, time as dtime, timedelta
import logging

import pytz

from odoo import api, fields, models
from odoo.exceptions import AccessError
from odoo.http import STORED_SESSION_BYTES, request
from odoo.tools import SQL

_logger = logging.getLogger(__name__)

# 재접속 판정 간격(초). "마지막 동작 시각" 기준으로 이 시간 이상 아무 요청이
# 없다가 다시 요청이 오면 재접속으로 1건 기록한다(자리 비웠다 복귀).
_REACCESS_INTERVAL_SECONDS = 3600  # 1시간

# 동시요청 중복 차단용 부분 유니크 인덱스명(같은 세션·기기·분 1건).
_DEDUP_INDEX = 'edb_device_access_dedup_minute_uniq'


class EdbDeviceAccess(models.Model):
    """사용자 접속 내역 (Device Access History)

    코어 ``res.device`` / ``res.device.log`` 는 세션·디바이스별 '마지막 접속'만
    확인 가능하고, 자동 GC(:meth:`res.device.log._gc_device_log`)가 중복 로그를
    정리한다. 이 모델은 그와 별개로 **접속(새 세션/디바이스 연결)이 발생할 때마다**
    한 건씩 영구 이력을 남긴다.

    저장 정보:
      - 접속 기기/OS (안드로이드 · iOS · macOS · Windows · Linux 등)
      - 브라우저
      - 접속 시각 · IP
      - 접속 사용자

    고객은 ``os_family`` / ``device_type`` 로 안드로이드·iOS·모바일 등
    원하는 조건만 필터링해서 조회할 수 있다.

    Ecodoobiz 공용 보안 모듈(edb_security). 프로젝트 무관하게 재사용한다.
    """
    _name = 'edb.device.access'
    _description = '사용자 접속 내역'
    _order = 'access_datetime desc, id desc'
    _rec_names_search = ['user_id', 'device', 'browser', 'ip_address']

    user_id = fields.Many2one(
        'res.users', string='사용자',
        index='btree', ondelete='cascade',
    )
    session_identifier = fields.Char(string='세션 식별자', index='btree')
    access_datetime = fields.Datetime(string='접속 시각', index='btree')

    device = fields.Char(string='접속기기')
    browser = fields.Char(string='브라우저')
    access_detail = fields.Char(
        string='접속 상세정보',
        help='접속 시 브라우저가 보낸 원본 User-Agent 문자열. '
             '브라우저가 "알 수 없음"으로 저장된 경우 실제 브라우저 확인용.',
    )
    os_family = fields.Selection(
        selection=[
            ('android', 'Android'),
            ('ios', 'iOS'),
            ('windows', 'Windows'),
            ('macos', 'macOS'),
            ('linux', 'Linux'),
            ('chromeos', 'ChromeOS'),
            ('other', '기타'),
        ],
        string='운영체제',
        index='btree',
        help='접속 기기의 운영체제 계열. 안드로이드/iOS 등으로 필터링할 때 사용.',
    )
    device_type = fields.Selection(
        selection=[('computer', 'PC'), ('mobile', '모바일')],
        string='기기 구분',
        index='btree',
    )

    ip_address = fields.Char(string='IP 주소')

    event_type = fields.Selection(
        selection=[
            ('access', '접속'),
        ],
        string='유형', default='access', index='btree', required=True,
        help='접속 = 로그인/재접속. 로그인 실패는 보안 이벤트(edb.security.event)에 기록한다.',
    )

    def _compute_display_name(self):
        for rec in self:
            os_label = dict(self._fields['os_family'].selection).get(rec.os_family, '')
            rec.display_name = ' '.join(filter(None, [os_label, rec.browser])) or '접속 내역'

    def init(self):
        """동시요청 중복(같은 세션·기기·분) 차단용 부분 유니크 인덱스.

        로그인 시 웹클라이언트가 요청을 다발로 보내면 여러 요청이 동시에 재접속
        판정을 통과해 같은 시각 중복행이 쌓인다. Odoo 기본 트랜잭션 격리가
        REPEATABLE READ 라서 advisory lock + 조회-후-삽입 패턴은 스냅샷 고정으로
        동시 커밋행을 못 봐 중복을 막지 못한다. 스냅샷과 무관한 유니크 인덱스로
        원자적으로 차단한다(적재는 ON CONFLICT DO NOTHING).

        인덱스 생성 전, 기존 동일-분 중복(가장 이른 id 유지)을 자동 정리한다
        (모듈 업데이트 시 self-heal). event_type='access' 만 대상.
        """
        cr = self.env.cr
        cr.execute("""
            DELETE FROM edb_device_access a USING edb_device_access b
            WHERE a.event_type = 'access' AND b.event_type = 'access'
              AND COALESCE(a.session_identifier, '') = COALESCE(b.session_identifier, '')
              AND COALESCE(a.device, '') = COALESCE(b.device, '')
              AND COALESCE(a.browser, '') = COALESCE(b.browser, '')
              AND COALESCE(a.ip_address, '') = COALESCE(b.ip_address, '')
              AND date_trunc('minute', a.access_datetime) = date_trunc('minute', b.access_datetime)
              AND b.id < a.id
        """)
        if cr.rowcount:
            _logger.info('접속 내역 동일-분 중복 %s건 정리(인덱스 생성 전)', cr.rowcount)
        cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS %s
            ON edb_device_access
               (COALESCE(session_identifier, ''), COALESCE(device, ''), COALESCE(browser, ''),
                COALESCE(ip_address, ''), date_trunc('minute', access_datetime))
            WHERE event_type = 'access'
        """ % _DEDUP_INDEX)

    # ------------------------------------------------------------------
    # 헬퍼
    # ------------------------------------------------------------------
    @api.model
    def _os_family_from_platform(self, platform):
        """코어 user-agent ``platform`` 값을 OS 계열 selection 으로 매핑."""
        if not platform:
            return 'other'
        p = platform.lower()
        if p == 'android':
            return 'android'
        if p in ('iphone', 'ipad', 'ipod', 'ios'):
            return 'ios'
        if p == 'windows':
            return 'windows'
        if p == 'macos':
            return 'macos'
        if p == 'chromeos':
            return 'chromeos'
        if p == 'linux':
            return 'linux'
        return 'other'

    @api.model
    def _os_family_from_user_agent(self, ua_string, platform):
        """원본 User-Agent 로 OS 계열을 판별(코어 platform 오판 보정).

        코어 파서는 UA 안의 ``Crosswalk`` 를 ``cros``(ChromeOS)로 오인하는 등
        모바일 인앱브라우저를 잘못 분류한다(예: 네이버 인앱 웹뷰의 안드로이드폰이
        ChromeOS 로 잡힘). 원본 UA 의 강한 신호(Android·iPhone 등)를 먼저 본다.
        """
        low = (ua_string or '').lower()
        if 'android' in low:
            return 'android'
        if 'iphone' in low or 'ipad' in low or 'ipod' in low:
            return 'ios'
        if 'windows' in low:
            return 'windows'
        if 'macintosh' in low or 'mac os x' in low:
            return 'macos'
        # 진짜 ChromeOS 만 (Crosswalk 오탐 제외 — 'cr os' 또는 chromebook 토큰)
        if 'cros ' in low or 'chromebook' in low:
            return 'chromeos'
        if 'linux' in low:
            return 'linux'
        # UA 로 판단 불가 시 코어 platform 기준
        return self._os_family_from_platform(platform)

    @api.model
    def _is_mobile_user_agent(self, ua_string, platform):
        """원본 User-Agent 로 모바일 여부 판별(코어 platform 오판 보정)."""
        low = (ua_string or '').lower()
        if 'android' in low or 'iphone' in low or 'ipad' in low or 'ipod' in low:
            return True
        # 명백한 데스크톱 신호면 PC
        if 'windows nt' in low or 'macintosh' in low or 'cros ' in low:
            return False
        if 'mobile' in low:
            return True
        # 판단 불가 시 코어 platform 기준(_is_mobile 은 res.device.log 제공)
        return self.env['res.device.log']._is_mobile(platform)

    @api.model
    def _browser_from_user_agent(self, ua_string, fallback=None):
        """원본 User-Agent 문자열로 브라우저를 세분화.

        코어 UA 파서는 오래된 목록만 인식해서 크롬 기반 파생 브라우저
        (네이버 웨일 · 삼성 인터넷 · Brave · Vivaldi · 최신 Edge/Opera)를
        전부 'chrome' 으로 뭉뚱그린다. 여기서는 UA 문자열의 고유 토큰을
        직접 찾아 실제 브라우저명을 돌려준다. 코어 파서는 건드리지 않는다.

        :param ua_string: request.httprequest.user_agent.string (원본 UA)
        :param fallback: 코어가 판별한 브라우저 토큰(예: 'chrome', 'safari')
        """
        low = (ua_string or '').lower()
        # 고유 토큰 우선 매칭 (크롬 기반 파생 브라우저를 먼저 걸러냄)
        token_map = [
            ('whale', 'Whale'),               # 네이버 웨일
            ('samsungbrowser', 'Samsung Internet'),
            ('vivaldi', 'Vivaldi'),
            ('edg/', 'Edge'), ('edga/', 'Edge'), ('edgios/', 'Edge'), ('edge/', 'Edge'),
            ('opr/', 'Opera'), ('opios/', 'Opera'), ('opera', 'Opera'),
            ('fxios', 'Firefox'),             # iOS 파이어폭스
            ('crios', 'Chrome'),              # iOS 크롬
        ]
        for token, label in token_map:
            if token in low:
                return label
        # 위에서 못 걸러냈으면 코어가 판별한 주요 브라우저만 인정
        mainstream = {
            'chrome': 'Chrome', 'safari': 'Safari', 'firefox': 'Firefox',
            'edge': 'Edge', 'opera': 'Opera',
        }
        if fallback and fallback.lower() in mainstream:
            return mainstream[fallback.lower()]
        # 그 외 / 식별 불가 → 알 수 없음
        return '알 수 없음'

    # ------------------------------------------------------------------
    # 대시보드 집계
    # ------------------------------------------------------------------
    @api.model
    def _dept_label(self, user):
        """사용자 부서명(선택). hr 미설치 시 빈 문자열."""
        if 'employee_ids' in user._fields:
            emp = user.employee_ids[:1]
            if emp and emp.department_id:
                return emp.department_id.name
        return ''

    @api.model
    def _relative_day_label(self, dt_local, today_local):
        """로컬 datetime 을 '오늘 09:12' / '어제 17:30' / 'N일 전' 로 표기."""
        days = (today_local - dt_local.date()).days
        if days <= 0:
            return '오늘 %02d:%02d' % (dt_local.hour, dt_local.minute)
        if days == 1:
            return '어제 %02d:%02d' % (dt_local.hour, dt_local.minute)
        return '%d일 전' % days

    @api.model
    def get_access_dashboard_data(self, period='month'):
        """접속 현황 대시보드용 집계 데이터.

        저장된 접속 내역(edb.device.access)을 기준으로
        KPI / 접속추이 / 기기구분 / 시간대·요일 분포 / 사용자별 현황 / 미접속자
        를 한 번에 계산해 반환한다. 모두 읽기전용 SELECT 집계.
        시간대·요일·일자 구분은 사용자 타임존 기준으로 변환한다.

        :param period: 'week'(주=최근7일) / 'month'(월=최근30일) / 'year'(년=최근1년)
            추이·기기·시간대·요일·사용자별·미접속 판정이 이 기간을 따른다.
            추이 그래프는 주/월은 일별, 년은 월별로 집계한다.
        """
        # 원시 SQL 집계라 ACL 을 타지 않는다. RPC·엑셀 경로 모두 여기서 막는다.
        if not (self.env.su or self.env.user.has_group('edb_security.group_security_monitor')):
            raise AccessError("보안 감사자만 접속 현황을 볼 수 있습니다.")
        cr = self.env.cr
        tz_name = self.env.context.get('tz') or self.env.user.tz or 'Asia/Seoul'
        tz = pytz.timezone(tz_name)
        now_local = pytz.utc.localize(datetime.utcnow()).astimezone(tz)
        today_local = now_local.date()

        def start_utc(d):
            # 로컬 자정 → UTC naive (저장값이 UTC naive)
            return tz.localize(datetime.combine(d, dtime.min)).astimezone(pytz.utc).replace(tzinfo=None)

        s_today = start_utc(today_local)
        s_yest = start_utc(today_local - timedelta(days=1))
        s_7 = start_utc(today_local - timedelta(days=6))     # 오늘 포함 7일
        s_30 = start_utc(today_local - timedelta(days=29))   # 오늘 포함 30일

        # ── 선택 기간(주/월/년) 윈도우 ──
        if period == 'week':
            win_days, trend_mode = 7, 'day'
        elif period == 'year':
            win_days, trend_mode = 365, 'month'
        else:  # month (기본)
            period, win_days, trend_mode = 'month', 30, 'day'
        s_win = start_utc(today_local - timedelta(days=win_days - 1))

        # ── 총 내부 사용자 (활성·포털 제외) ──
        total_users = self.env['res.users'].search_count([
            ('share', '=', False), ('active', '=', True),
        ])

        def distinct_users(start, end=None):
            if end:
                cr.execute(
                    "SELECT COUNT(DISTINCT user_id) FROM edb_device_access "
                    "WHERE user_id IS NOT NULL AND event_type = 'access' AND access_datetime >= %s AND access_datetime < %s",
                    (start, end))
            else:
                cr.execute(
                    "SELECT COUNT(DISTINCT user_id) FROM edb_device_access "
                    "WHERE user_id IS NOT NULL AND event_type = 'access' AND access_datetime >= %s", (start,))
            return cr.fetchone()[0] or 0

        today_users = distinct_users(s_today)
        yest_users = distinct_users(s_yest, s_today)
        wau = distinct_users(s_7)
        mau = distinct_users(s_30)
        active_rate = round(mau / total_users * 100, 1) if total_users else 0.0

        # ── 접속 사용자 추이 (선택 기간, 고유 사용자) ──
        trend_labels, trend_counts = [], []
        if trend_mode == 'month':
            # 년: 최근 12개월 월별 집계
            cr.execute(
                "SELECT date_trunc('month', access_datetime AT TIME ZONE 'UTC' AT TIME ZONE %s) AS m, "
                "       COUNT(DISTINCT user_id) "
                "FROM edb_device_access "
                "WHERE user_id IS NOT NULL AND event_type = 'access' AND access_datetime >= %s "
                "GROUP BY m", (tz_name, s_win))
            month_map = {r[0].date().replace(day=1): r[1] for r in cr.fetchall()}
            first = today_local.replace(day=1)
            for i in range(11, -1, -1):
                y, m = divmod(first.month - 1 - i, 12)
                mo = first.replace(year=first.year + y, month=m + 1)
                trend_labels.append('%d월' % mo.month)
                trend_counts.append(month_map.get(mo, 0))
        else:
            # 주/월: 일별 집계
            cr.execute(
                "SELECT (access_datetime AT TIME ZONE 'UTC' AT TIME ZONE %s)::date AS d, "
                "       COUNT(DISTINCT user_id) "
                "FROM edb_device_access "
                "WHERE user_id IS NOT NULL AND event_type = 'access' AND access_datetime >= %s "
                "GROUP BY d", (tz_name, s_win))
            day_map = {r[0]: r[1] for r in cr.fetchall()}
            for i in range(win_days - 1, -1, -1):
                d = today_local - timedelta(days=i)
                trend_labels.append('%d/%d' % (d.month, d.day))
                trend_counts.append(day_map.get(d, 0))

        # ── 기기 구분 (선택 기간) ──
        cr.execute(
            "SELECT device_type, COUNT(*) FROM edb_device_access "
            "WHERE event_type = 'access' AND access_datetime >= %s GROUP BY device_type", (s_win,))
        dev_map = dict(cr.fetchall())
        device = {'pc': dev_map.get('computer', 0), 'mobile': dev_map.get('mobile', 0)}

        # ── 기기 2중 도넛: 안쪽 PC/모바일 + 바깥쪽 OS 세부 (선택 기간) ──
        # iOS 는 device(werkzeug platform)로 iPhone/iPad 세분화.
        cr.execute(
            "SELECT device_type, "
            "  CASE WHEN os_family='ios' AND lower(COALESCE(device,'')) LIKE '%%ipad%%' THEN 'ipad' "
            "       WHEN os_family='ios' THEN 'iphone' "
            "       ELSE COALESCE(os_family,'other') END AS osk, "
            "  COUNT(*) "
            "FROM edb_device_access "
            "WHERE event_type = 'access' AND access_datetime >= %s "
            "GROUP BY device_type, osk", (s_win,))
        detail_label = {
            'windows': 'Windows', 'macos': 'macOS', 'linux': 'Linux',
            'chromeos': 'ChromeOS', 'android': 'Android',
            'iphone': 'iPhone', 'ipad': 'iPad', 'other': '기타',
        }
        comp_os, mob_os = [], []
        for dtype, osk, cnt in cr.fetchall():
            item = (detail_label.get(osk, osk or '기타'), cnt)
            (mob_os if dtype == 'mobile' else comp_os).append(item)
        comp_os.sort(key=lambda x: -x[1])
        mob_os.sort(key=lambda x: -x[1])
        pc_shades = ['#714b67', '#8a6b82', '#a8879e', '#5c3d54', '#9a7b90', '#6b4763']
        mob_shades = ['#e0b3d1', '#d18cb8', '#c96fa6', '#eac9dd', '#b85c98', '#f0d5e6']
        outer_colors = ([pc_shades[i % len(pc_shades)] for i in range(len(comp_os))]
                        + [mob_shades[i % len(mob_shades)] for i in range(len(mob_os))])
        device_nested = {
            'inner': {
                'labels': ['PC', '모바일'],
                'data': [sum(c for _, c in comp_os), sum(c for _, c in mob_os)],
                'colors': ['#714b67', '#e0b3d1'],
            },
            'outer': {
                'labels': [l for l, _ in comp_os] + [l for l, _ in mob_os],
                'data': [c for _, c in comp_os] + [c for _, c in mob_os],
                'colors': outer_colors,
                # 각 OS 세그먼트가 속한 기기 구분(누적막대 카테고리 매칭용)
                'devices': ['PC'] * len(comp_os) + ['모바일'] * len(mob_os),
            },
        }

        # ── 운영체제 분포 (선택 기간) ──
        cr.execute(
            "SELECT os_family, COUNT(*) FROM edb_device_access "
            "WHERE event_type = 'access' AND access_datetime >= %s GROUP BY os_family", (s_win,))
        os_label_map = dict(self._fields['os_family'].selection)
        os_items = sorted(
            [(os_label_map.get(k or 'other', '기타'), v) for k, v in cr.fetchall()],
            key=lambda x: -x[1])
        os_dist = {'labels': [i[0] for i in os_items], 'data': [i[1] for i in os_items]}

        # ── 시간대별 분포 (선택 기간): 접속 건수 + 고유 접속 인원 ──
        cr.execute(
            "SELECT EXTRACT(HOUR FROM (access_datetime AT TIME ZONE 'UTC' AT TIME ZONE %s))::int AS h, "
            "       COUNT(*), COUNT(DISTINCT user_id) FROM edb_device_access "
            "WHERE event_type = 'access' AND access_datetime >= %s GROUP BY h", (tz_name, s_win))
        hour_map, hour_user_map = {}, {}
        for h, cnt, ucnt in cr.fetchall():
            hour_map[h] = cnt
            hour_user_map[h] = ucnt
        hours = [hour_map.get(h, 0) for h in range(24)]
        hours_users = [hour_user_map.get(h, 0) for h in range(24)]

        # ── 요일별 분포 (최근 30일). PG DOW: 0=일 … 6=토 → 월~일 순 재배열 ──
        cr.execute(
            "SELECT EXTRACT(DOW FROM (access_datetime AT TIME ZONE 'UTC' AT TIME ZONE %s))::int AS w, "
            "       COUNT(*) FROM edb_device_access "
            "WHERE event_type = 'access' AND access_datetime >= %s GROUP BY w", (tz_name, s_win))
        dow_map = dict(cr.fetchall())
        dow = [dow_map.get(w, 0) for w in (1, 2, 3, 4, 5, 6, 0)]  # 월화수목금토일

        # ── 사용자별 접속 현황 (최근 30일, 상위 50명) ──
        cr.execute(
            "SELECT user_id, COUNT(*), MAX(access_datetime) "
            "FROM edb_device_access "
            "WHERE user_id IS NOT NULL AND event_type = 'access' AND access_datetime >= %s "
            "GROUP BY user_id ORDER BY COUNT(*) DESC LIMIT 50", (s_win,))
        user_rows = cr.fetchall()

        # 사용자별 주 사용기기 (device_type + device 최빈)
        cr.execute(
            "SELECT user_id, device_type, device, COUNT(*) AS c "
            "FROM edb_device_access "
            "WHERE user_id IS NOT NULL AND event_type = 'access' AND access_datetime >= %s "
            "GROUP BY user_id, device_type, device ORDER BY c DESC", (s_win,))
        main_dev = {}
        for uid, dtype, dev, _c in cr.fetchall():
            main_dev.setdefault(uid, (dtype, dev))  # 첫 행(=최다) 채택

        # device(werkzeug platform) 표시용 라벨 (iPhone/iPad 등 세분)
        dev_label = {
            'windows': 'Windows', 'macos': 'macOS', 'linux': 'Linux',
            'chromeos': 'ChromeOS', 'android': 'Android',
            'iphone': 'iPhone', 'ipad': 'iPad', 'ipod': 'iPod',
        }
        user_ids = [r[0] for r in user_rows]
        users_by_id = {u.id: u for u in self.env['res.users'].browse(user_ids).exists()}
        users = []
        for uid, cnt, last_dt in user_rows:
            user = users_by_id.get(uid)
            if not user:
                continue
            last_local = pytz.utc.localize(last_dt).astimezone(tz)
            days = (today_local - last_local.date()).days
            status = 'active' if days <= 2 else ('normal' if days <= 7 else 'low')
            dtype, dev = main_dev.get(uid, (None, None))
            users.append({
                'name': user.name,
                'dept': self._dept_label(user),
                'count': cnt,
                'last_label': self._relative_day_label(last_local, today_local),
                'device_type': dtype or '',
                'device_label': ' · '.join(filter(None, [
                    'PC' if dtype == 'computer' else ('모바일' if dtype == 'mobile' else ''),
                    dev_label.get(dev, (dev or '').capitalize()),
                ])),
                'status': status,
            })

        # ── 미접속 사용자 (선택 기간 내 접속 없음) ──
        cr.execute(
            "SELECT DISTINCT user_id FROM edb_device_access "
            "WHERE user_id IS NOT NULL AND event_type = 'access' AND access_datetime >= %s", (s_win,))
        recent_uids = {r[0] for r in cr.fetchall()}
        # 전체 접속 이력의 사용자별 마지막 접속(있으면)
        cr.execute(
            "SELECT user_id, MAX(access_datetime) FROM edb_device_access "
            "WHERE user_id IS NOT NULL AND event_type = 'access' GROUP BY user_id")
        alltime_last = {r[0]: r[1] for r in cr.fetchall()}

        internal_users = self.env['res.users'].search([
            ('share', '=', False), ('active', '=', True),
        ])
        inactive = []
        for user in internal_users:
            if user.id in recent_uids:
                continue
            last_dt = alltime_last.get(user.id)
            if last_dt:
                last_local = pytz.utc.localize(last_dt).astimezone(tz)
                days = (today_local - last_local.date()).days
                label, sort_key = '%d일 전' % days, days
            else:
                label, sort_key = '한 번도 없음', 10 ** 6
            inactive.append({
                'name': user.name,
                'dept': self._dept_label(user),
                'last_label': label,
                '_sort': sort_key,
            })
        inactive.sort(key=lambda x: -x['_sort'])  # 오래 미접속/미접속 우선
        for it in inactive:
            it.pop('_sort', None)

        # ── 로그인 실패 (선택 기간) ── 보안 이벤트에서 읽는다(로그인값은 저장 시 가려져 있음)
        Event = self.env['edb.security.event'].sudo()
        failed_domain = [('event_type', '=', 'login_failed'), ('create_date', '>=', s_win)]
        failed_login_count = Event.search_count(failed_domain)
        recent_failed = []
        for ev in Event.search(failed_domain, limit=20):
            fl = pytz.utc.localize(ev.create_date).astimezone(tz)
            ua = ev.user_agent or ''
            recent_failed.append({
                'time_label': '%d/%d %02d:%02d' % (fl.month, fl.day, fl.hour, fl.minute),
                'login': ev.login_display or '(없음)',
                'ip': ev.client_ip or '-',
                'device_label': ' · '.join(filter(None, [
                    ('모바일' if self._is_mobile_user_agent(ua, None) else 'PC') if ua else '',
                    os_label_map.get(self._os_family_from_user_agent(ua, None), '') if ua else '',
                ])) or '-',
            })

        return {
            'period': period,
            'window_days': win_days,
            'trend_mode': trend_mode,
            'range': {
                'from': (today_local - timedelta(days=win_days - 1)).strftime('%Y-%m-%d'),
                'to': today_local.strftime('%Y-%m-%d'),
            },
            'kpi': {
                'today': today_users,
                'today_delta': today_users - yest_users,
                'wau': wau,
                'mau': mau,
                'total_users': total_users,
                'active_rate': active_rate,
                'failed_login': failed_login_count,
            },
            'trend': {'labels': trend_labels, 'counts': trend_counts},
            'device': device,
            'device_nested': device_nested,
            'os': os_dist,
            'hours': hours,
            'hours_users': hours_users,
            'dow': dow,
            'users': users,
            'inactive': inactive[:20],
            'inactive_count': len(inactive),
            'recent_failed': recent_failed,
        }

    @api.model
    def build_dashboard_xlsx(self, period='month'):
        """접속 현황(선택 기간)을 엑셀 워크북 bytes 로 생성. 차트 대신 표만 담는다."""
        import io
        import xlsxwriter

        data = self.get_access_dashboard_data(period)
        period_label = {'week': '주간(최근 7일)', 'month': '월간(최근 30일)',
                        'year': '연간(최근 1년)'}.get(data['period'], '')
        now_local = pytz.utc.localize(datetime.utcnow()).astimezone(
            pytz.timezone(self.env.context.get('tz') or self.env.user.tz or 'Asia/Seoul'))
        status_map = {'active': '활발', 'normal': '보통', 'low': '저조'}

        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output, {'in_memory': True})
        f_title = wb.add_format({'bold': True, 'font_size': 14})
        f_meta = wb.add_format({'font_size': 10, 'font_color': '#666666'})
        f_sec = wb.add_format({'bold': True, 'font_size': 11, 'bg_color': '#714b67', 'font_color': '#FFFFFF'})
        f_hdr = wb.add_format({'bold': True, 'font_size': 10, 'bg_color': '#F2EEF2', 'border': 1, 'align': 'center'})
        f_txt = wb.add_format({'font_size': 10, 'border': 1})
        f_num = wb.add_format({'font_size': 10, 'border': 1, 'align': 'right', 'num_format': '#,##0'})

        def table(sheet, r, c, title, headers, rows, widths=None):
            sheet.write(r, c, title, f_sec)
            r += 1
            for j, h in enumerate(headers):
                sheet.write(r, c + j, h, f_hdr)
            r += 1
            for row in rows:
                for j, v in enumerate(row):
                    fmt = f_num if isinstance(v, (int, float)) and not isinstance(v, bool) else f_txt
                    sheet.write(r, c + j, v, fmt)
                r += 1
            if widths:
                for j, w in enumerate(widths):
                    sheet.set_column(c + j, c + j, w)
            return r + 1  # 다음 표 시작 전 빈 줄

        # ── 시트1: 요약 ──
        s = wb.add_worksheet('요약')
        s.write(0, 0, '사용자 접속 현황', f_title)
        s.write(1, 0, f"기간: {period_label}", f_meta)
        s.write(2, 0, f"출력일시: {now_local.strftime('%Y-%m-%d %H:%M')}", f_meta)
        k = data['kpi']
        r = table(s, 4, 0, '요약(KPI)', ['항목', '값'], [
            ['오늘 접속 사용자', k['today']],
            ['이번 주 활성(WAU)', k['wau']],
            ['이번 달 활성(MAU)', k['mau']],
            ['전체 내부 사용자', k['total_users']],
            ['활성률(%)', k['active_rate']],
            ['로그인 실패(기간)', k['failed_login']],
        ], widths=[22, 14])
        r = table(s, r, 0, '기기 구분', ['구분', '건수'],
                  [['PC', data['device']['pc']], ['모바일', data['device']['mobile']]], widths=[22, 14])
        r = table(s, r, 0, '요일별 접속', ['요일', '건수'],
                  [[d, data['dow'][i]] for i, d in enumerate(['월', '화', '수', '목', '금', '토', '일'])])
        table(s, r, 0, '시간대별 접속', ['시(0~23)', '건수'],
              [[f"{h}시", data['hours'][h]] for h in range(24)])

        # ── 시트2: 접속 추이 ──
        s2 = wb.add_worksheet('접속추이')
        trend_hdr = '월' if data['trend_mode'] == 'month' else '날짜'
        table(s2, 0, 0, '접속 사용자 수 추이', [trend_hdr, '접속 사용자 수'],
              list(zip(data['trend']['labels'], data['trend']['counts'])), widths=[14, 16])

        # ── 시트3: 사용자별 접속 현황 ──
        s3 = wb.add_worksheet('사용자별')
        table(s3, 0, 0, '사용자별 접속 현황', ['사용자', '부서', '접속 횟수', '최근 접속', '주 사용기기', '활동'],
              [[u['name'], u['dept'], u['count'], u['last_label'], u['device_label'],
                status_map.get(u['status'], '')] for u in data['users']],
              widths=[16, 14, 10, 16, 20, 8])

        # ── 시트4: 미접속 사용자 ──
        s4 = wb.add_worksheet('미접속')
        table(s4, 0, 0, f"미접속 사용자 (전체 {k['total_users']}명 중 {data['inactive_count']}명)",
              ['사용자', '부서', '마지막 접속'],
              [[i['name'], i['dept'], i['last_label']] for i in data['inactive']], widths=[16, 14, 14])

        # ── 시트5: 로그인 실패 ──
        s5 = wb.add_worksheet('로그인실패')
        table(s5, 0, 0, '최근 로그인 실패', ['시각', '시도한 로그인', 'IP 주소', '기기'],
              [[f['time_label'], f['login'], f['ip'], f['device_label']] for f in data['recent_failed']]
              or [['-', '기록 없음', '-', '-']], widths=[16, 22, 16, 18])

        wb.close()
        output.seek(0)
        return output.read()

    # ------------------------------------------------------------------
    # 이벤트 기록(로그인 실패) + 보관정책
    # ------------------------------------------------------------------
    @api.model
    def _edb_request_device_vals(self, req):
        """요청의 User-Agent/IP 로 기기·브라우저 값을 dict 로 뽑는다."""
        vals = {
            'ip_address': None,
            'device': None, 'browser': None, 'access_detail': None,
            'os_family': 'other', 'device_type': 'computer',
        }
        if not req:
            return vals
        ua = req.httprequest.user_agent
        vals['ip_address'] = req.httprequest.remote_addr
        if ua:
            vals['device'] = ua.platform
            vals['access_detail'] = ua.string
            vals['browser'] = self._browser_from_user_agent(ua.string, ua.browser)
            vals['os_family'] = self._os_family_from_user_agent(ua.string, ua.platform)
            vals['device_type'] = 'mobile' if self._is_mobile_user_agent(ua.string, ua.platform) else 'computer'
        return vals

    @api.model
    def _edb_insert_event(self, cr, vals):
        """이벤트 1건 INSERT (호출자가 커서를 넘긴다)."""
        cr.execute(SQL(
            """
            INSERT INTO edb_device_access
                (event_type, user_id, session_identifier, access_datetime,
                 device, browser, access_detail, os_family, device_type, ip_address,
                 create_uid, write_uid, create_date, write_date)
            VALUES
                (%(event_type)s, %(user_id)s, %(session_identifier)s, %(access_datetime)s,
                 %(device)s, %(browser)s, %(access_detail)s, %(os_family)s, %(device_type)s, %(ip_address)s,
                 %(cuid)s, %(cuid)s, %(access_datetime)s, %(access_datetime)s)
            """,
            event_type=vals.get('event_type', 'access'),
            user_id=vals.get('user_id'),
            session_identifier=vals.get('session_identifier'),
            access_datetime=vals.get('access_datetime') or datetime.now(),
            device=vals.get('device'), browser=vals.get('browser'),
            access_detail=vals.get('access_detail'), os_family=vals.get('os_family'),
            device_type=vals.get('device_type'), ip_address=vals.get('ip_address'),
            cuid=self.env.uid or 1,
        ))

    @api.autovacuum
    def _gc_device_access(self):
        """보관기간(기본 365일) 지난 접속 내역 자동 삭제. ICP 로 일수 조정.

        ``edb_security.device_access_retention_days`` = 0 이면 삭제하지 않는다.
        base 의 일일 자동정리(ir.autovacuum) 크론이 호출한다.
        """
        days = int(self.env['ir.config_parameter'].sudo().get_param(
            'edb_security.device_access_retention_days', 365) or 365)
        if days <= 0:
            return
        limit = datetime.now() - timedelta(days=days)
        self.env.cr.execute(
            "DELETE FROM edb_device_access WHERE access_datetime < %s", (limit,))
        _logger.info('접속 내역 GC: %s일 경과 %s건 삭제', days, self.env.cr.rowcount)


class ResDeviceLog(models.Model):
    """코어 디바이스 로그 확장 — 접속 시마다 영구 이력 적재."""
    _inherit = 'res.device.log'

    @api.model
    def _update_device(self, request):
        """코어 디바이스 로그 갱신 시, 접속(신규/재접속)이면 접속 내역도 남긴다.

        모델 B — **마지막 동작 시각 기준**. 세션에 (platform, browser, ip) 별
        마지막 요청 시각을 매 요청마다 기록해 두고, 그 시각으로부터
        ``_REACCESS_INTERVAL_SECONDS`` 이상 아무 요청이 없다가 다시 요청이 오면
        재접속으로 1건 남긴다(자리 비웠다 복귀). 연속 사용 중에는 기록하지 않는다.
        코어 ``update_trace`` 의 heartbeat(마지막 '기록' 시각 기준)와 무관하게
        우리 기준으로만 판정한다.
        접속 내역 적재 실패가 로그인/요청 자체를 막지 않도록 예외는 흡수한다.
        """
        should_log = self._edb_should_log(request)
        res = super()._update_device(request)
        # 로그인 사용자의 접속만 이력으로 남긴다 (익명/공용 세션 제외).
        if should_log and request.session.uid:
            try:
                self._edb_log_access(request)
            except Exception:  # pragma: no cover - 감사 로그 실패가 요청을 막으면 안 됨
                _logger.exception('접속 내역(edb.device.access) 적재 실패')
        return res

    def _edb_should_log(self, request):
        """이번 요청에 접속 내역을 남길지 판별 + 마지막 동작 시각 갱신 (모델 B).

          - 세션에 (platform, browser, ip) 별 마지막 동작 시각을 매 요청마다 기록.
          - 그 값이 없으면(첫 접속) → 기록.
          - 마지막 동작 후 ``_REACCESS_INTERVAL_SECONDS`` 이상 지나 다시 요청이 오면
            → 재접속으로 기록(자리 비웠다 복귀).
          - 그 사이 연속 사용(간격 미만)은 기록하지 않되, 마지막 동작 시각은 계속 이동.
        """
        session = request.session
        if session.get('_trace_disable'):
            return False
        user_agent = request.httprequest.user_agent
        key = '%s|%s|%s' % (
            user_agent.platform, user_agent.browser,
            request.httprequest.remote_addr,
        )
        now = int(datetime.now().timestamp())
        seen = dict(session.get('_edb_last_seen') or {})
        last = seen.get(key)
        should_log = last is None or (now - last) >= _REACCESS_INTERVAL_SECONDS
        # 마지막 동작 시각 갱신(기준점 이동). 세션 쓰기 최소화를 위해
        # 기록 대상이거나 30초 이상 지났을 때만 갱신/저장한다.
        if should_log or last is None or (now - last) >= 30:
            seen[key] = now
            session['_edb_last_seen'] = seen
            session.is_dirty = True
        return should_log

    def _edb_log_access(self, request):
        """접속 내역 1건 INSERT (감사 로그).

        동시요청 중복은 부분 유니크 인덱스(``_DEDUP_INDEX``, 같은 세션·기기·분 1건)
        + ``ON CONFLICT DO NOTHING`` 으로 스냅샷과 무관하게 원자적으로 차단한다.
        감사 로그는 요청 트랜잭션과 독립적으로 별도 커서에 커밋한다. 이 커서만
        READ COMMITTED 로 두어, Odoo 기본 REPEATABLE READ 에서 ON CONFLICT 가
        동시 커밋행 충돌 시 serialization 오류를 내지 않고 조용히 스킵하게 한다.
        """
        user_agent = request.httprequest.user_agent
        platform = user_agent.platform
        # 코어 파서가 뭉뚱그리는 크롬 기반 파생 브라우저를 원본 UA 로 세분화
        browser = self.env['edb.device.access']._browser_from_user_agent(
            user_agent.string, fallback=user_agent.browser,
        )
        ip_address = request.httprequest.remote_addr
        user_id = request.session.uid
        session_identifier = request.session.sid[:STORED_SESSION_BYTES]

        Access = self.env['edb.device.access']
        # 코어 platform 오판(예: 'Crosswalk'→ChromeOS)을 원본 UA 로 보정
        os_family = Access._os_family_from_user_agent(user_agent.string, platform)
        device_type = 'mobile' if Access._is_mobile_user_agent(user_agent.string, platform) else 'computer'

        # 읽기전용 요청 커서는 롤백하고, 항상 별도 쓰기 커서로 독립 커밋한다.
        if self.env.cr.readonly:
            self.env.cr.rollback()
        with self.env.registry.cursor(readonly=False) as cr:
            cr.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
            cr.execute(SQL(
                """
                INSERT INTO edb_device_access
                    (event_type, user_id, session_identifier, access_datetime, device,
                     browser, access_detail, os_family, device_type, ip_address,
                     create_uid, write_uid, create_date, write_date)
                VALUES
                    ('access', %(user_id)s, %(session_identifier)s, %(access_datetime)s,
                     %(device)s, %(browser)s, %(access_detail)s, %(os_family)s, %(device_type)s,
                     %(ip_address)s,
                     %(user_id)s, %(user_id)s, %(access_datetime)s, %(access_datetime)s)
                ON CONFLICT DO NOTHING
                """,
                user_id=user_id,
                session_identifier=session_identifier,
                access_datetime=datetime.now(),
                device=platform,
                browser=browser,
                access_detail=user_agent.string,
                os_family=os_family,
                device_type=device_type,
                ip_address=ip_address,
            ))
            inserted = cr.rowcount
        if inserted:
            _logger.info('접속 내역 적재: user=%s os=%s ip=%s', user_id, os_family, ip_address)
