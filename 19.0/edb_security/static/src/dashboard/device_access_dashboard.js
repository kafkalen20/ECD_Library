/** @odoo-module **/

import { Component, useState, onWillStart, useRef, useEffect } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";

const EDB = "#714b67";
const EDB_SOFT = "#e0b3d1";

export class DeviceAccessDashboard extends Component {
    static template = "edb_security.DeviceAccessDashboard";

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");

        this.trendRef = useRef("trendChart");
        this.deviceRef = useRef("deviceChart");
        this.hourRef = useRef("hourChart");
        this.dowRef = useRef("dowChart");
        this.charts = {};

        this.state = useState({ loading: true, data: null, period: "month" });
        this.PERIODS = [
            { key: "week", label: "주" },
            { key: "month", label: "월" },
            { key: "year", label: "년" },
        ];

        onWillStart(async () => {
            if (typeof Chart === "undefined") {
                await loadJS("/web/static/lib/Chart/Chart.js");
            }
            await this.loadData();
        });

        useEffect(
            () => {
                if (this.state.data) {
                    this.renderAllCharts();
                }
                return () => this.destroyAllCharts();
            },
            () => [this.state.data],
        );
    }

    async loadData() {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call(
                "edb.device.access", "get_access_dashboard_data", [this.state.period],
            );
        } catch (e) {
            console.error("접속 현황 대시보드 로드 실패", e);
        } finally {
            this.state.loading = false;
        }
    }

    onRefresh() {
        this.loadData();
    }

    onExportXlsx() {
        // 선택 기간의 접속 현황을 엑셀(표)로 다운로드
        window.location.href =
            "/edb_security/device_access/export?period=" + encodeURIComponent(this.state.period);
    }

    openList() {
        // 접속 내역 전체 목록 열기
        this.actionService.doAction("edb_security.action_edb_device_access");
    }

    setPeriod(key) {
        if (this.state.period === key) {
            return;
        }
        this.state.period = key;
        this.loadData();
    }

    // ── 기간 라벨 ──
    get windowLabel() {
        return { week: "최근 7일", month: "최근 30일", year: "최근 1년" }[this.state.period] || "";
    }

    get trendTitle() {
        return this.state.period === "year"
            ? "월별 접속 사용자 수 추이"
            : "일별 접속 사용자 수 추이";
    }

    get trendSub() {
        return this.state.period === "year"
            ? "최근 12개월 · 월별 접속한 고유 사용자 수"
            : `${this.windowLabel} · 하루에 접속한 고유 사용자 수`;
    }

    // ── 표시용 헬퍼 ──
    get dateRangeLabel() {
        const r = this.state.data && this.state.data.range;
        return r ? `${r.from} ~ ${r.to}` : "";
    }

    get deltaArrow() {
        const n = this.state.data.kpi.today_delta;
        return n > 0 ? "▲" : (n < 0 ? "▼" : "—");
    }

    get deltaText() {
        const n = this.state.data.kpi.today_delta;
        if (n === 0) return "어제와 동일";
        return `${n > 0 ? "+" : ""}${n} 어제 대비`;
    }

    get wauPct() {
        const k = this.state.data.kpi;
        return k.total_users ? Math.round((k.wau / k.total_users) * 1000) / 10 : 0;
    }

    get mauPct() {
        const k = this.state.data.kpi;
        return k.total_users ? Math.round((k.mau / k.total_users) * 1000) / 10 : 0;
    }

    get mauNote() {
        const k = this.state.data.kpi;
        const diff = k.mau - k.wau;
        return diff <= 0 ? "WAU와 동일 — 신규 유입 없음" : `WAU 대비 +${diff}명`;
    }

    activeStatus() {
        const r = this.state.data.kpi.active_rate;
        return r >= 40
            ? { label: "정상", cls: "b-active", note: "목표 40% 달성" }
            : { label: "주의", cls: "b-low", note: "목표 40% 미달" };
    }

    failedStatus() {
        const n = this.state.data.kpi.failed_login;
        return n === 0
            ? { label: "정상", cls: "b-active", note: `${this.windowLabel} 이상 없음` }
            : { label: "주의", cls: "b-low", note: `${n}건 발생` };
    }

    initial(name) {
        return (name || "?").trim().charAt(0);
    }

    statusLabel(s) {
        return { active: "활발", normal: "보통", low: "저조" }[s] || "-";
    }

    statusClass(s) {
        return { active: "b-active", normal: "b-normal", low: "b-low" }[s] || "b-idle";
    }

    deviceIcon(t) {
        // Odoo 번들 Font Awesome 4.7 기준 아이콘명
        return t === "mobile" ? "fa-mobile" : "fa-desktop";
    }

    // ── 차트 ──
    destroyAllCharts() {
        for (const k of Object.keys(this.charts)) {
            if (this.charts[k]) { this.charts[k].destroy(); this.charts[k] = null; }
        }
    }

    renderAllCharts() {
        const AX = { grid: { color: "#eef0f5" }, ticks: { color: "#8a8f9c", font: { size: 11 } } };
        const NOGRID = { grid: { display: false }, ticks: { color: "#8a8f9c", font: { size: 11 } } };
        const d = this.state.data;

        // 일별 접속 사용자 추이
        if (this.trendRef.el) {
            this.charts.trend = new Chart(this.trendRef.el, {
                type: "line",
                data: {
                    labels: d.trend.labels,
                    datasets: [{
                        label: "접속 사용자 수", data: d.trend.counts, fill: true,
                        borderColor: EDB, backgroundColor: "rgba(113,75,103,.10)",
                        tension: 0.35, pointRadius: 2, pointHoverRadius: 5, borderWidth: 2,
                    }],
                },
                options: {
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: { y: { beginAtZero: true, ...AX }, x: NOGRID },
                },
            });
        }

        // 기기 구분 (가로 누적막대: PC/모바일 막대 안에 OS 세부 누적)
        if (this.deviceRef.el) {
            const nd = d.device_nested;
            const cats = nd.inner.labels;   // ['PC', '모바일']
            const datasets = nd.outer.labels.map((lbl, i) => {
                const dev = nd.outer.devices[i];
                return {
                    label: lbl,
                    // 각 OS 는 자기 기기 카테고리 칸에만 값(나머지 0) → 카테고리별 누적
                    data: cats.map((c) => (c === dev ? nd.outer.data[i] : 0)),
                    backgroundColor: nd.outer.colors[i],
                    borderWidth: 0,
                    barPercentage: 0.6,      // 막대 두께 기본(0.9)의 2/3
                    categoryPercentage: 0.8,
                };
            });
            this.charts.device = new Chart(this.deviceRef.el, {
                type: "bar",
                data: { labels: cats, datasets },
                options: {
                    indexAxis: "y",
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: "bottom", labels: { font: { size: 11 }, boxWidth: 12 } },
                        tooltip: {
                            filter: (item) => item.parsed.x > 0,   // 0 세그먼트 숨김
                            callbacks: { label: (ctx) => ` ${ctx.dataset.label}: ${ctx.parsed.x}` },
                        },
                    },
                    scales: {
                        x: { stacked: true, beginAtZero: true, grid: { color: "#eef0f5" }, ticks: { color: "#8a8f9c", font: { size: 11 } } },
                        y: { stacked: true, grid: { display: false }, ticks: { color: "#55505e", font: { size: 12 } } },
                    },
                },
            });
        }

        // 시간대별 분포 (계단 라인) — 해당 시간대 고유 접속 인원(명)
        if (this.hourRef.el) {
            this.charts.hour = new Chart(this.hourRef.el, {
                type: "line",
                data: {
                    labels: Array.from({ length: 24 }, (_, i) => `${i}`),
                    datasets: [{
                        label: "접속 인원", data: d.hours_users, stepped: true, fill: true,
                        borderColor: "#8a6b82", backgroundColor: "rgba(138,107,130,.12)",
                        pointRadius: 0, pointHoverRadius: 4, borderWidth: 2,
                    }],
                },
                options: {
                    maintainAspectRatio: false,
                    interaction: { mode: "index", intersect: false },
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                title: (items) => `${items[0].label}시`,
                                label: (ctx) => ` 접속 ${ctx.parsed.y}명`,
                            },
                        },
                    },
                    scales: { y: { beginAtZero: true, ...AX }, x: { ...NOGRID, ticks: { ...NOGRID.ticks, maxRotation: 0 } } },
                },
            });
        }

        // 요일별 분포 (세로 막대)
        if (this.dowRef.el) {
            const dowColors = [EDB, EDB, EDB, EDB, EDB, "#cbb6c6", "#cbb6c6"];
            this.charts.dow = new Chart(this.dowRef.el, {
                type: "bar",
                data: {
                    labels: ["월", "화", "수", "목", "금", "토", "일"],
                    datasets: [{ data: d.dow, backgroundColor: dowColors, borderRadius: 4 }],
                },
                options: {
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: { y: { beginAtZero: true, ...AX }, x: NOGRID },
                },
            });
        }
    }
}

registry.category("actions").add("edb_device_access_dashboard", DeviceAccessDashboard);
