# -*- coding: utf-8 -*-
"""전역 통합검색(Global Search) 설정 + 검색 서비스.

상단 시스트레이 검색창에서 여러 모델을 여러 필드로 동시에 검색한다.
검색 대상 모델/필드는 이 설정 모델(global.search.config)로 관리하며,
관리자가 화면에서 자유롭게 추가/제거할 수 있다.

검색은 각 모델의 접근권한(ACL)과 레코드 규칙(record rule)을 존중한다.
(사용자 컨텍스트로 search 하므로 볼 수 없는 레코드는 결과에서 자동 제외)

프로젝트 독립적이며 표준 Odoo(base/web)에만 의존한다.
"""
import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# 검색어 최소 길이 (너무 짧으면 전 모델 스캔 낭비)
_MIN_TERM_LEN = 2
# 모델당 기본 결과 상한
_DEFAULT_LIMIT = 8
# o2m 라인 테이블 1회 스캔 시 가져올 최대 라인 수(부모 매핑용, 상위 결과엔 충분)
_O2M_SCAN_LIMIT = 500

# 부제(매칭 힌트)에 쓰는 필드 라벨 한글화 — 코어 필드는 field_description 이 영어라
# 자주 노출되는 것만 한글로 덮는다(커스텀 필드는 이미 한글이라 건드리지 않음).
_KO_FIELD_LABEL = {
    'name': '이름',
    'default_code': '품목코드',
    'barcode': '바코드',
    'ref': '참조',
    'origin': '출처문서',
    'phone': '전화',
    'mobile': '휴대전화',
    'email': '이메일',
    'partner_id': '거래처',
    'product_id': '품목',
}

# '필드 가져오기' 시 o2m/m2m 중 제외할 기술 관계 필드(메일·활동 등은 접두사로도 거름)
_IMPORT_SKIP_REL = {
    'message_ids', 'message_follower_ids', 'message_partner_ids',
    'activity_ids', 'website_message_ids', 'rating_ids',
    'access_url', 'my_activity_date_deadline',
}


