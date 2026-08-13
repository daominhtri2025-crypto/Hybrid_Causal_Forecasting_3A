@extends('layouts.dashboard')

@section('title', 'Forecast')
@section('page-title', 'Phase 4 — VAR Forecast')
@section('page-subtitle', '4-week ahead forecast with 95% confidence intervals')

@section('export-buttons')
<button class="btn-export" data-export="forecast-export" onclick="exportSectionPDF('forecast-export', 'phase4_forecast.pdf')">
    <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
    Export PDF
</button>
@endsection

@section('content')
<div id="forecast-export">

{{-- Explainer --}}
<div class="explainer-card mb-6">
    <div class="explainer-header" onclick="toggleExplainer('explain-forecast')">
        <div class="explainer-header-left">
            <div class="explainer-icon">
                <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            </div>
            <div>
                <div class="explainer-title">Dự báo VAR (Vector Autoregression)</div>
                <div class="explainer-subtitle">Mô hình dự báo đa biến — mỗi biến phụ thuộc vào quá khứ của tất cả biến</div>
            </div>
        </div>
        <svg id="explain-forecast-icon" class="explainer-chevron" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
    </div>
    <div id="explain-forecast" class="explainer-body hidden math-content">
        <p>
            Mô hình <span class="highlight">VAR(p)</span> mô tả hệ thống $k$ biến, trong đó mỗi biến là hàm tuyến tính
            của $p$ giá trị trễ của <em>tất cả</em> biến trong hệ thống.
        </p>

        <div class="formula-block">
            <div class="formula-label">VAR(p) — dạng ma trận</div>
            $$\mathbf{Y}_t = \mathbf{c} + \mathbf{A}_1 \mathbf{Y}_{t-1} + \mathbf{A}_2 \mathbf{Y}_{t-2} + \ldots + \mathbf{A}_p \mathbf{Y}_{t-p} + \mathbf{u}_t$$
        </div>

        <p>
            Trong đó $\mathbf{Y}_t$ là vector $k \times 1$ (3 biến: ProductionVolume, DelayRate, OrderDemand),
            $\mathbf{A}_i$ là ma trận hệ số $k \times k$, và $\mathbf{u}_t \sim N(\mathbf{0}, \Sigma)$.
        </p>
        <p>
            <span class="highlight-orange">Khoảng tin cậy 95%:</span> Các dải CI được tính bằng bootstrap,
            thể hiện mức độ bất định của dự báo — dải rộng hơn = bất định lớn hơn.
        </p>
    </div>
</div>

<div id="forecast-root">
    {{-- Loading --}}
    <div id="forecast-loading" class="space-y-6">
        <div class="rounded-xl p-6 animate-pulse" style="background-color: var(--color-bg-card);">
            <div class="h-4 w-40 rounded mb-6" style="background-color: var(--color-border);"></div>
            <div class="h-64 rounded" style="background-color: var(--color-bg-input);"></div>
        </div>
    </div>

    {{-- Error --}}
    <div id="forecast-error" class="hidden"></div>

    {{-- Content --}}
    <div id="forecast-content" class="hidden space-y-6">
        {{-- Model diagnostics strip --}}
        <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3" id="diag-strip"></div>

        {{-- Charts: one per variable --}}
        <div id="forecast-charts" class="space-y-6"></div>

        {{-- Warnings --}}
        <div id="forecast-warnings" class="hidden"></div>
    </div>
</div>

</div>
@endsection

