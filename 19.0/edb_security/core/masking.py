# -*- coding: utf-8 -*-
"""로그에 남는 문자열에서 개인정보 패턴을 제거한다.

한계: 이름·주소는 패턴이 없어 걸러지지 않는다 (설계서 §8.1).
"""
import re

_PATTERNS = (
    # 주민등록번호·외국인등록번호를 전화번호보다 먼저 검사한다 (자릿수가 겹친다).
    # 성별코드 1-4 는 내국인, 5-8 은 외국인이다.
    (re.compile(r'\b\d{6}[-\s]?[1-8]\d{6}\b'), '[RRN]'),
    (re.compile(r'\b[\w.+-]+@[\w-]+\.[\w.-]+\b'), '[EMAIL]'),
    # 국제 형식(+82-10-1234-5678)을 국내 형식보다 먼저 잡는다.
    # 먼저 잡지 않으면 계좌번호 패턴이 앞부분만 삼켜 뒷자리가 노출된다.
    (re.compile(r'\+?\d{1,3}[-.\s]\d{1,2}[-.\s]\d{3,4}[-.\s]\d{4}\b'), '[PHONE]'),
    (re.compile(r'\b0\d{1,2}[-.\s]?\d{3,4}[-.\s]?\d{4}\b'), '[PHONE]'),
    # 계좌번호: 하이픈 3그룹이면서 전체 숫자가 11자리 이상인 것만.
    # 자릿수 하한이 없으면 ISO 날짜(2026-09-17)와 레코드 ID 범위를 오탐한다.
    (re.compile(r'\b(?=(?:\d-?){11,})\d{2,6}-\d{2,6}-\d{2,8}\b'), '[ACCOUNT]'),
)

MAX_LEN = 4000


def mask(text):
    if not text:
        return text
    out = str(text)
    for pattern, token in _PATTERNS:
        out = pattern.sub(token, out)
    if len(out) > MAX_LEN:
        out = out[:MAX_LEN] + '…(truncated)'
    return out


def mask_value(value):
    """dict / list / str 재귀 마스킹. 그 외 타입은 그대로 둔다."""
    if isinstance(value, str):
        return mask(value)
    if isinstance(value, dict):
        return {k: mask_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [mask_value(v) for v in value]
    return value
