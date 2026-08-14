@extends('layouts.dashboard')

@section('title', 'FEVD')
@section('page-title', 'Phase 5 — Forecast Error Variance Decomposition')
@section('page-subtitle', 'Stacked variance decomposition with Null Finding highlight')

@section('export-buttons')
<button class="btn-export" data-export="fevd-export" onclick="exportSectionPDF('fevd-export', 'phase5_fevd.pdf')">
    <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
    <span data-i18n="header.export_pdf">Export PDF</span>
</button>
@endsection

@section('content')
<div id="fevd-export">

{{-- Explainer --}}
<div class="explainer-card mb-6">
    <div class="explainer-header" onclick="toggleExplainer('explain-fevd')">
        <div class="explainer-header-left">
            <div class="explainer-icon">
                <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            </div>
            <div>
                <div class="explainer-title">
                    <span data-lang="vi">Phân rã phương sai sai số dự báo (FEVD)</span>
                    <span data-lang="en" style="display: none;">Forecast Error Variance Decomposition (FEVD)</span>
                </div>
                <div class="explainer-subtitle">
                    <span data-lang="vi">Mỗi biến đóng góp bao nhiêu % vào biến động của biến mục tiêu?</span>
                    <span data-lang="en" style="display: none;">How much does each variable contribute to the target's variance?</span>
                </div>
            </div>
        </div>
        <svg id="explain-fevd-icon" class="explainer-chevron" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
    </div>
    <div id="explain-fevd" class="explainer-body hidden math-content">
        <div data-lang="vi">
            <p>
                FEVD đo lường <span class="highlight">tỷ trọng phương sai</span> sai số dự báo $h$-bước-trước
                của biến $i$ được giải thích bởi các cú sốc từ biến $j$. Tổng tất cả nguồn = 100% tại mỗi horizon.
            </p>

            <div class="formula-block">
                <div class="formula-label">FEVD tại horizon h</div>
                $$\theta_{ij}(h) = \frac{\sum_{s=0}^{h-1} (\mathbf{e}_i' \boldsymbol{\Psi}_s \mathbf{e}_j)^2}{\sum_{s=0}^{h-1} \mathbf{e}_i' \boldsymbol{\Psi}_s \boldsymbol{\Sigma} \boldsymbol{\Psi}_s' \mathbf{e}_i} \times 100\%$$
            </div>

            <p>
                Trong đó $\mathbf{e}_i$ là vector chọn, $\boldsymbol{\Psi}_s$ là ma trận IRF tại lag $s$,
                và $\boldsymbol{\Sigma}$ là ma trận hiệp phương sai nhiễu.
            </p>
            <p>
                <span class="highlight-orange">Null Finding:</span> Khi phần "self" (tự giải thích) chiếm tỷ lệ rất cao (ví dụ > 90%),
                các biến khác gần như không ảnh hưởng — đây là phát hiện khoa học hợp lệ (null finding), không phải lỗi mô hình.
            </p>
        </div>
        <div data-lang="en" style="display: none;">
            <p>FEVD measures the <span class="highlight">proportion of variance</span> in the $h$-step-ahead forecast error of variable $i$ that is explained by shocks from variable $j$. All sources sum to 100% at each horizon.</p>

            <div class="formula-block">
                <div class="formula-label">FEVD at horizon h</div>
                $$\theta_{ij}(h) = \frac{\sum_{s=0}^{h-1} (\mathbf{e}_i' \boldsymbol{\Psi}_s \mathbf{e}_j)^2}{\sum_{s=0}^{h-1} \mathbf{e}_i' \boldsymbol{\Psi}_s \boldsymbol{\Sigma} \boldsymbol{\Psi}_s' \mathbf{e}_i} \times 100\%$$
            </div>

            <p>Where $\mathbf{e}_i$ is a selection vector, $\boldsymbol{\Psi}_s$ is the IRF matrix at lag $s$, and $\boldsymbol{\Sigma}$ is the error covariance matrix.</p>
            <p><span class="highlight-orange">Null Finding:</span> When the "self" (own variance) share is very high (e.g. > 90%), other variables have almost no influence — this is a valid scientific finding (null finding), not a model error.</p>
        </div>
    </div>
</div>

<div id="fevd-root">
    <div id="fevd-loading">
        <div class="rounded-xl p-6 animate-pulse" style="background-color: var(--color-bg-card);">
            <div class="h-4 w-40 rounded mb-4" style="background-color: var(--color-border);"></div>
            <div class="h-48 rounded" style="background-color: var(--color-bg-input);"></div>
        </div>
    </div>
    <div id="fevd-error" class="hidden"></div>
    <div id="fevd-content" class="hidden space-y-6">
        {{-- Null Finding highlight --}}
        <div id="null-finding" class="hidden rounded-xl p-6 border"
             style="background-color: rgba(249,115,22,0.06); border-color: rgba(249,115,22,0.25);"></div>
        {{-- Charts --}}
        <div id="fevd-charts" class="space-y-6"></div>
        <div id="p5fevd-notation-legend" class="mt-6"></div>
    </div>
</div>

</div>
@endsection

@push('scripts')
<script type="module">
    const VS = window.VARIABLE_STYLES;
    const STACK_COLORS = ['#3b82f6', '#f97316', '#22c55e', '#a855f7', '#06b6d4', '#ef4444'];
    let cachedData = null;

    async function load() {
        try {
            const data = await window.dashboardFetch('fevd');
            cachedData = data;
            document.getElementById('fevd-loading').classList.add('hidden');
            document.getElementById('fevd-content').classList.remove('hidden');
            document.getElementById('page-title').textContent = window.t('p5fevd.title');
            document.getElementById('page-subtitle').textContent = window.t('p5fevd.subtitle');
            renderNullFinding(data.null_finding);
            renderCharts(data.variables);
            window.renderNotationLegend('p5fevd-notation-legend', { statistics: ['ci'], significance: false });
        } catch (err) {
            document.getElementById('fevd-loading').classList.add('hidden');
            document.getElementById('fevd-error').classList.remove('hidden');
            window.showError('fevd-error', err.message);
        }
    }

    function renderNullFinding(nf) {
        if (!nf) return;
        const el = document.getElementById('null-finding');
        el.classList.remove('hidden');
        el.innerHTML = `
            <div class="flex items-start gap-4">
                <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg"
                     style="background-color: rgba(249,115,22,0.2);">
                    <svg class="h-5 w-5" style="color: var(--color-accent-orange);" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                    </svg>
                </div>
                <div>
                    <h3 class="text-sm font-semibold" style="color: var(--color-accent-orange);">${window.t('common.null_finding')}</h3>
                    <p class="mt-1 text-sm" style="color: var(--color-text-secondary);">${nf.interpretation}</p>
                    <div class="mt-3 flex flex-wrap gap-4 text-xs tabular-nums" style="color: var(--color-text-muted);">
                        <span>h=1: ${nf.self_pct_h1?.toFixed(1) ?? '—'}%</span>
                        <span>h=4: ${nf.self_pct_h4?.toFixed(1) ?? '—'}%</span>
                        <span>h=8: ${nf.self_pct_h8?.toFixed(1) ?? '—'}%</span>
                        <span>h=12: ${nf.self_pct_h12?.toFixed(1) ?? '—'}%</span>
                    </div>
                </div>
            </div>
        `;
    }

    function renderCharts(variables) {
        const container = document.getElementById('fevd-charts');
        if (!variables) return;

        for (const [targetVar, vData] of Object.entries(variables)) {
            const style = VS[targetVar] ?? { color: '#94a3b8', label: targetVar };
            const wrapper = document.createElement('div');
            wrapper.className = 'rounded-xl p-6 border';
            wrapper.style.backgroundColor = 'var(--color-bg-card)';
            wrapper.style.borderColor = 'var(--color-border)';

            const canvasId = `fevd-chart-${targetVar}`;
            wrapper.innerHTML = `
                <div class="flex items-center justify-between mb-4">
                    <h3 class="text-sm font-semibold" style="color: var(--color-text-primary);">
                        ${window.t('p5fevd.target')}: ${style.label}
                    </h3>
                    <span class="text-xs tabular-nums" style="color: var(--color-text-muted);">
                        ${window.t('p5fevd.self_final').replace('{pct}', vData.self_pct_final?.toFixed(1) ?? '—')}
                    </span>
                </div>
                <div class="chart-container" style="height: 260px;">
                    <canvas id="${canvasId}"></canvas>
                </div>
            `;
            container.appendChild(wrapper);

            const sources = vData.sources ?? {};
            const horizons = vData.horizons ?? [];
            const sourceNames = Object.keys(sources);
            const datasets = sourceNames.map((src, idx) => {
                const srcStyle = VS[src] ?? { color: STACK_COLORS[idx % STACK_COLORS.length] };
                return {
                    label: VS[src]?.label ?? src,
                    data: sources[src],
                    backgroundColor: srcStyle.color + 'CC',
                    borderColor: srcStyle.color,
                    borderWidth: 1,
                    fill: true,
                };
            });

            new window.Chart(document.getElementById(canvasId), {
                type: 'line',
                data: { labels: horizons, datasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    plugins: {
                        legend: { position: 'top', labels: { padding: 16, font: { size: 11 } } },
                        tooltip: {
                            callbacks: {
                                label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y?.toFixed(1)}%`,
                            },
                        },
                    },
                    scales: {
                        x: { title: { display: true, text: window.t('p5fevd.axis.horizon'), color: '#64748b', font: { size: 11 } }, grid: { color: 'rgba(51,65,85,0.5)' } },
                        y: {
                            stacked: true,
                            min: 0, max: 100,
                            title: { display: true, text: window.t('p5fevd.axis.variance'), color: '#64748b', font: { size: 11 } },
                            grid: { color: 'rgba(51,65,85,0.5)' },
                            ticks: { callback: (v) => v + '%' },
                        },
                    },
                },
            });
        }
    }

    window.onLangChange(() => {
        if (!cachedData) return;
        document.getElementById('page-title').textContent = window.t('p5fevd.title');
        document.getElementById('page-subtitle').textContent = window.t('p5fevd.subtitle');
        renderNullFinding(cachedData.null_finding);
        window.renderNotationLegend('p5fevd-notation-legend', { statistics: ['ci'], significance: false });
    });

    load();
</script>
@endpush