@push('scripts')
<script type="module">
    const VS = window.VARIABLE_STYLES;
    const chartInstances = [];

    async function loadForecast() {
        try {
            const data = await window.dashboardFetch('forecast');
            document.getElementById('forecast-loading').classList.add('hidden');
            document.getElementById('forecast-content').classList.remove('hidden');
            renderDiagStrip(data);
            renderCharts(data.forecast);
            renderWarnings(data.warnings);
        } catch (err) {
            document.getElementById('forecast-loading').classList.add('hidden');
            document.getElementById('forecast-error').classList.remove('hidden');
            window.showError('forecast-error', err.message);
        }
    }

    function renderDiagStrip(data) {
        const d = data.diagnostics;
        const m = data.model;
        const items = [
            ['Route',       m.route?.replace(/_/g, ' ') ?? '—'],
            ['Lag Order',   m.lag_order ?? '—'],
            ['AIC',         d.aic != null ? Number(d.aic).toFixed(1) : '—'],
            ['BIC',         d.bic != null ? Number(d.bic).toFixed(1) : '—'],
            ['Log-L',       d.log_likelihood != null ? Number(d.log_likelihood).toFixed(1) : '—'],
            ['T_eff',       d.effective_obs ?? '—'],
        ];

        document.getElementById('diag-strip').innerHTML = items.map(([label, value]) => `
            <div class="rounded-lg px-4 py-3 border"
                 style="background-color: var(--color-bg-card); border-color: var(--color-border);">
                <p class="text-[10px] font-semibold uppercase tracking-wider" style="color: var(--color-text-muted);">${label}</p>
                <p class="mt-1 text-base font-bold tabular-nums" style="color: var(--color-text-primary);">${value}</p>
            </div>
        `).join('');
    }

    function renderCharts(forecast) {
        const container = document.getElementById('forecast-charts');
        const dates = forecast.dates;
        const variables = forecast.variables;

        container.innerHTML = '';

        for (const [varName, series] of Object.entries(variables)) {
            const style = VS[varName] || { color: '#94a3b8', faded: 'rgba(148,163,184,0.15)', label: varName };

            const wrapper = document.createElement('div');
            wrapper.className = 'rounded-xl p-6 border';
            wrapper.style.backgroundColor = 'var(--color-bg-card)';
            wrapper.style.borderColor = 'var(--color-border)';

            wrapper.innerHTML = `
                <div class="flex items-center justify-between mb-4">
                    <h3 class="text-sm font-semibold" style="color: var(--color-text-primary);">
                        <span class="inline-block h-2.5 w-2.5 rounded-full mr-2" style="background-color: ${style.color};"></span>
                        ${style.label}
                    </h3>
                    <span class="text-xs tabular-nums" style="color: var(--color-text-muted);">
                        ${series.length} periods &middot; 95% CI
                    </span>
                </div>
                <div class="chart-container" style="height: 280px;">
                    <canvas id="chart-${varName}"></canvas>
                </div>
            `;
            container.appendChild(wrapper);

            const labels = series.map(d => d.date);
            const points = series.map(d => d.point);
            const lowers = series.map(d => d.lower);
            const uppers = series.map(d => d.upper);

            const ctx = document.getElementById(`chart-${varName}`).getContext('2d');
            const chart = new window.Chart(ctx, {
                type: 'line',
                data: {
                    labels,
                    datasets: [
                        {
                            label: 'Upper 95%',
                            data: uppers,
                            borderColor: 'transparent',
                            backgroundColor: style.faded,
                            fill: '+1',
                            pointRadius: 0,
                            order: 2,
                        },
                        {
                            label: 'Lower 95%',
                            data: lowers,
                            borderColor: 'transparent',
                            backgroundColor: style.faded,
                            fill: false,
                            pointRadius: 0,
                            order: 2,
                        },
                        {
                            label: style.label,
                            data: points,
                            borderColor: style.color,
                            backgroundColor: style.color,
                            borderWidth: 2.5,
                            pointRadius: 4,
                            pointBackgroundColor: style.color,
                            pointBorderColor: 'var(--color-bg-card)',
                            pointBorderWidth: 2,
                            fill: false,
                            order: 1,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                title: (items) => `Week: ${items[0].label}`,
                                label: (ctx) => {
                                    const i = ctx.dataIndex;
                                    if (ctx.datasetIndex === 2) {
                                        const pt = points[i]?.toFixed(4) ?? '—';
                                        const lo = lowers[i]?.toFixed(4) ?? '—';
                                        const hi = uppers[i]?.toFixed(4) ?? '—';
                                        return [
                                            `Point: ${pt}`,
                                            `95% CI: [${lo}, ${hi}]`,
                                        ];
                                    }
                                    return null;
                                },
                            },
                            filter: (item) => item.datasetIndex === 2,
                        },
                    },
                    scales: {
                        x: {
                            grid: { color: 'rgba(51, 65, 85, 0.5)', drawTicks: false },
                            ticks: { padding: 8, font: { size: 11 } },
                        },
                        y: {
                            grid: { color: 'rgba(51, 65, 85, 0.5)', drawTicks: false },
                            ticks: {
                                padding: 8,
                                font: { size: 11 },
                                callback: (v) => Number(v).toFixed(2),
                            },
                        },
                    },
                },
            });
            chartInstances.push(chart);
        }
    }

    function renderWarnings(warnings) {
        if (!warnings || warnings.length === 0) return;
        const container = document.getElementById('forecast-warnings');
        container.classList.remove('hidden');
        container.innerHTML = `
            <div class="rounded-xl p-5 border" style="background-color: rgba(249, 115, 22, 0.08); border-color: rgba(249, 115, 22, 0.3);">
                <h3 class="text-xs font-semibold uppercase tracking-wider mb-2" style="color: var(--color-accent-orange);">
                    Warnings
                </h3>
                <ul class="space-y-1">
                    ${warnings.map(w => `<li class="text-sm" style="color: var(--color-text-secondary);">&bull; ${w}</li>`).join('')}
                </ul>
            </div>
        `;
    }

    loadForecast();
</script>
@endpush
