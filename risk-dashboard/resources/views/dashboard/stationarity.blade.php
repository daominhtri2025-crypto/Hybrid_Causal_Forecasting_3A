@extends('layouts.dashboard')

@section('title', 'Stationarity')
@section('page-title', 'Phase 1 — Unit Root Tests')
@section('page-subtitle', 'ADF and KPSS stationarity results with Zivot-Andrews tiebreaker')

@section('export-buttons')
<button class="btn-export" data-export="stationarity-export" onclick="exportSectionPDF('stationarity-export', 'phase1_stationarity.pdf')">
    <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
    <span data-i18n="header.export_pdf">Export PDF</span>
</button>
@endsection

@section('content')
<div id="stationarity-export">

{{-- Explainer --}}
<div class="explainer-card mb-6">
    <div class="explainer-header" onclick="toggleExplainer('explain-station')">
        <div class="explainer-header-left">
            <div class="explainer-icon">
                <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            </div>
            <div>
                <div class="explainer-title">
                    <span data-lang="vi">Kiểm định tính dừng (Unit Root Tests)</span>
                    <span data-lang="en" style="display: none;">Unit Root Tests (Stationarity)</span>
                </div>
                <div class="explainer-subtitle">
                    <span data-lang="vi">ADF, KPSS và Zivot-Andrews — tại sao cần kiểm tra trước khi mô hình hóa?</span>
                    <span data-lang="en" style="display: none;">ADF, KPSS and Zivot-Andrews — why test before modeling?</span>
                </div>
            </div>
        </div>
        <svg id="explain-station-icon" class="explainer-chevron" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
    </div>
    <div id="explain-station" class="explainer-body hidden math-content">
        <div data-lang="vi">
            <p>
                Trước khi xây dựng mô hình VAR, ta cần xác định <span class="highlight">bậc tích hợp</span> của từng chuỗi thời gian.
                Nếu chuỗi không dừng (non-stationary), các kiểm định thống kê truyền thống sẽ cho kết quả giả (spurious regression).
            </p>

            <div class="formula-block">
                <div class="formula-label">Augmented Dickey-Fuller (ADF) Test</div>
                $$\Delta Y_t = \alpha + \beta t + \gamma Y_{t-1} + \sum_{i=1}^{p} \delta_i \Delta Y_{t-i} + \varepsilon_t$$
            </div>

            <p>
                <span class="highlight">ADF</span>: Kiểm định giả thuyết $H_0$: $\gamma = 0$ (có unit root → không dừng).
                Nếu bác bỏ $H_0$ → chuỗi dừng. Bậc lag $p$ được chọn tự động theo tiêu chí Schwert.
            </p>

            <div class="hypothesis-box">
                <div class="hyp hyp-h0">
                    <strong>H₀ (ADF):</strong> Chuỗi có unit root → không dừng
                </div>
                <div class="hyp hyp-h1">
                    <strong>H₁ (ADF):</strong> Chuỗi dừng (stationary)
                </div>
            </div>

            <p>
                <span class="highlight-orange">KPSS</span>: Kiểm định ngược chiều — $H_0$: chuỗi dừng.
                Kết hợp ADF + KPSS giúp tránh sai lầm loại I/II. Khi hai kiểm định mâu thuẫn,
                pipeline tự động chạy <span class="highlight">Zivot-Andrews (1992)</span> — cho phép 1 structural break nội sinh — làm tiebreaker.
            </p>
        </div>
        <div data-lang="en" style="display: none;">
            <p>Before building a VAR model, we need to determine the <span class="highlight">integration order</span> of each time series. If a series is non-stationary, traditional statistical tests will produce spurious results (spurious regression).</p>

            <div class="formula-block">
                <div class="formula-label">Augmented Dickey-Fuller (ADF) Test</div>
                $$\Delta Y_t = \alpha + \beta t + \gamma Y_{t-1} + \sum_{i=1}^{p} \delta_i \Delta Y_{t-i} + \varepsilon_t$$
            </div>

            <p><span class="highlight">ADF</span>: Tests the null hypothesis $H_0$: $\gamma = 0$ (unit root → non-stationary). Rejecting $H_0$ → series is stationary. Lag order $p$ is automatically selected using Schwert's criterion.</p>

            <div class="hypothesis-box">
                <div class="hyp hyp-h0"><strong>H₀ (ADF):</strong> Series has a unit root → non-stationary</div>
                <div class="hyp hyp-h1"><strong>H₁ (ADF):</strong> Series is stationary</div>
            </div>

            <p><span class="highlight-orange">KPSS</span>: Tests the opposite direction — $H_0$: series is stationary. Combining ADF + KPSS avoids Type I/II errors. When the two tests contradict, the pipeline automatically runs <span class="highlight">Zivot-Andrews (1992)</span> — allowing 1 endogenous structural break — as a tiebreaker.</p>
        </div>
    </div>
</div>

