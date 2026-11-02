/** @odoo-module */

// 전역 통합검색(Global Search) — 상단 시스트레이 검색창.
// 백엔드 global.search.config.search_global 을 호출해 여러 모델을 여러 필드로
// 동시에 검색하고, 그룹별 결과를 드롭다운으로 표시. 클릭 시 해당 레코드 폼을 연다.

import { Component, useState, useRef, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { debounce } from "@web/core/utils/timing";

const MIN_TERM_LEN = 2;

export class GlobalSearch extends Component {
    static template = "global_search.GlobalSearch";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            term: "",
            groups: [],
            open: false,
            loading: false,
            searched: false,
            activeIndex: -1,   // 키보드로 선택 중인 결과의 평면(flat) 인덱스
        });
        this.rootRef = useRef("root");
        this._searchSeq = 0;   // stale 응답 가드용 요청 순번

        // 바깥 클릭 시 패널 닫기
        this._onDocClick = (ev) => {
            if (this.rootRef.el && !this.rootRef.el.contains(ev.target)) {
                this.state.open = false;
            }
        };
        document.addEventListener("click", this._onDocClick, true);
        onWillUnmount(() => document.removeEventListener("click", this._onDocClick, true));

        this._debouncedSearch = debounce(this._search.bind(this), 300);
    }

    get showNoResults() {
        return this.state.searched && !this.state.loading && this.state.groups.length === 0;
    }

    // 키보드 이동을 위해 모든 그룹의 항목을 순서대로 평면화
    get flatItems() {
        const out = [];
        for (const g of this.state.groups) {
            for (const r of g.records) {
                // open_model/open_id 는 부모 리다이렉트 지원(라인 → 부모 레코드)
                out.push({ model: r.open_model || g.model, id: r.open_id || r.id });
            }
        }
        return out;
    }

    // 텍스트를 검색어 기준으로 잘라 [{text, hit}] 조각 배열로 반환(하이라이트용)
    highlightParts(text) {
        const term = this.state.term.trim();
        if (!term || !text) {
            return [{ text: text || "", hit: false }];
        }
        const parts = [];
        const lower = text.toLowerCase();
        const t = term.toLowerCase();
        let idx = 0;
        let pos;
        while ((pos = lower.indexOf(t, idx)) !== -1) {
            if (pos > idx) {
                parts.push({ text: text.slice(idx, pos), hit: false });
            }
            parts.push({ text: text.slice(pos, pos + term.length), hit: true });
            idx = pos + term.length;
        }
        if (idx < text.length) {
            parts.push({ text: text.slice(idx), hit: false });
        }
        return parts;
    }

    onInput(ev) {
        this.state.term = ev.target.value;
        this.state.activeIndex = -1;
        if (this.state.term.trim().length < MIN_TERM_LEN) {
            this.state.groups = [];
            this.state.searched = false;
            this.state.loading = false;   // 진행 중 표시 해제(안 하면 '검색 중...' 잔류)
            this.state.open = false;      // 보여줄 게 없으니 빈 패널 닫기
            this._searchSeq++;            // 진행 중이던 응답 무효화
            return;
        }
        this.state.open = true;
        this._debouncedSearch();
    }

    onFocus() {
        if (this.state.term.trim().length >= MIN_TERM_LEN) {
            this.state.open = true;
        }
    }

    onKeydown(ev) {
        if (ev.key === "Escape") {
            this.state.open = false;
            ev.target.blur();
            return;
        }
        const items = this.flatItems;
        if (!this.state.open || !items.length) {
            return;
        }
        if (ev.key === "ArrowDown") {
            ev.preventDefault();
            this.state.activeIndex = Math.min(this.state.activeIndex + 1, items.length - 1);
            this._scrollActiveIntoView();
        } else if (ev.key === "ArrowUp") {
            ev.preventDefault();
            this.state.activeIndex = Math.max(this.state.activeIndex - 1, 0);
            this._scrollActiveIntoView();
        } else if (ev.key === "Enter") {
            const it = items[this.state.activeIndex];
            if (it) {
                ev.preventDefault();
                this.openRecord(it.model, it.id);
            }
        }
    }

    _scrollActiveIntoView() {
        // 렌더 반영 후 활성 항목을 패널 안에서 보이게 스크롤
        window.requestAnimationFrame(() => {
            const el = this.rootRef.el
                && this.rootRef.el.querySelector(".o_global_search_item.active");
            if (el) {
                el.scrollIntoView({ block: "nearest" });
            }
        });
    }

    async _search() {
        const term = this.state.term.trim();
        if (term.length < MIN_TERM_LEN) {
            return;
        }
        const seq = ++this._searchSeq;
        this.state.loading = true;
        try {
            const groups = await this.orm.call(
                "global.search.config", "search_global", [term]
            );
            // 늦게 도착한 이전 요청의 응답이면 버림(최신 것만 반영)
            if (seq !== this._searchSeq) {
                return;
            }
            // 키보드 이동용 평면 인덱스를 각 레코드에 부여
            let i = 0;
            for (const g of groups || []) {
                for (const r of g.records) {
                    r._i = i++;
                }
            }
            this.state.groups = groups || [];
            this.state.activeIndex = -1;
            this.state.searched = true;
        } finally {
            if (seq === this._searchSeq) {
                this.state.loading = false;
            }
        }
    }

    async openRecord(model, resId) {
        this.state.open = false;
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: model,
            res_id: resId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    // 그룹의 '전체보기' — 같은 검색조건(다중필드 OR)으로 목록뷰를 열어 전 결과 조회
    async openAll(group) {
        this.state.open = false;
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: `${group.label} — "${this.state.term.trim()}"`,
            res_model: group.model,
            domain: group.domain,
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }
}

// 시스트레이(상단 네비바)에 등록
registry.category("systray").add(
    "global_search",
    { Component: GlobalSearch },
    { sequence: 1 }
);
