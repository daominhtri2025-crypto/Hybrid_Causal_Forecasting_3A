@extends('layouts.dashboard')

@section('title', 'Cointegration')
@section('page-title', 'Phase 3 — Johansen Cointegration')
@section('page-subtitle', 'Cointegration rank determination and model route selection')

@section('export-buttons')
<button class="btn-export" data-export="coint-export" onclick="exportSectionPDF('coint-export', 'phase3_cointegration.pdf')">
    <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
    Export PDF
</button>
@endsection

@section('content')
<div id="coint-export">

{{-- Explainer --}}
<div class="explainer-card mb-6">
    <div class="explainer-header" onclick="toggleExplainer('explain-coint')">
        <div class="explainer-header-left">
            <div class="explainer-icon">
                <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            </div>
            <div>
                <div class="explainer-title">Kiểm định đồng tích hợp Johansen</div>
                <div class="explainer-subtitle">Các biến có mối quan hệ cân bằng dài hạn không? — Johansen (1991)</div>
            </div>
        </div>
        <svg id="explain-coint-icon" class="explainer-chevron" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
    </div>
    <div id="explain-coint" class="explainer-body hidden math-content">
        <p>
            Kiểm định Johansen xác định số lượng <span class="highlight">quan hệ đồng tích hợp</span> (cointegration rank $r$)
            giữa các chuỗi thời gian. Nếu $r > 0$, các biến có mối quan hệ cân bằng dài hạn → dùng mô hình VECM.
            Nếu $r = 0$ hoặc $r = k$ (full rank), dùng VAR trên mức gốc (levels).
        </p>

        <div class="formula-block">
            <div class="formula-label">Dạng VECM (Vector Error Correction)</div>
            $$\Delta Y_t = \Pi Y_{t-1} + \sum_{i=1}^{p-1} \Gamma_i \Delta Y_{t-i} + \varepsilon_t$$
        </div>

        <p>
            Trong đó ma trận $\Pi = \alpha \beta'$ với rank $r$. Kiểm định <span class="highlight">Trace test</span>
            tuần tự kiểm tra $H_0: r \leq r_0$ so với $H_1: r > r_0$, bắt đầu từ $r_0 = 0$.
        </p>

        <div class="hypothesis-box">
            <div class="hyp hyp-h0">
                <strong>H₀:</strong> Rank $\leq r_0$ — số quan hệ đồng tích hợp không vượt quá $r_0$
            </div>
            <div class="hyp hyp-h1">
                <strong>H₁:</strong> Rank $> r_0$ — có thêm quan hệ đồng tích hợp
            </div>
        </div>

        <p>
            <span class="highlight-orange">Quyết định route:</span> Khi rank $r = k$ (full rank, bằng số biến),
            ma trận $\Pi$ khả nghịch → không có đồng tích hợp thực sự → chọn <span class="highlight">VAR on Levels</span>.
        </p>
    </div>
</div>

<div id="coint-root">
    <div id="coint-loading">
        <div class="rounded-xl p-6 animate-pulse" style="background-color: var(--color-bg-card);">
            <div class="h-4 w-48 rounded mb-4" style="background-color: var(--color-border);"></div>
            <div class="h-32 rounded" style="background-color: var(--color-bg-input);"></div>
        </div>
    </div>
    <div id="coint-error" class="hidden"></div>
    <div id="coint-content" class="hidden space-y-6">
        {{-- Route decision --}}
        <div class="rounded-xl p-6 border" id="route-decision" style="background-color: var(--color-bg-card); border-color: var(--color-border);"></div>
        {{-- Rank tests table --}}
        <div id="coint-table-wrap" class="rounded-xl border overflow-hidden" style="background-color: var(--color-bg-card); border-color: var(--color-border);">
            <div class="overflow-x-auto">
                <table class="w-full text-sm">
                    <thead>
                        <tr style="background-color: var(--color-bg-input);">
                            <th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider" style="color: var(--color-text-muted);">H0: rank ≤ r</th>
                            <th class="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider" style="color: var(--color-text-muted);">Trace Stat</th>
                            <th class="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider" style="color: var(--color-text-muted);">Critical (5%)</th>
                            <th class="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider" style="color: var(--color-text-muted);">Decision</th>
                        </tr>
                    </thead>
                    <tbody id="coint-tbody"></tbody>
                </table>
            </div>
        </div>
        {{-- Shown when Johansen test was skipped --}}
        <div id="coint-skipped" class="hidden rounded-xl p-5 border" style="background-color: var(--color-bg-card); border-color: var(--color-border);"></div>
    </div>
