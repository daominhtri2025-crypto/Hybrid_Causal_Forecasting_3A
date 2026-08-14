@extends('layouts.dashboard')

@section('title', 'Summary')
@section('page-title', 'System Overview')
@section('page-subtitle', 'Model configuration, KPI metrics, and pipeline status')

@section('export-buttons')
<button class="btn-export btn-export-primary" data-export="summary-export" onclick="exportSectionPDF('summary-export', 'executive_report_full.pdf')">
    <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
    <span data-i18n="header.full_report">Full Report</span>
</button>
@endsection

@section('content')
<div id="summary-export">

{{-- Explainer --}}
<div class="explainer-card mb-6">
    <div class="explainer-header" onclick="toggleExplainer('explain-summary')">
        <div class="explainer-header-left">
            <div class="explainer-icon" style="background-color: rgba(34, 197, 94, 0.12); color: var(--color-accent-green);">
                <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            </div>
            <div>
                <div class="explainer-title">
                    <span data-lang="vi">Tổng quan Pipeline phân tích nhân quả</span>
                    <span data-lang="en" style="display: none;">Causal Analysis Pipeline Overview</span>
                </div>
                <div class="explainer-subtitle">
                    <span data-lang="vi">VAR(p) trên 3 biến vận hành — 5 Phase phân tích tuần tự</span>
                    <span data-lang="en" style="display: none;">VAR(p) on 3 operational variables — 5 sequential analysis Phases</span>
                </div>
            </div>
        </div>
        <svg id="explain-summary-icon" class="explainer-chevron" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
    </div>
    <div id="explain-summary" class="explainer-body hidden math-content">
        <div data-lang="vi">
            <p>
                Dashboard trực quan hóa kết quả từ pipeline <span class="highlight">Hybrid Causal Forecasting 3A</span>
                — phân tích mối quan hệ nhân quả giữa 3 biến vận hành sản xuất:
                <span class="highlight">ProductionVolume</span> (sản lượng),
                <span class="highlight-orange">DelayRate</span> (tỷ lệ trễ đơn hàng),
                và <span style="color: var(--color-accent-green); font-weight: 500;">OrderDemand</span> (nhu cầu đặt hàng).
            </p>
            <p>
                Pipeline gồm 5 Phase tuần tự: (1) Kiểm định tính dừng, (2) Nhân quả Granger,
                (3) Đồng tích hợp Johansen + cross-check Toda-Yamamoto, (4) Dự báo VAR,
                (5) IRF & FEVD. Mọi kết quả là <span class="highlight-orange">READ-ONLY</span> — dashboard chỉ đọc file JSON
                từ Python pipeline, không tính toán lại.
            </p>
        </div>
        <div data-lang="en" style="display: none;">
            <p>Dashboard visualizes results from the <span class="highlight">Hybrid Causal Forecasting 3A</span> pipeline — analyzing causal relationships among 3 operational variables: <span class="highlight">ProductionVolume</span> (production output), <span class="highlight-orange">DelayRate</span> (order delay rate), and <span style="color: var(--color-accent-green); font-weight: 500;">OrderDemand</span> (order demand).</p>
            <p>The pipeline consists of 5 sequential Phases: (1) Stationarity tests, (2) Granger causality, (3) Johansen cointegration + Toda-Yamamoto cross-check, (4) VAR forecast, (5) IRF & FEVD. All results are <span class="highlight-orange">READ-ONLY</span> — the dashboard only reads JSON files from the Python pipeline, no recalculation is performed.</p>
        </div>
    </div>
</div>

<div id="summary-root">
    {{-- Loading skeleton --}}
    <div id="summary-loading" class="space-y-6">
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            @for ($i = 0; $i < 4; $i++)
            <div class="rounded-xl p-5 animate-pulse" style="background-color: var(--color-bg-card);">
                <div class="h-3 w-20 rounded" style="background-color: var(--color-border);"></div>
                <div class="mt-3 h-7 w-24 rounded" style="background-color: var(--color-border);"></div>
            </div>
            @endfor
        </div>
    </div>

    {{-- Error state --}}
    <div id="summary-error" class="hidden"></div>

    {{-- Loaded content --}}
    <div id="summary-content" class="hidden space-y-6">
        {{-- KPI Cards --}}
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4" id="kpi-cards"></div>

        {{-- Phase Status + Model Info --}}
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {{-- Model Card --}}
            <div class="rounded-xl p-5 border" style="background-color: var(--color-bg-card); border-color: var(--color-border);">
                <h3 class="text-xs font-semibold uppercase tracking-wider mb-4" style="color: var(--color-text-muted);" data-i18n="summary.model_config">
                    Model Configuration
                </h3>
                <dl id="model-info" class="space-y-3"></dl>
            </div>

            {{-- Phase Status --}}
            <div class="lg:col-span-2 rounded-xl p-5 border" style="background-color: var(--color-bg-card); border-color: var(--color-border);">
                <h3 class="text-xs font-semibold uppercase tracking-wider mb-4" style="color: var(--color-text-muted);" data-i18n="summary.phase_status">
                    Pipeline Phase Status
                </h3>
                <div id="phase-status" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3"></div>
            </div>
        </div>

        {{-- Notation Legend --}}
        <div id="summary-notation-legend" class="mt-6"></div>
    </div>
</div>

</div>
@endsection