class GlobalSearchConfig(models.Model):
    _name = 'global.search.config'
    _description = '통합검색 설정'
    _order = 'sequence, id'

    name = fields.Char(
        string='표시 라벨',
        help='검색 결과에서 이 모델 그룹의 제목. 비우면 모델 이름을 사용.',
    )
    model_id = fields.Many2one(
        'ir.model', string='대상 모델', required=True, ondelete='cascade',
        help='통합검색이 조회할 모델.',
    )
    model_name = fields.Char(
        related='model_id.model', string='모델 기술명', store=True, index=True,
    )
    line_ids = fields.One2many(
        'global.search.config.line', 'config_id', string='검색 대상 필드',
        help='이 모델에서 검색할 필드 목록. 직접 필드는 선택, 관련 필드는 점 표기 경로로.',
    )
    title_path = fields.Char(
        string='제목 필드',
        help='검색 결과 제목에 표시할 필드 경로(선택). 비우면 레코드 표시명을 사용.\n'
             'sale.order.line 처럼 자체 이름이 없는 라인 모델에서 부모 정보를 '
             '제목으로 쓰고 싶을 때 사용. 예: order_id.name',
    )
    sequence = fields.Integer(string='순서', default=10)
    result_limit = fields.Integer(
        string='최대 결과 수', default=_DEFAULT_LIMIT,
        help='이 모델에서 한 번에 표시할 최대 결과 개수.',
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('model_uniq', 'unique(model_id)',
         '이미 등록된 모델입니다. 모델당 하나의 설정만 가능합니다.'),
    ]

    # ── 액션 ──────────────────────────────────────────────────────
    def action_import_all_fields(self):
        """대상 모델의 검색 가능 필드를 모두 라인으로 추가(기존은 유지).

        - 직접 검색 필드(char/text/html/selection/many2one, 저장)는 필드로 추가.
        - o2m/m2m 관계 필드도 필드로 추가. 하위 필드까지 검색하려면 이후
          '하위 필드'에서 골라 담는다(예: line_ids → 품목·이력번호·바코드).
        - 메일/활동 등 기술 관계 필드는 잡음이라 제외.
        불필요한 라인은 이후 삭제하면 된다.
        """
        self.ensure_one()
        if not self.model_id:
            raise ValidationError('대상 모델을 먼저 선택하세요.')
        existing_field_ids = self.line_ids.mapped('field_id').ids
        seq = max(self.line_ids.mapped('sequence') or [0])
        new_lines = []

        # 1) 직접 검색 필드
        direct = self.env['ir.model.fields'].search([
            ('model_id', '=', self.model_id.id),
            ('ttype', 'in', ['char', 'text', 'html', 'selection', 'many2one']),
            ('store', '=', True),
            ('name', 'not in', ['display_name']),
            ('id', 'not in', existing_field_ids),
        ])
        for f in direct:
            seq += 10
            new_lines.append((0, 0, {'field_id': f.id, 'sequence': seq}))

        # 2) o2m/m2m 관계 필드 → 필드로 추가(하위 필드는 이후 '하위 필드'에서 선택)
        #    단, 도메인 검색이 되는 것만(계산형 o2m 등 검색 불가 필드는 제외).
        Model = self.env[self.model_name] if self.model_name in self.env else None
        relational = self.env['ir.model.fields'].search([
            ('model_id', '=', self.model_id.id),
            ('ttype', 'in', ['one2many', 'many2many']),
            ('id', 'not in', existing_field_ids),
        ])
        for f in relational:
            if (f.name in _IMPORT_SKIP_REL
                    or f.name.startswith(('message_', 'activity_', 'website_'))):
                continue
            fld = Model._fields.get(f.name) if Model is not None else None
            searchable = fld is not None and (
                fld.store or fld.search or getattr(fld, 'inverse_name', None))
            if not searchable:
                continue
            seq += 10
            new_lines.append((0, 0, {'field_id': f.id, 'sequence': seq}))

        if new_lines:
            self.write({'line_ids': new_lines})
        return True

    # ── 헬퍼 ──────────────────────────────────────────────────────
    def _line_paths(self, line):
        """라인의 검색 경로 목록.
        - 필드 + 하위필드 선택 → '필드.하위필드' 들.
        - 필드만(하위필드 없음) → 필드명(o2m 는 대표이름 검색).
        """
        if not line.field_id:
            return []
        base = line.field_id.name
        if line.sub_field_ids:
            return ['%s.%s' % (base, s.name) for s in line.sub_field_ids]
        return [base]

    def _search_paths(self, cfg):
        """검색/부제에 쓰는 경로 목록(중복 제거)."""
        out = []
        for line in cfg.line_ids:
            out.extend(self._line_paths(line))
        return list(dict.fromkeys(out))

    def _build_search_domain(self, cfg, model_name, term):
        """검색 도메인 조립. 성능 최적화:
        - 직접 필드/m2o·m2m 경로 → 부모에 OR ilike 리프.
        - o2m 경로 → 라인(comodel) 테이블을 1번만 검색해 부모 id 로 매핑
          (부모 행마다 도는 상관 서브쿼리를 피해 훨씬 빠름).
        하위필드 미선택 o2m 은 대표이름만 검색(빠른 기본값).
        leaf 가 하나도 없으면 None.
        """
        Model = self.env[model_name]
        direct_leaves = []          # 부모 OR 리프
        o2m_roots = {}              # root -> {comodel, inverse, subfields[]}
        for path in self._search_paths(cfg):
            root = path.split('.')[0]
            f = Model._fields.get(root)
            inverse = getattr(f, 'inverse_name', None) if f else None
            if f is not None and f.type == 'one2many' and inverse:
                grp = o2m_roots.setdefault(root, {
                    'comodel': f.comodel_name, 'inverse': inverse, 'subfields': []})
                if '.' in path:
                    grp['subfields'].append(path.split('.', 1)[1])
                else:
                    rn = self.env[f.comodel_name]._rec_name
                    if rn:
                        grp['subfields'].append(rn)
            else:
                # 도메인에 쓸 수 없는 필드(계산형 o2m/m2m 등 저장·검색 불가)는
                # 건너뛴다 — 하나 때문에 모델 전체 검색이 죽지 않도록.
                if f is not None and not f.store and not f.search:
                    continue
                direct_leaves.append((path, 'ilike', term))

        # o2m: comodel 1회 검색 → 부모 id 수집
        parent_ids = set()
        for grp in o2m_roots.values():
            subs = list(dict.fromkeys(grp['subfields']))
            if not subs:
                continue
            sub_leaves = [(s, 'ilike', term) for s in subs]
            subdom = ['|'] * (len(sub_leaves) - 1) + sub_leaves
            try:
                lines = self.env[grp['comodel']].search(subdom, limit=_O2M_SCAN_LIMIT)
            except Exception:
                continue
            parent_ids.update(lines.mapped(grp['inverse']).ids)

        leaves = list(direct_leaves)
        if parent_ids:
            leaves.append(('id', 'in', list(parent_ids)))
        if not leaves:
            return None
        return ['|'] * (len(leaves) - 1) + leaves

    def _path_label_for(self, model_name, path):
        """경로의 부제 라벨: 한글 매핑 > 경로 끝 필드 라벨 > 기술명."""
        last = path.split('.')[-1]
        if last in _KO_FIELD_LABEL:
            return _KO_FIELD_LABEL[last]
        return self._path_field_label(model_name, path) or last

    def _path_field_label(self, model_name, path):
        """경로 끝 필드의 실제 라벨(string)을 대상 모델 정의에서 조회. 실패 시 None."""
        model = model_name
        label = None
        try:
            for part in path.split('.'):
                if not model or model not in self.env:
                    return None
                fld = self.env[model]._fields.get(part)
                if not fld:
                    return None
                label = fld.string
                model = fld.comodel_name if fld.relational else None
        except Exception:
            return None
        return label

    def _matched_value(self, rec, path, term):
        """경로값 중 검색어를 포함하는 첫 텍스트를 반환(없으면 None).

        rec.mapped(path) 로 o2m/m2o 를 타고 값을 모으므로 라인 경로도 처리된다.
        """
        tl = term.lower()
        try:
            vals = rec.mapped(path)
        except Exception:
            return None
        for v in vals:
            if not v:
                continue
            text = v.display_name if hasattr(v, 'display_name') else str(v)
            if text and tl in text.lower():
                return text
        return None

    def _read_path(self, record, path):
        """레코드에서 점 표기 경로 값을 안전하게 읽어 문자열로 반환."""
        value = record
        try:
            for part in path.split('.'):
                if not value:
                    return ''
                value = value[part] if not hasattr(value, part) else getattr(value, part)
            if not value:
                return ''
            # Many2one 등 레코드면 display_name
            if hasattr(value, 'display_name'):
                return value.display_name or ''
            return str(value)
        except Exception:
            return ''

    def _match_hint(self, rec, cfg, term):
        """검색어가 실제로 걸린 경로를 찾아 '라벨: 값' 힌트를 반환.

        관계 경로(line_ids.product_id 등)도 처리한다. 타이틀과 중복되는 값은
        건너뛰고, 매칭 필드가 없으면 부제 없음('').
        """
        title = (rec.display_name or '').lower()
        for path in self._search_paths(cfg):
            text = self._matched_value(rec, path, term)
            if text and text.lower() != title:
                return '%s: %s' % (self._path_label_for(cfg.model_name, path), text)
        # 매칭 필드를 못 찾으면 부제 없음
        return ''

    # ── 검색 서비스 ────────────────────────────────────────────────
    @api.model
    def search_global(self, term, limit_per_model=None):
        """활성 설정 모델을 순회하며 term 을 다중 필드로 검색.

        각 모델의 has_access + record rule 을 존중한다(사용자 컨텍스트 search).
        반환: 결과가 있는 그룹 리스트
          [{'model', 'label', 'count', 'records':[{'id','name','subtitle'}]}]
        """
        term = (term or '').strip()
        if len(term) < _MIN_TERM_LEN:
            return []

        groups = []
        configs = self.search([('active', '=', True)], order='sequence, id')
        for cfg in configs:
            model_name = cfg.model_name
            if not model_name or model_name not in self.env:
                continue
            Model = self.env[model_name]
            # 접근권한 없으면 skip (사용자가 못 보는 모델 제외)
            try:
                if not Model.has_access('read'):
                    continue
            except Exception:
                continue

            try:
                domain = self._build_search_domain(cfg, model_name, term)
            except Exception as e:
                _logger.warning(
                    "통합검색 '%s' 도메인 조립 실패(설정 확인): %s", model_name, e)
                continue
            if domain is None:
                continue

            try:
                recs = Model.search(domain, limit=cfg.result_limit or _DEFAULT_LIMIT)
            except Exception as e:
                # 잘못된 필드 경로 등 — 이 모델만 건너뛰고 전체는 계속
                _logger.warning(
                    "통합검색 '%s' 모델 검색 실패(설정 확인 필요): %s", model_name, e)
                continue

            if not recs:
                continue

            records = []
            for rec in recs:
                # 제목: title_path 가 설정되면 그 경로값(예: 라인 → order_id.name),
                # 아니면 표시명. 라인 같은 o2m 모델은 자체 표시명이 없어 부모 정보를 쓴다.
                if cfg.title_path:
                    name = self._read_path(rec, cfg.title_path)
                else:
                    name = rec.display_name
                records.append({
                    'id': rec.id,
                    'name': name or '(이름 없음)',
                    'subtitle': self._match_hint(rec, cfg, term),
                    'open_model': model_name,
                    'open_id': rec.id,
                })
            groups.append({
                'model': model_name,
                'label': cfg.name or cfg.model_id.name or model_name,
                'count': len(records),
                # '전체보기' 버튼이 목록뷰를 같은 조건으로 열 수 있도록 검색 도메인 동봉.
                # (튜플은 JSON 직렬화 시 배열이 되어 그대로 유효한 Odoo 도메인)
                'domain': domain,
                'records': records,
            })

        return groups


