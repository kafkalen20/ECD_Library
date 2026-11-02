# -*- coding: utf-8 -*-
{
    'name': '전역 통합검색 (Global Search)',
    'version': '19.0.1.0.0',
    'category': 'Tools',
    'summary': '상단 시스트레이 검색창에서 여러 모델을 여러 필드로 동시에 검색',
    'description': """
전역 통합검색 (Global Search)
=============================

상단 시스트레이(네비바) 검색창 하나에서 **여러 모델을 여러 필드로 동시에** 검색한다.

- 검색 대상 모델/필드는 설정 모델(``global.search.config``)로 관리 — 관리자가
  화면에서 자유롭게 추가/제거 (코드 수정 불필요).
- o2m 필드는 '하위 필드' 다중 선택으로 라인 내부까지 검색.
- 각 모델의 접근권한(ACL)·레코드 규칙(record rule)을 존중 (사용자 컨텍스트 검색).
- 결과 UX: 그룹별 표시, 검색어 하이라이트, 키보드 내비게이션(↑↓/Enter),
  그룹별 '전체보기'(목록뷰 열기).

프로젝트 독립적이며 표준 Odoo(base/web)에만 의존한다. 원하는 대상 모델은
설정 > 기술 > 사용자 인터페이스 > 통합검색 (개발자모드)에서 등록한다.
""",
    'author': 'Ecodoo',
    'website': 'https://www.ecodoobiz.com',
    'license': 'LGPL-3',
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/global_search_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'global_search/static/src/js/global_search/global_search.js',
            'global_search/static/src/js/global_search/global_search.xml',
            'global_search/static/src/js/global_search/global_search.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