</div>

</div>
@endsection

@push('scripts')
<script type="module">
    async function load() {
        try {
            const data = await window.dashboardFetch('cointegration');
            document.getElementById('coint-loading').classList.add('hidden');
            document.getElementById('coint-content').classList.remove('hidden');
            render(data);
        } catch (err) {
            document.getElementById('coint-loading').classList.add('hidden');
            document.getElementById('coint-error').classList.remove('hidden');
            window.showError('coint-error', err.message);
        }
    }

    function render(data) {
        const routeStr = (data.route ?? '—').replace(/_/g, ' ');
        const rank = data.rank ?? '—';
        const explanation = data.route_explanation ?? '';

        document.getElementById('route-decision').innerHTML = `
            <div class="flex items-start gap-4">
                <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg"
                     style="background-color: rgba(59,130,246,0.15);">
                    <svg class="h-5 w-5" style="color: var(--color-accent-blue);" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/>
                    </svg>
                </div>
                <div>
                    <h3 class="text-base font-semibold" style="color: var(--color-text-primary);">
                        Route: ${routeStr}
                    </h3>
                    <p class="mt-1 text-sm" style="color: var(--color-text-secondary);">
                        Cointegration rank r = ${rank} &middot; ${explanation}
                    </p>
                </div>
            </div>
        `;

        const tests = data.trace_test?.details ?? [];
        if (tests.length === 0) {
            document.getElementById('coint-table-wrap').classList.add('hidden');
            const skipped = document.getElementById('coint-skipped');
            skipped.classList.remove('hidden');
            skipped.innerHTML = `
                <div class="flex items-start gap-3">
                    <svg class="h-5 w-5 shrink-0 mt-0.5" style="color: var(--color-accent-cyan);" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                    </svg>
                    <div>
                        <p class="text-sm font-medium" style="color: var(--color-text-primary);">Bảng Trace test không có dữ liệu</p>
                        <p class="mt-1 text-xs" style="color: var(--color-text-muted);">
                            Tất cả biến đều dừng ở mức I(0) → full rank → pipeline bỏ qua kiểm định Johansen.
                            Route được xác định trực tiếp từ kết quả Phase 1.
                        </p>
                    </div>
                </div>
            `;
        } else {
            document.getElementById('coint-tbody').innerHTML = tests.map(t => {
                const cv95 = t.critical_values?.['95%'] ?? null;
                const rejected = t.reject_h0_at_5pct ?? ((t.statistic ?? 0) > (cv95 ?? Infinity));
                return `
                    <tr class="border-t" style="border-color: var(--color-border);">
                        <td class="px-4 py-3 font-medium" style="color: var(--color-text-primary);">${t.h0 ?? '?'}</td>
                        <td class="px-4 py-3 text-right tabular-nums" style="color: var(--color-text-primary);">${t.statistic?.toFixed(3) ?? '—'}</td>
                        <td class="px-4 py-3 text-right tabular-nums" style="color: var(--color-text-secondary);">${cv95?.toFixed(3) ?? '—'}</td>
                        <td class="px-4 py-3 text-center">
                            ${rejected
                                ? '<span class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium" style="background-color: rgba(239,68,68,0.15); color: var(--color-accent-red);">Reject</span>'
                                : '<span class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium" style="background-color: rgba(34,197,94,0.15); color: var(--color-kpi-positive);">Fail to Reject</span>'}
                        </td>
                    </tr>
                `;
            }).join('');
        }
    }

    load();
</script>
@endpush