@push('scripts')
<script type="module">
    let cachedData = null;

    const PHASE_I18N = {
        phase1_stationarity:   'phase.p1',
        phase2_granger:        'phase.p2',
        phase3_cointegration:  'phase.p3',
        phase3b_toda_yamamoto: 'phase.p3b',
        phase4_forecast:       'phase.p4',
        phase5_irf_fevd:       'phase.p5',
    };

    async function loadSummary() {
        try {
            const data = await window.dashboardFetch('summary');
            cachedData = data;

            document.getElementById('page-title').textContent = window.t('summary.title');
            document.getElementById('page-subtitle').textContent = window.t('summary.subtitle');

            document.getElementById('summary-loading').classList.add('hidden');
            document.getElementById('summary-content').classList.remove('hidden');
            renderKPIs(data);
            renderModelInfo(data);
            renderPhaseStatus(data.phases_status);
            window.renderNotationLegend('summary-notation-legend', { statistics: ['p-value', 'lag'], significance: true });
        } catch (err) {
            document.getElementById('summary-loading').classList.add('hidden');
            document.getElementById('summary-error').classList.remove('hidden');
            window.showError('summary-error', err.message);
        }
    }

    function renderKPIs(data) {
        const kpis = [
            {
                label: window.t('summary.kpi.route'),
                value: data.model_route?.replace(/_/g, ' ') ?? '—',
                sub: `${window.t('summary.kpi.lag_sub')} = ${data.lag_order ?? '?'}`,
                color: 'var(--color-accent-blue)',
            },
            {
                label: window.t('summary.kpi.obs'),
                value: data.n_observations ?? '—',
                sub: window.t('summary.kpi.eff_t'),
                color: 'var(--color-accent-cyan)',
            },
            {
                label: window.t('summary.kpi.granger'),
                value: data.granger_significant_count !== null
                    ? `${data.granger_significant_count}/${data.granger_total_pairs}`
                    : '—',
                sub: window.t('summary.kpi.causal'),
                color: 'var(--color-accent-purple)',
            },
            {
                label: window.t('summary.kpi.dr_self'),
                value: data.null_finding_dr_self_pct !== null
                    ? `${data.null_finding_dr_self_pct}%`
                    : '—',
                sub: window.t('summary.kpi.fevd_nf'),
                color: 'var(--color-accent-orange)',
            },
        ];

        const container = document.getElementById('kpi-cards');
        container.innerHTML = kpis.map(kpi => `
            <div class="rounded-xl p-5 border transition-colors"
                 style="background-color: var(--color-bg-card); border-color: var(--color-border);">
                <p class="text-xs font-medium uppercase tracking-wider" style="color: var(--color-text-muted);">
                    ${kpi.label}
                </p>
                <p class="mt-2 text-2xl font-bold tabular-nums" style="color: ${kpi.color};">
                    ${kpi.value}
                </p>
                <p class="mt-1 text-xs" style="color: var(--color-text-secondary);">
                    ${kpi.sub}
                </p>
            </div>
        `).join('');
    }

    function renderModelInfo(data) {
        const items = [
            [window.t('summary.lbl.route'), data.model_route ?? '—'],
            [window.t('summary.lbl.lag'),   data.lag_order ?? '—'],
            [window.t('summary.lbl.vars'),  (data.variables ?? []).join(', ') || '—'],
            ['AIC',                          data.aic != null ? Number(data.aic).toFixed(2) : '—'],
            ['BIC',                          data.bic != null ? Number(data.bic).toFixed(2) : '—'],
        ];

        document.getElementById('model-info').innerHTML = items.map(([k, v]) => `
            <div class="flex items-center justify-between">
                <dt class="text-xs" style="color: var(--color-text-muted);">${k}</dt>
                <dd class="text-sm font-medium tabular-nums" style="color: var(--color-text-primary);">${v}</dd>
            </div>
        `).join('');
    }

    function renderPhaseStatus(phases) {
        const container = document.getElementById('phase-status');
        container.innerHTML = Object.entries(phases).map(([key, phase]) => {
            const isReady = phase.status === 'ready';
            const isError = phase.status === 'error';
            const dotColor = isReady ? 'var(--color-kpi-positive)'
                : isError ? 'var(--color-accent-red)'
                : 'var(--color-text-muted)';

            return `
                <div class="flex items-center gap-3 rounded-lg px-3 py-2.5 border"
                     style="background-color: var(--color-bg-input); border-color: var(--color-border);">
                    <span class="h-2 w-2 rounded-full shrink-0" style="background-color: ${dotColor};"></span>
                    <div class="min-w-0">
                        <p class="text-sm font-medium truncate" style="color: var(--color-text-primary);">
                            ${window.t(PHASE_I18N[key]) ?? key}
                        </p>
                        <p class="text-[11px] truncate" style="color: var(--color-text-muted);">
                            ${isReady ? (phase.timestamp ?? 'ready') : phase.status}
                        </p>
                    </div>
                </div>
            `;
        }).join('');
    }

    window.onLangChange(() => {
        if (!cachedData) return;
        document.getElementById('page-title').textContent = window.t('summary.title');
        document.getElementById('page-subtitle').textContent = window.t('summary.subtitle');
        renderKPIs(cachedData);
        renderModelInfo(cachedData);
        renderPhaseStatus(cachedData.phases_status);
        window.renderNotationLegend('summary-notation-legend', { statistics: ['p-value', 'lag'], significance: true });
    });

    loadSummary();
</script>
@endpush
