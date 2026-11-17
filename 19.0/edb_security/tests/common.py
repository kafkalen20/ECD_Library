# -*- coding: utf-8 -*-


def create_user(env, vals):
    """테스트용 사용자를 만든다.

    branch_hlb 같은 모듈이 설치된 DB(HLB 운영 복제본)에서는 res.users 에
    branch_id 가 필수라 기본 값만으로는 create 가 ValidationError 를 낸다.
    그 필드가 있으면 아무 사업장 하나를 채운다. 없으면 그대로 만든다.
    """
    Users = env['res.users']
    if 'branch_id' in Users._fields:
        branch = env['res.branch'].sudo().search([], limit=1)
        vals = dict(vals, branch_id=branch.id, branch_ids=[(6, 0, branch.ids)])
    return Users.create(vals)
