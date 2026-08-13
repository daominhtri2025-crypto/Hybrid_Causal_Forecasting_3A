@extends('layouts.dashboard')

@section('title', 'Toda-Yamamoto')
@section('page-title', 'Phase 3b — Toda-Yamamoto Cross-Check')
@section('page-subtitle', 'Granger vs Toda-Yamamoto agreement analysis')

@section('export-buttons')
<button class="btn-export" data-export="ty-export" onclick="exportSectionPDF('ty-export', 'phase3b_toda_yamamoto.pdf')">
    <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
    Export PDF
</button>
@endsection

@section('content')
<div id="ty-export">

{{-- Explainer --}}
<div class="explainer-card mb-6">
    <div class="explainer-header" onclick="toggleExplainer('explain-ty')">
        <div class="explainer-header-left">
            <div class="explainer-icon">
                <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            </div>
            <div>
                <div class="explainer-title">Kiểm định Toda-Yamamoto (Cross-check)</div>
                <div class="explainer-subtitle">Kiểm tra nhân quả không cần biến dừng — Toda & Yamamoto (1995)</div>
            </div>
        </div>
        <svg id="explain-ty-icon" class="explainer-chevron" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
    </div>
    <div id="explain-ty" class="explainer-body hidden math-content">
        <p>
            Khác với Granger truyền thống (yêu cầu chuỗi dừng), phương pháp <span class="highlight">Toda-Yamamoto</span>
            ước lượng VAR bậc $p + d_{max}$ rồi chỉ kiểm định $p$ hệ số đầu, bỏ qua $d_{max}$ hệ số thêm.
            Điều này đảm bảo kiểm định Wald có phân phối $\chi^2$ đúng, bất kể chuỗi dừng hay không.
        </p>

        <div class="formula-block">
            <div class="formula-label">VAR mở rộng Toda-Yamamoto</div>
            $$Y_t = \alpha + \sum_{i=1}^{p} \Phi_i Y_{t-i} + \sum_{j=p+1}^{p+d_{max}} \Phi_j Y_{t-j} + \varepsilon_t$$
        </div>

        <div class="hypothesis-box">
            <div class="hyp hyp-h0">
                <strong>H₀:</strong> $\Phi_1^{(X)} = \ldots = \Phi_p^{(X)} = 0$ — X không cause Y
            </div>
            <div class="hyp hyp-h1">
                <strong>H₁:</strong> Ít nhất một $\Phi_i^{(X)} \neq 0$
            </div>
        </div>

        <p>
            <span class="highlight-orange">Cross-check:</span> So sánh kết quả Granger (Phase 2) với Toda-Yamamoto.
            Tỷ lệ đồng thuận (Agreement %) cho biết mức độ nhất quán giữa hai phương pháp — tỷ lệ cao tăng độ tin cậy kết luận.
        </p>
    </div>
</div>

<div id="ty-root">
    <div id="ty-loading">
        <div class="rounded-xl p-6 animate-pulse" style="background-color: var(--color-bg-card);">
            <div class="h-4 w-48 rounded mb-4" style="background-color: var(--color-border);"></div>
            <div class="h-32 rounded" style="background-color: var(--color-bg-input);"></div>
        </div>
    </div>
    <div id="ty-error" class="hidden"></div>
    <div id="ty-content" class="hidden space-y-6">
        <div id="ty-agreement" class="rounded-xl p-6 border" style="background-color: var(--color-bg-card); border-color: var(--color-border);"></div>
        <div class="rounded-xl border overflow-hidden" style="background-color: var(--color-bg-card); border-color: var(--color-border);">
            <div class="overflow-x-auto">
                <table class="w-full text-sm">
                    <thead>
                        <tr style="background-color: var(--color-bg-input);">
                            <th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider" style="color: var(--color-text-muted);">Pair</th>
                            <th class="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider" style="color: var(--color-text-muted);">Granger</th>
                            <th class="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider" style="color: var(--color-text-muted);">Toda-Yamamoto</th>
                            <th class="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider" style="color: var(--color-text-muted);">Agreement</th>
                        </tr>
                    </thead>
                    <tbody id="ty-tbody"></tbody>
                </table>
            </div>
        </div>
    </div>
</div>

</div>
@endsection

@push('scripts')
<script type="module">
    async function load() {
        try {
            const data = await window.dashboardFetch('toda-yamamoto');
            document.getElementById('ty-loading').classList.add('hidden');
            document.getElementById('ty-content').classList.remove('hidden');
            render(data);
        } catch (err) {
            document.getElementById('ty-loading').classList.add('hidden');
            document.getElementById('ty-error').classList.remove('hidden');
            window.showError('ty-error', err.message);
        }
    }

    function sigBadge(val) {
        return val
            ? '<span class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium" style="background-color: rgba(59,130,246,0.15); color: var(--color-accent-blue);">Sig</span>'
            : '<span class="text-xs" style="color: var(--color-text-muted);">NS</span>';
    }

    function render(data) {
        const agr = data.summary?.agreement_pct;
        document.getElementById('ty-agreement').innerHTML = `
            <div class="flex items-center gap-4">
                <div class="text-3xl font-bold tabular-nums" style="color: var(--color-accent-blue);">${agr != null ? agr + '%' : '—'}</div>
                <div>
                    <p class="text-sm font-medium" style="color: var(--color-text-primary);">Granger–TY Agreement</p>
                    <p class="text-xs" style="color: var(--color-text-muted);">Percentage of pairs where both methods agree</p>
                </div>
            </div>
        `;

        const pairs = data.comparison ?? [];
        document.getElementById('ty-tbody').innerHTML = pairs.map(p => {
            const isMatch = p.agreement === 'agree';
            const isGrangerMissing = p.agreement === 'granger_missing';
            return `
            <tr class="border-t" style="border-color: var(--color-border);">
                <td class="px-4 py-3 font-medium" style="color: var(--color-text-primary);">${p.cause} → ${p.effect}</td>
                <td class="px-4 py-3 text-center">${p.granger_significant != null ? sigBadge(p.granger_significant) : '<span class="text-xs" style="color: var(--color-text-muted);">N/A</span>'}</td>
                <td class="px-4 py-3 text-center">${sigBadge(p.ty_significant)}</td>
                <td class="px-4 py-3 text-center">
                    ${isGrangerMissing
                        ? '<span class="text-xs" style="color: var(--color-text-muted);">N/A</span>'
                        : isMatch
                            ? '<span class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium" style="background-color: rgba(34,197,94,0.15); color: var(--color-kpi-positive);">Match</span>'
                            : '<span class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium" style="background-color: rgba(249,115,22,0.15); color: var(--color-accent-orange);">Mismatch</span>'}
                </td>
            </tr>
            `;
        }).join('');
    }

    load();
</script>
@endpush