<div id="stationarity-root">
    <div id="stationarity-loading">
        <div class="rounded-xl p-6 animate-pulse" style="background-color: var(--color-bg-card);">
            <div class="h-4 w-48 rounded mb-4" style="background-color: var(--color-border);"></div>
            <div class="space-y-3">
                @for ($i = 0; $i < 3; $i++)
                <div class="h-10 rounded" style="background-color: var(--color-bg-input);"></div>
                @endfor
            </div>
        </div>
    </div>
    <div id="stationarity-error" class="hidden"></div>
    <div id="stationarity-content" class="hidden space-y-6">
        <div class="rounded-xl border overflow-hidden" style="background-color: var(--color-bg-card); border-color: var(--color-border);">
            <div class="overflow-x-auto">
                <table class="w-full text-sm" id="station-table">
                    <thead>
                        <tr style="background-color: var(--color-bg-input);">
                            <th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider" style="color: var(--color-text-muted);" data-i18n="p1.col.variable">Variable</th>
                            <th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider" style="color: var(--color-text-muted);" data-i18n="p1.col.level">Level</th>
                            <th class="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider" style="color: var(--color-text-muted);" data-i18n="p1.col.adf_stat">ADF Stat</th>
                            <th class="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider" style="color: var(--color-text-muted);" data-i18n="p1.col.adf_pval">ADF p-val</th>
                            <th class="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider" style="color: var(--color-text-muted);" data-i18n="p1.col.adf">ADF</th>
                            <th class="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider" style="color: var(--color-text-muted);" data-i18n="p1.col.kpss_stat">KPSS Stat</th>
                            <th class="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider" style="color: var(--color-text-muted);" data-i18n="p1.col.kpss">KPSS</th>
                            <th class="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider" style="color: var(--color-text-muted);" data-i18n="p1.col.verdict">Verdict</th>
                        </tr>
                    </thead>
                    <tbody id="station-tbody"></tbody>
                </table>
            </div>
        </div>
        <div id="station-legend" class="rounded-xl p-5 border" style="background-color: var(--color-bg-card); border-color: var(--color-border);"></div>
        <div id="p1-notation-legend" class="mt-6"></div>
    </div>
</div>

</div>
@endsection

@push('scripts')
<script type="module">
    let cachedData = null;

    async function load() {
        try {
            const data = await window.dashboardFetch('stationarity');
            cachedData = data;
            document.getElementById('stationarity-loading').classList.add('hidden');
            document.getElementById('stationarity-content').classList.remove('hidden');
            renderTable(data);
            updatePageTitles();
            window.renderNotationLegend('p1-notation-legend', { statistics: ['adf', 'kpss', 'p-value'], significance: true });
        } catch (err) {
            document.getElementById('stationarity-loading').classList.add('hidden');
            document.getElementById('stationarity-error').classList.remove('hidden');
            window.showError('stationarity-error', err.message);
        }
    }

    function updatePageTitles() {
        const titleEl = document.getElementById('page-title');
        const subtitleEl = document.getElementById('page-subtitle');
        if (titleEl) titleEl.textContent = window.t('p1.title');
        if (subtitleEl) subtitleEl.textContent = window.t('p1.subtitle');
    }

    function verdictBadge(verdict) {
        const map = {
            stationary:    { bg: 'rgba(34,197,94,0.15)',  text: 'var(--color-kpi-positive)', key: 'common.stationary' },
            non_stationary:{ bg: 'rgba(239,68,68,0.15)',  text: 'var(--color-accent-red)',   key: 'common.non_stationary' },
            contradictory: { bg: 'rgba(249,115,22,0.15)', text: 'var(--color-accent-orange)',key: 'common.contradictory' },
        };
        const s = map[verdict] ?? map.contradictory;
        const label = window.t(s.key);
        return `<span class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium"
                      style="background-color: ${s.bg}; color: ${s.text};">${label}</span>`;
    }

    function pBadge(isReject) {
        if (isReject) return `<span style="color: var(--color-kpi-positive);">${window.t('common.reject')}</span>`;
        return `<span style="color: var(--color-text-muted);">${window.t('common.fail_to_reject')}</span>`;
    }

    function renderTable(data) {
        const rows = data.table ?? [];
        const tbody = document.getElementById('station-tbody');
        tbody.innerHTML = rows.map(r => {
            const levelLabel = r.integration_order != null ? `I(${r.integration_order})` : 'Level';

            return `
            <tr class="border-t" style="border-color: var(--color-border);">
                <td class="px-4 py-3 font-medium" style="color: var(--color-text-primary);">${r.variable}</td>
                <td class="px-4 py-3 text-xs" style="color: var(--color-text-secondary);">${levelLabel}</td>
                <td class="px-4 py-3 text-right tabular-nums" style="color: var(--color-text-primary);">${r.adf_statistic?.toFixed(3) ?? '—'}</td>
                <td class="px-4 py-3 text-right tabular-nums" style="color: var(--color-text-primary);">${r.adf_p_value?.toFixed(4) ?? '—'}</td>
                <td class="px-4 py-3 text-center">${pBadge(r.adf_reject)}</td>
                <td class="px-4 py-3 text-right tabular-nums" style="color: var(--color-text-primary);">${r.kpss_statistic?.toFixed(3) ?? '—'}</td>
                <td class="px-4 py-3 text-center">${pBadge(r.kpss_reject)}</td>
                <td class="px-4 py-3 text-center">${verdictBadge(r.conclusion)}</td>
            </tr>
            `;
        }).join('');

        const meta = data.metadata ?? {};
        document.getElementById('station-legend').innerHTML = `
            <p class="text-xs" style="color: var(--color-text-muted);">
                ${window.t('p1.sig_level')}: ${meta.significance_level ?? 0.05} &middot;
                ${window.t('p1.adf_maxlag')}: ${meta.schwert_maxlag ?? '—'} &middot;
                ${window.t('p1.observations')}: ${meta.n_observations ?? '—'}
            </p>
        `;
    }

    window.onLangChange(() => {
        if (cachedData) {
            renderTable(cachedData);
        }
        updatePageTitles();
        window.renderNotationLegend('p1-notation-legend', { statistics: ['adf', 'kpss', 'p-value'], significance: true });
    });

    load();
</script>
@endpush
