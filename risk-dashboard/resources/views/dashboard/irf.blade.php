@extends('layouts.dashboard')

@section('title', 'IRF')
@section('page-title', 'Phase 5 — Impulse Response Functions')
@section('page-subtitle', 'Orthogonalized impulse response with 95% confidence bands')

@section('export-buttons')
<button class="btn-export" data-export="irf-export" onclick="exportSectionPDF('irf-export', 'phase5_irf.pdf')">
    <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
    Export PDF
</button>
@endsection

@section('content')
<div id="irf-export">

{{-- Explainer --}}
<div class="explainer-card mb-6">
    <div class="explainer-header" onclick="toggleExplainer('explain-irf')">
        <div class="explainer-header-left">
            <div class="explainer-icon">
                <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            </div>
            <div>
                <div class="explainer-title">Hàm phản ứng xung (Impulse Response Function)</div>
                <div class="explainer-subtitle">Khi một biến bị "sốc", các biến khác phản ứng thế nào theo thời gian?</div>
            </div>
        </div>
        <svg id="explain-irf-icon" class="explainer-chevron" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
    </div>
    <div id="explain-irf" class="explainer-body hidden math-content">
        <p>
            IRF theo dõi tác động của <span class="highlight">một cú sốc 1 độ lệch chuẩn</span> vào biến $j$
            lên biến $i$ qua $h$ kỳ (horizons). Sử dụng phân rã Cholesky để trực giao hóa các sốc.
        </p>

        <div class="formula-block">
            <div class="formula-label">Biểu diễn VMA(∞) — Moving Average</div>
            $$\mathbf{Y}_t = \boldsymbol{\mu} + \sum_{s=0}^{\infty} \boldsymbol{\Psi}_s \mathbf{u}_{t-s}, \quad \boldsymbol{\Psi}_0 = \mathbf{I}_k$$
        </div>

        <p>
            Phần tử $\Psi_s(i,j)$ chính là phản ứng của biến $i$ sau $s$ kỳ trước cú sốc vào biến $j$.
        </p>
        <p>
            <span class="highlight-orange">Đọc biểu đồ:</span> Đường về 0 nhanh → tác động tạm thời.
            Đường duy trì khác 0 → tác động kéo dài. Đường âm → phản ứng ngược chiều.
            Vùng nằm trong đường zero (nét đứt) cho thấy tác động không có ý nghĩa thống kê.
        </p>
    </div>
</div>

<div id="irf-root">
    <div id="irf-loading">
        <div class="rounded-xl p-6 animate-pulse" style="background-color: var(--color-bg-card);">
            <div class="h-4 w-40 rounded mb-4" style="background-color: var(--color-border);"></div>
            <div class="h-48 rounded" style="background-color: var(--color-bg-input);"></div>
        </div>
    </div>
    <div id="irf-error" class="hidden"></div>
    <div id="irf-content" class="hidden space-y-6">
        <div id="irf-meta" class="grid grid-cols-2 sm:grid-cols-4 gap-3"></div>
        <div id="irf-charts" class="space-y-6"></div>
    </div>
</div>

</div>
@endsection

@push('scripts')
<script type="module">
    const VS = window.VARIABLE_STYLES;
    const SHOCK_COLORS = ['#3b82f6', '#f97316', '#22c55e', '#a855f7', '#06b6d4'];

    async function load() {
        try {
            const data = await window.dashboardFetch('irf');
            document.getElementById('irf-loading').classList.add('hidden');
            document.getElementById('irf-content').classList.remove('hidden');
            renderMeta(data);
            renderCharts(data);
        } catch (err) {
            document.getElementById('irf-loading').classList.add('hidden');
            document.getElementById('irf-error').classList.remove('hidden');
            window.showError('irf-error', err.message);
        }
    }

    function renderMeta(data) {
        const m = data.metadata;
        const items = [
            ['IRF Periods', m.irf_periods ?? '—'],
            ['Orthogonalization', m.orthogonalization ?? '—'],
            ['CI Method', m.ci_method ?? '—'],
            ['Ordering', (m.cholesky_ordering ?? []).join(' → ')],
        ];
        document.getElementById('irf-meta').innerHTML = items.map(([l, v]) => `
            <div class="rounded-lg px-4 py-3 border" style="background-color: var(--color-bg-card); border-color: var(--color-border);">
                <p class="text-[10px] font-semibold uppercase tracking-wider" style="color: var(--color-text-muted);">${l}</p>
                <p class="mt-1 text-sm font-medium truncate" style="color: var(--color-text-primary);">${v}</p>
            </div>
        `).join('');
    }

    function renderCharts(data) {
        const container = document.getElementById('irf-charts');
        const byResponse = data.by_response ?? {};

        for (const [respVar, shocks] of Object.entries(byResponse)) {
            const style = VS[respVar] ?? { color: '#94a3b8', label: respVar };
            const wrapper = document.createElement('div');
            wrapper.className = 'rounded-xl p-6 border';
            wrapper.style.backgroundColor = 'var(--color-bg-card)';
            wrapper.style.borderColor = 'var(--color-border)';

            const canvasId = `irf-chart-${respVar}`;
            wrapper.innerHTML = `
                <h3 class="text-sm font-semibold mb-4" style="color: var(--color-text-primary);">
                    Response: ${style.label}
                </h3>
                <div class="chart-container" style="height: 280px;">
                    <canvas id="${canvasId}"></canvas>
                </div>
            `;
            container.appendChild(wrapper);

            const datasets = [];
            shocks.forEach((s, idx) => {
                const color = SHOCK_COLORS[idx % SHOCK_COLORS.length];
                const shockStyle = VS[s.shock] ?? { color, label: s.shock };
                datasets.push({
                    label: `${shockStyle.label} shock`,
                    data: s.data.irf_values,
                    borderColor: shockStyle.color,
                    backgroundColor: shockStyle.color,
                    borderWidth: 2,
                    pointRadius: 2,
                    fill: false,
                });
            });

            new window.Chart(document.getElementById(canvasId), {
                type: 'line',
                data: {
                    labels: shocks[0]?.data.horizons ?? [],
                    datasets,
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    plugins: {
                        legend: { position: 'top', labels: { padding: 16, font: { size: 11 } } },
                        annotation: {
                            annotations: {
                                zeroLine: { type: 'line', yMin: 0, yMax: 0, borderColor: 'rgba(148,163,184,0.4)', borderWidth: 1, borderDash: [4, 4] },
                            },
                        },
                    },
                    scales: {
                        x: { title: { display: true, text: 'Horizon', color: '#64748b', font: { size: 11 } }, grid: { color: 'rgba(51,65,85,0.5)' } },
                        y: { title: { display: true, text: 'Response', color: '#64748b', font: { size: 11 } }, grid: { color: 'rgba(51,65,85,0.5)' } },
                    },
                },
            });
        }
    }

    load();
</script>
@endpush
