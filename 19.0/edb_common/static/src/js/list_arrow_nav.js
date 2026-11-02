/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ListRenderer } from "@web/views/list/list_renderer";

/**
 * 에디터블 리스트(one2many 주문라인 등)에서 방향키로 셀 사이를 이동하는
 * 기능(엑셀식). 모든 편집 가능한 리스트에 전역 적용된다.
 *  - ↑/↓ : 위/아래 라인의 같은 컬럼으로 이동
 *  - ←/→ : 왼쪽/오른쪽 컬럼으로 이동 (Tab 대체) — 단, 셀 내 글자 편집을 해치지
 *    않도록 텍스트 커서가 맨 앞(←)/맨 끝(→)일 때만 컬럼 이동, 그 외엔 커서 이동 유지
 *
 * Tab 은 코어 동작 그대로 유지된다.
 *
 * 안전 처리:
 *  - 여러 줄 입력(textarea)에서는 커서 이동을 방해하지 않도록 제외
 *  - 품목/재고위치 등 Many2one 자동완성 드롭다운이 열린 상태에서 ↑/↓ 는
 *    AutoComplete 가 이벤트를 소비(stopPropagation)하므로 여기까지 오지 않는다
 *    → 드롭다운 항목 탐색 동작 그대로 유지
 *  - 영역/메모 라인(display_type)은 건너뛴다
 */
patch(ListRenderer.prototype, {
    onCellKeydownEditMode(hotkey, cell, group, record) {
        if (record && cell) {
            const active = document.activeElement;
            const isTextarea = active && active.tagName === "TEXTAREA";
            if (!isTextarea) {
                if (
                    (hotkey === "arrowdown" || hotkey === "arrowup") &&
                    this.__edbNavigateRow(hotkey === "arrowdown" ? 1 : -1, cell, record)
                ) {
                    return true;
                }
                if (
                    (hotkey === "arrowleft" || hotkey === "arrowright") &&
                    this.__edbNavigateColumn(hotkey === "arrowright" ? 1 : -1, cell, active)
                ) {
                    return true;
                }
            }
        }
        return super.onCellKeydownEditMode(...arguments);
    },

    /**
     * 같은 라인 내에서 step(+1 오른쪽 / -1 왼쪽) 방향의 편집 가능한 셀로 이동한다.
     * 텍스트 입력 중 커서가 끝/앞이 아닐 때는 셀 내 커서 이동을 유지하기 위해 false.
     */
    __edbNavigateColumn(step, cell, active) {
        if (active && typeof active.selectionStart === "number" && active.value !== undefined) {
            const atStart = active.selectionStart === 0 && active.selectionEnd === 0;
            const atEnd =
                active.selectionStart === active.value.length &&
                active.selectionEnd === active.value.length;
            if (step > 0 && !atEnd) {
                return false;
            }
            if (step < 0 && !atStart) {
                return false;
            }
        }
        const row = cell.parentElement;
        const toFocus =
            step > 0
                ? this.findNextFocusableOnRow(row, cell)
                : this.findPreviousFocusableOnRow(row, cell);
        if (toFocus) {
            this.focus(toFocus);
            return true;
        }
        return false;
    },

    /**
     * 현재 라인 기준 step(+1 아래 / -1 위) 방향의 편집 가능한 라인으로 이동하며,
     * 같은 컬럼에 포커스를 유지한다. 이동 대상이 없으면 false.
     */
    __edbNavigateRow(step, cell, record) {
        const list = this.props.list;
        const records = list.records;
        const idx = records.indexOf(record);
        if (idx === -1) {
            return false;
        }
        let target = null;
        for (let i = idx + step; i >= 0 && i < records.length; i += step) {
            if (!records[i].data.display_type) {
                target = records[i];
                break;
            }
        }
        if (!target) {
            return false;
        }
        const columnName = cell.getAttribute("name");
        const column = columnName
            ? this.columns.find((c) => c.type === "field" && c.name === columnName)
            : null;
        if (column) {
            // 재렌더 후 onPatched 훅이 같은 컬럼 셀로 포커스를 옮긴다.
            this.cellToFocus = { column, record: target };
        }
        list.enterEditMode(target);
        return true;
    },
});
