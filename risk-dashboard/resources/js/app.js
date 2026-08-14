import Chart from 'chart.js/auto';
import annotationPlugin from 'chartjs-plugin-annotation';
import 'katex/dist/katex.min.css';
import renderMathInElement from 'katex/dist/contrib/auto-render.mjs';
import { t, getLang, setLang, onLangChange, applyLang, renderNotationLegend } from './i18n.js';

Chart.register(annotationPlugin);

window.t = t;
window.getLang = getLang;
window.setLang = setLang;
window.onLangChange = onLangChange;
window.renderNotationLegend = renderNotationLegend;

Chart.defaults.color = '#94a3b8';
Chart.defaults.borderColor = '#334155';
Chart.defaults.font.family = "'Inter', ui-sans-serif, system-ui, sans-serif";
Chart.defaults.font.size = 12;
Chart.defaults.plugins.legend.labels.usePointStyle = true;
Chart.defaults.plugins.legend.labels.pointStyleWidth = 8;
Chart.defaults.plugins.tooltip.backgroundColor = '#1e293b';
Chart.defaults.plugins.tooltip.titleColor = '#f1f5f9';
Chart.defaults.plugins.tooltip.bodyColor = '#94a3b8';
Chart.defaults.plugins.tooltip.borderColor = '#334155';
Chart.defaults.plugins.tooltip.borderWidth = 1;
Chart.defaults.plugins.tooltip.cornerRadius = 6;
Chart.defaults.plugins.tooltip.padding = 10;
Chart.defaults.elements.point.radius = 3;
Chart.defaults.elements.point.hoverRadius = 5;
Chart.defaults.elements.line.tension = 0.3;

window.Chart = Chart;

window.DASHBOARD_COLORS = {
    blue:       '#3b82f6',
    blueFaded:  'rgba(59, 130, 246, 0.15)',
    orange:     '#f97316',
    orangeFaded:'rgba(249, 115, 22, 0.15)',
    green:      '#22c55e',
    greenFaded: 'rgba(34, 197, 94, 0.15)',
    red:        '#ef4444',
    purple:     '#a855f7',
    cyan:       '#06b6d4',
    textPrimary:'#f1f5f9',
    textSecond: '#94a3b8',
    textMuted:  '#64748b',
    cardBg:     '#1e293b',
    border:     '#334155',
};

window.VARIABLE_STYLES = {
    ProductionVolume: { color: '#3b82f6', faded: 'rgba(59, 130, 246, 0.15)', label: 'Production Volume' },
    DelayRate:        { color: '#f97316', faded: 'rgba(249, 115, 22, 0.15)', label: 'Delay Rate' },
    OrderDemand:      { color: '#22c55e', faded: 'rgba(34, 197, 94, 0.15)', label: 'Order Demand' },
};

window.dashboardFetch = async function(endpoint) {
    const res = await fetch(`/api/dashboard/${endpoint}`);
    if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.message || `API error ${res.status}`);
    }
    const json = await res.json();
    if (json.status !== 'ok') {
        throw new Error(json.message || 'Unknown API error');
    }
    return json.data;
};

window.showLoading = function(containerId) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = `
        <div class="flex flex-col items-center justify-center py-16 gap-3">
            <div class="h-8 w-8 animate-spin rounded-full border-2 border-current border-t-transparent"
                 style="color: var(--color-accent-blue);"></div>
            <p class="text-sm" style="color: var(--color-text-muted);">Loading data...</p>
        </div>`;
};

window.showError = function(containerId, message) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = `
        <div class="flex flex-col items-center justify-center py-16 gap-3 text-center">
            <svg class="h-10 w-10" style="color: var(--color-accent-red);" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
                      d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.732-.833-2.5 0L4.27 16.5c-.77.833.192 2.5 1.732 2.5z"/>
            </svg>
            <p class="text-sm font-medium" style="color: var(--color-text-primary);">Unable to load data</p>
            <p class="text-xs max-w-md" style="color: var(--color-text-muted);">${escapeHtml(message)}</p>
        </div>`;
};

window.renderMath = function() {
    document.querySelectorAll('.math-content').forEach(el => {
        renderMathInElement(el, {
            delimiters: [
                { left: '$$', right: '$$', display: true },
                { left: '$', right: '$', display: false },
            ],
            throwOnError: false,
        });
    });
};

window.exportSectionPDF = async function(sectionId, filename) {
    const html2pdf = (await import('html2pdf.js')).default;
    const element = document.getElementById(sectionId);
    if (!element) return;

    const btn = document.querySelector(`[data-export="${sectionId}"]`);
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'Exporting...';
    }

    const opt = {
        margin:       [10, 10, 10, 10],
        filename:     filename || 'report.pdf',
        image:        { type: 'jpeg', quality: 0.95 },
        html2canvas:  { scale: 2, backgroundColor: '#0f172a', useCORS: true },
        jsPDF:        { unit: 'mm', format: 'a4', orientation: 'landscape' },
    };

    try {
        await html2pdf().set(opt).from(element).save();
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = 'Export PDF';
        }
    }
};

window.toggleExplainer = function(id) {
    const body = document.getElementById(id);
    const icon = document.getElementById(id + '-icon');
    if (!body) return;
    const isHidden = body.classList.contains('hidden');
    body.classList.toggle('hidden');
    if (icon) icon.style.transform = isHidden ? 'rotate(180deg)' : 'rotate(0deg)';
    if (isHidden) window.renderMath();
};

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

document.addEventListener('DOMContentLoaded', () => {
    applyLang();
    window.renderMath();
});
