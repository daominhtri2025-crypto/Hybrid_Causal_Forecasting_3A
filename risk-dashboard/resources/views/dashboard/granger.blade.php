@extends('layouts.dashboard')

@section('title', 'Granger Causality')
@section('page-title', 'Phase 2 — Granger Causality')
@section('page-subtitle', 'Pairwise Granger causality test heatmap and results table')

@section('export-buttons')
<button class="btn-export" data-export="granger-export" onclick="exportSectionPDF('granger-export', 'phase2_granger_causality.pdf')">
    <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
    <span data-i18n="header.export_pdf">Export PDF</span>
</button>
@endsection

@section('content')
<div id="granger-export">

{{-- Explainer --}}
<div class="explainer-card mb-6">
    <div class="explainer-header" onclick="toggleExplainer('explain-granger')">
        <div class="explainer-header-left">
            <div class="explainer-icon">
                <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            </div>
            <div>
                <div class="explainer-title"><span data-lang="vi">Kiểm định nhân quả Granger</span><span data-lang="en" style="display: none;">Granger Causality Test</span></div>
                <div class="explainer-subtitle"><span data-lang="vi">X có giúp dự báo Y tốt hơn không? — Granger (1969)</span><span data-lang="en" style="display: none;">Does X help forecast Y? — Granger (1969)</span></div>
            </div>
        </div>
        <svg id="explain-granger-icon" class="explainer-chevron" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
    </div>
    <div id="explain-granger" class="explainer-body hidden math-content">
        <div data-lang="vi">
            <p>
                Kiểm định Granger đánh giá liệu <span class="highlight">giá trị quá khứ của biến X</span>
                có cung cấp thông tin dự báo bổ sung cho biến Y hay không, vượt trên thông tin từ chính quá khứ của Y.
            </p>

            <div class="formula-block">
                <div class="formula-label">Mô hình không ràng buộc (Unrestricted)</div>
                $$Y_t = \alpha + \sum_{i=1}^{p} \beta_i Y_{t-i} + \sum_{i=1}^{p} \gamma_i X_{t-i} + \varepsilon_t$$
            </div>

            <div class="hypothesis-box">
                <div class="hyp hyp-h0">
                    <strong>H₀:</strong> $\gamma_1 = \gamma_2 = \ldots = \gamma_p = 0$ — X không Granger-cause Y
                </div>
                <div class="hyp hyp-h1">
                    <strong>H₁:</strong> Ít nhất một $\gamma_i \neq 0$ — X có Granger-cause Y
                </div>
            </div>

            <p>
                Kiểm định sử dụng <span class="highlight">F-test</span> so sánh mô hình có và không có biến X.
                Với 3 biến trong hệ thống, ta kiểm tra tất cả 6 cặp theo từng chiều — tạo thành ma trận nhân quả heatmap bên dưới.
                Ngưỡng ý nghĩa: $\alpha = 0.05$.
            </p>
        </div>
        <div data-lang="en" style="display: none;">
            <p>The Granger test evaluates whether <span class="highlight">past values of variable X</span> provide additional forecasting information for variable Y, beyond what Y's own past provides.</p>

            <div class="formula-block">
                <div class="formula-label">Unrestricted Model</div>
                $$Y_t = \alpha + \sum_{i=1}^{p} \beta_i Y_{t-i} + \sum_{i=1}^{p} \gamma_i X_{t-i} + \varepsilon_t$$
            </div>

            <div class="hypothesis-box">
                <div class="hyp hyp-h0"><strong>H₀:</strong> $\gamma_1 = \gamma_2 = \ldots = \gamma_p = 0$ — X does not Granger-cause Y</div>
                <div class="hyp hyp-h1"><strong>H₁:</strong> At least one $\gamma_i \neq 0$ — X Granger-causes Y</div>
            </div>

            <p>The test uses an <span class="highlight">F-test</span> comparing models with and without variable X. With 3 variables in the system, all 6 directional pairs are tested — forming the causality heatmap below. Significance level: $\alpha = 0.05$.</p>
        </div>
    </div>
</div>

<div id="granger-root">
    <div id="granger-loading">
        <div class="rounded-xl p-6 animate-pulse" style="background-color: var(--color-bg-card);">
            <div class="h-4 w-40 rounded mb-4" style="background-color: var(--color-border);"></div>
            <div class="h-48 rounded" style="background-color: var(--color-bg-input);"></div>
        </div>
    </div>
    <div id="granger-error" class="hidden"></div>
    <div id="granger-content" class="hidden space-y-6">
        {{-- Summary strip --}}
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4" id="granger-summary"></div>

        {{-- Heatmap --}}
        <div class="rounded-xl p-6 border" style="background-color: var(--color-bg-card); border-color: var(--color-border);">
            <h3 class="text-xs font-semibold uppercase tracking-wider mb-4" style="color: var(--color-text-muted);" data-i18n="p2.heatmap_title">
                Causality Heatmap (p-values)
            </h3>
            <div id="heatmap-grid"></div>
        </div>

        {{-- Detail table --}}
        <div class="rounded-xl border overflow-hidden" style="background-color: var(--color-bg-card); border-color: var(--color-border);">
            <div class="overflow-x-auto">
                <table class="w-full text-sm">
                    <thead>
                        <tr style="background-color: var(--color-bg-input);">
                            <th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider" style="color: var(--color-text-muted);" data-i18n="p2.col.pair">Cause → Effect</th>
                            <th class="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider" style="color: var(--color-text-muted);" data-i18n="p2.col.fstat">F-stat</th>
                            <th class="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider" style="color: var(--color-text-muted);" data-i18n="p2.col.pvalue">p-value</th>
                            <th class="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider" style="color: var(--color-text-muted);" data-i18n="p2.col.significant">Significant</th>
                        </tr>
                    </thead>
                    <tbody id="granger-tbody"></tbody>
                </table>
            </div>
        </div>

        {{-- Notation legend --}}
        <div id="p2-notation-legend" class="mt-6"></div>
    </div>