class GlobalSearchConfigLine(models.Model):
    _name = 'global.search.config.line'
    _description = '통합검색 대상 필드'
    _order = 'sequence, id'

    config_id = fields.Many2one(
        'global.search.config', string='설정', required=True, ondelete='cascade',
    )
    model_id = fields.Many2one(
        related='config_id.model_id', string='대상 모델', store=True,
    )
    sequence = fields.Integer(string='순서', default=10)
    field_id = fields.Many2one(
        'ir.model.fields', string='필드', ondelete='cascade',
        domain="[('model_id', '=', model_id),"
               " ('ttype', 'in', ['char', 'text', 'html', 'selection',"
               " 'many2one', 'one2many', 'many2many'])]",
        help='이 모델에서 검색할 필드를 선택. 직접 필드는 그 값으로, 관계 필드'
             '(거래처 등)는 표시명으로 검색됩니다. 라인 같은 o2m 를 고르면 오른쪽'
             " '하위 필드'에서 검색할 세부 필드를 골라 담을 수 있습니다.",
    )
    field_relation = fields.Char(
        related='field_id.relation', string='관계 대상 모델',
        help='선택한 필드가 관계 필드이면 그 대상 모델(하위 필드 선택 대상).',
    )
    sub_field_ids = fields.Many2many(
        'ir.model.fields', 'global_search_line_subfield_rel',
        'line_id', 'field_id', string='하위 필드',
        domain="[('model', '=', field_relation),"
               " ('ttype', 'in', ['char', 'text', 'html', 'selection', 'many2one'])]",
        help='관계 필드(o2m/m2o)에서 검색할 하위 필드만 골라 담기(선택). 예: '
             'line_ids 필드에서 품목·이력번호·바코드만 선택. 비우면 대표이름만 검색.',
    )
    # ── 표시 컬럼(읽기 전용) — 경로 끝 필드 기준으로 자동 채움 ──
    # 선택한 필드 기준으로 라벨·유형·읽기전용 등을 표시(하위 필드는 태그로 별도).
    field_name = fields.Char(string='필드명', compute='_compute_field_info')
    field_label = fields.Char(string='필드 라벨', compute='_compute_field_info')
    field_ttype = fields.Char(string='필드 유형', compute='_compute_field_info')
    field_required = fields.Boolean(string='요청함', compute='_compute_field_info')
    field_readonly = fields.Boolean(string='읽기 전용', compute='_compute_field_info')
    field_index = fields.Boolean(string='색인화', compute='_compute_field_info')
    field_state = fields.Char(string='유형', compute='_compute_field_info')
    display_name = fields.Char(compute='_compute_display_name')

    _sql_constraints = [
        ('field_uniq', 'unique(config_id, field_id)',
         '이미 추가된 필드입니다.'),
    ]

    @api.depends('field_id')
    def _compute_field_info(self):
        """선택한 필드 기준으로 표시 컬럼(라벨·유형·읽기전용 등)을 채운다.
        하위 필드는 sub_field_ids 태그로 별도 표시."""
        state_label = {'base': '기본 필드', 'manual': '사용자 정의'}
        for line in self:
            f = line.field_id
            line.field_name = f.name if f else ''
            line.field_label = f.field_description if f else False
            line.field_ttype = f.ttype if f else False
            line.field_required = f.required if f else False
            line.field_readonly = f.readonly if f else False
            line.field_index = f.index if f else False
            line.field_state = state_label.get(f.state, f.state) if f else False

    @api.depends('field_id')
    def _compute_display_name(self):
        for line in self:
            line.display_name = line.field_id.name or '?'