</div>

</div>
@endsection

@push('scripts')
<script type="module">
    let cachedData = null;

    async function load() {
        try {
            const data = await window.dashboardFetch('granger');
            cachedData = data;
            document.getElementById('page-title').textContent = window.t('p2.title');
            document.getElementById('page-subtitle').textContent = window.t('p2.subtitle');
            document.getElementById('granger-loading').classList.add('hidden');
            document.getElementById('granger-content').classList.remove('hidden');
            renderSummary(data);
            renderHeatmap(data);
            renderTable(data);
            window.renderNotationLegend('p2-notation-legend', { statistics: ['f-stat', 'p-value', 'lag'], significance: true });
        } catch (err) {
            document.getElementById('granger-loading').classList.add('hidden');
            document.getElementById('granger-error').classList.remove('hidden');
            window.showError('granger-error', err.message);
        }
    }

    function renderSummary(data) {
        const items = [
            [window.t('p2.sig_pairs'), `${data.summary?.significant_count ?? '—'}/${data.summary?.total_pairs ?? '—'}`, 'var(--color-accent-blue)'],
            [window.t('p2.lag_order'), data.lag_selection?.selected_lag ?? '—', 'var(--color-accent-cyan)'],
            [window.t('p2.sig_level'), data.metadata?.significance_level ?? 0.05, 'var(--color-accent-purple)'],
        ];
        document.getElementById('granger-summary').innerHTML = items.map(([label, val, color]) => `
            <div class="rounded-lg px-4 py-3 border" style="background-color: var(--color-bg-card); border-color: var(--color-border);">
                <p class="text-[10px] font-semibold uppercase tracking-wider" style="color: var(--color-text-muted);">${label}</p>
                <p class="mt-1 text-lg font-bold tabular-nums" style="color: ${color};">${val}</p>
            </div>
        `).join('');
    }

    function renderHeatmap(data) {
        const heatmap = data.heatmap ?? {};
        const vars = heatmap.variables ?? [];
        const matrix = heatmap.matrix ?? {};
        if (vars.length === 0) return;

        const grid = document.getElementById('heatmap-grid');
        const size = vars.length;

        let html = '<div class="inline-grid gap-1" style="grid-template-columns: auto ' + 'minmax(60px, 1fr) '.repeat(size) + ';">';

        html += '<div></div>';
        vars.forEach(v => {
            html += `<div class="text-center text-[10px] font-medium px-2 py-1 truncate" style="color: var(--color-text-muted);">${v}</div>`;
        });

        vars.forEach(cause => {
            html += `<div class="text-right text-[10px] font-medium px-2 py-2 truncate" style="color: var(--color-text-muted);">${cause}</div>`;
            vars.forEach(effect => {
                const cell = matrix[cause]?.[effect];
                if (cause === effect) {
                    html += `<div class="rounded text-center py-2 text-[10px]" style="background-color: var(--color-bg-input); color: var(--color-text-muted);">—</div>`;
                } else if (cell != null) {
                    const pval = cell.p_value ?? 1;
                    const sig = cell.significant ?? false;
                    const bg = sig ? 'rgba(59, 130, 246, 0.3)' : 'rgba(51, 65, 85, 0.3)';
                    const textColor = sig ? 'var(--color-accent-blue)' : 'var(--color-text-muted)';
                    html += `<div class="rounded text-center py-2 text-xs tabular-nums font-medium cursor-default"
                                  style="background-color: ${bg}; color: ${textColor};"
                                  title="F=${(cell.f_statistic ?? 0).toFixed(2)}, p=${pval.toFixed(4)}">${pval.toFixed(3)}</div>`;
                } else {
                    html += `<div class="rounded text-center py-2 text-[10px]" style="background-color: var(--color-bg-input); color: var(--color-text-muted);">—</div>`;
                }
            });
        });

        html += '</div>';
        grid.innerHTML = html;
    }

    function renderTable(data) {
        const pairs = data.pairs ?? [];
        document.getElementById('granger-tbody').innerHTML = pairs.map(p => `
            <tr class="border-t" style="border-color: var(--color-border);">
                <td class="px-4 py-3 font-medium" style="color: var(--color-text-primary);">${p.cause} → ${p.effect}</td>
                <td class="px-4 py-3 text-right tabular-nums" style="color: var(--color-text-primary);">${p.f_statistic?.toFixed(3) ?? '—'}</td>
                <td class="px-4 py-3 text-right tabular-nums" style="color: ${p.significant ? 'var(--color-accent-blue)' : 'var(--color-text-primary)'};">${p.p_value?.toFixed(4) ?? '—'}</td>
                <td class="px-4 py-3 text-center">
                    ${p.significant
                        ? `<span class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium" style="background-color: rgba(59,130,246,0.15); color: var(--color-accent-blue);">${window.t('common.yes')}</span>`
                        : `<span class="text-xs" style="color: var(--color-text-muted);">${window.t('common.no')}</span>`}
                </td>
            </tr>
        `).join('');
    }

    window.onLangChange(() => {
        if (!cachedData) return;
        document.getElementById('page-title').textContent = window.t('p2.title');
        document.getElementById('page-subtitle').textContent = window.t('p2.subtitle');
        renderSummary(cachedData);
        renderTable(cachedData);
        window.renderNotationLegend('p2-notation-legend', { statistics: ['f-stat', 'p-value', 'lag'], significance: true });
    });

    load();
</script>
@endpush
