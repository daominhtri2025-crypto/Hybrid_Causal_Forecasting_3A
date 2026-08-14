/**
 * Client-side i18n system for Risk Dashboard.
 *
 * Architecture choice: JS-based (not Laravel lang/) because most content is
 * rendered client-side via dashboardFetch + template literals. This allows
 * instant language switching without page reload.
 *
 * Mechanism:
 *   - Static Blade text: data-i18n="key" attributes → textContent replaced
 *   - Bilingual blocks: data-lang="en" / data-lang="vi" → visibility toggled
 *   - JS-rendered content: t('key') function + onLangChange() re-render
 */

const translations = {
  en: {
    // ── Layout ──────────────────────────────────────────────
    'nav.overview':          'OVERVIEW',
    'nav.summary':           'Summary',
    'nav.causality':         'CAUSALITY ANALYSIS',
    'nav.phase1':            'Phase 1 — Stationarity',
    'nav.phase2':            'Phase 2 — Granger',
    'nav.phase3':            'Phase 3 — Cointegration',
    'nav.phase3b':           'Phase 3b — Toda-Yamamoto',
    'nav.forecasting':       'FORECASTING',
    'nav.phase4':            'Phase 4 — Forecast',
    'nav.phase5_irf':        'Phase 5 — IRF',
    'nav.phase5_fevd':       'Phase 5 — FEVD',
    'nav.footer':            'Pipeline 3A · VAR on Levels',
    'header.read_only':      'READ-ONLY',
    'header.export_pdf':     'Export PDF',
    'header.full_report':    'Full Report',
    'stepper.1':             'Stationarity',
    'stepper.2':             'Granger',
    'stepper.3':             'Cointegration',
    'stepper.4':             'Forecast',
    'stepper.5':             'IRF & FEVD',

    // ── Common ──────────────────────────────────────────────
    'common.loading':        'Loading data...',
    'common.error_title':    'Unable to load data',
    'common.yes':            'Yes',
    'common.no':             'No',
    'common.reject':         'Reject',
    'common.fail_to_reject': 'Fail to Reject',
    'common.sig':            'Sig',
    'common.ns':             'NS',
    'common.na':             'N/A',
    'common.match':          'Match',
    'common.mismatch':       'Mismatch',
    'common.stationary':     'Stationary',
    'common.non_stationary': 'Non-Stationary',
    'common.contradictory':  'Contradictory',
    'common.warnings':       'Warnings',
    'common.null_finding':   'Null Finding',

    // ── Notation Legend ─────────────────────────────────────
    'legend.title':            'Notation & Legend',
    'legend.variables':        'System Variables',
    'legend.pv':               'Production Volume',
    'legend.dr':               'Delay Rate',
    'legend.od':               'Order Demand',
    'legend.stat_notation':    'Statistical Notation',
    'legend.pvalue_def':       '$p$-value: probability of observing the test statistic under $H_0$. Smaller $p$ = stronger evidence against $H_0$.',
    'legend.fstat_def':        '$F$-statistic: test statistic for Granger causality (F-test comparing restricted vs unrestricted model).',
    'legend.lag_def':          'Lag $p$: number of past periods included in the model. Selected by AIC/BIC information criteria.',
    'legend.rank_def':         'Rank $r$: number of cointegrating relationships among variables (Johansen test).',
    'legend.adf_def':          'ADF: Augmented Dickey-Fuller test. $H_0$: unit root (non-stationary). Reject = stationary.',
    'legend.kpss_def':         'KPSS: Kwiatkowski-Phillips-Schmidt-Shin test. $H_0$: stationary. Reject = non-stationary.',
    'legend.significance':     'Significance Levels',
    'legend.sig_stars':        '$^{***}$ significant at 1% · $^{**}$ significant at 5% · $^{*}$ significant at 10%',
    'legend.ci_def':           '95% CI: 95% confidence interval — the true value lies within this range with 95% probability.',

    // ── Summary ─────────────────────────────────────────────
    'summary.title':         'System Overview',
    'summary.subtitle':      'Model configuration, KPI metrics, and pipeline status',
    'summary.kpi.route':     'Model Route',
    'summary.kpi.obs':       'Observations',
    'summary.kpi.granger':   'Granger Significant',
    'summary.kpi.dr_self':   'DelayRate Self %',
    'summary.kpi.lag_sub':   'Lag order p',
    'summary.kpi.eff_t':     'Effective T',
    'summary.kpi.causal':    'Causal pairs (p < 0.05)',
    'summary.kpi.fevd_nf':   'FEVD Null Finding',
    'summary.model_config':  'Model Configuration',
    'summary.phase_status':  'Pipeline Phase Status',
    'summary.lbl.route':     'Route',
    'summary.lbl.lag':       'Lag Order',
    'summary.lbl.vars':      'Variables',

    // ── Phase 1 — Stationarity ──────────────────────────────
    'p1.title':              'Phase 1 — Unit Root Tests',
    'p1.subtitle':           'ADF and KPSS stationarity results with Zivot-Andrews tiebreaker',
    'p1.col.variable':       'Variable',
    'p1.col.level':          'Level',
    'p1.col.adf_stat':       'ADF Stat',
    'p1.col.adf_pval':       'ADF p-val',
    'p1.col.adf':            'ADF',
    'p1.col.kpss_stat':      'KPSS Stat',
    'p1.col.kpss':           'KPSS',
    'p1.col.verdict':        'Verdict',
    'p1.sig_level':          'Significance level',
    'p1.adf_maxlag':         'ADF max lag (Schwert)',
    'p1.observations':       'Observations',

    // ── Phase 2 — Granger ───────────────────────────────────
    'p2.title':              'Phase 2 — Granger Causality',
    'p2.subtitle':           'Pairwise Granger causality test heatmap and results table',
    'p2.sig_pairs':          'Significant Pairs',
    'p2.lag_order':          'Lag Order',
    'p2.sig_level':          'Significance Level',
    'p2.heatmap_title':      'Causality Heatmap (p-values)',
    'p2.col.pair':           'Cause → Effect',
    'p2.col.fstat':          'F-stat',
    'p2.col.pvalue':         'p-value',
    'p2.col.significant':    'Significant',

    // ── Phase 3 — Cointegration ─────────────────────────────
    'p3.title':              'Phase 3 — Johansen Cointegration',
    'p3.subtitle':           'Cointegration rank determination and model route selection',
    'p3.route_label':        'Route',
    'p3.coint_rank':         'Cointegration rank r',
    'p3.col.h0':             'H0: rank ≤ r',
    'p3.col.trace':          'Trace Stat',
    'p3.col.critical':       'Critical (5%)',
    'p3.col.decision':       'Decision',
    'p3.skipped_title':      'Johansen test — no Trace/Max-Eigenvalue data',
    'p3.skipped_default':    'Pipeline did not produce Johansen test results for this dataset.',

    // ── Phase 3b — Toda-Yamamoto ────────────────────────────
    'p3b.title':             'Phase 3b — Toda-Yamamoto Cross-Check',
    'p3b.subtitle':          'Granger vs Toda-Yamamoto agreement analysis',
    'p3b.agreement':         'Granger–TY Agreement',
    'p3b.agreement_sub':     'Percentage of pairs where both methods agree',
    'p3b.col.pair':          'Pair',
    'p3b.col.granger':       'Granger',
    'p3b.col.ty':            'Toda-Yamamoto',
    'p3b.col.agreement':     'Agreement',

    // ── Phase 4 — Forecast ──────────────────────────────────
    'p4.title':              'Phase 4 — VAR Forecast',
    'p4.subtitle':           '4-week ahead forecast with 95% confidence intervals',
    'p4.lbl.route':          'Route',
    'p4.lbl.lag':            'Lag Order',
    'p4.lbl.logl':           'Log-L',
    'p4.lbl.teff':           'T_eff',
    'p4.chart_info':         'periods · 95% CI',
    'p4.tooltip.week':       'Week',
    'p4.tooltip.point':      'Point',

    // ── Phase 5 — IRF ───────────────────────────────────────
    'p5irf.title':           'Phase 5 — Impulse Response Functions',
    'p5irf.subtitle':        'Orthogonalized impulse response with 95% confidence bands',
    'p5irf.lbl.periods':     'IRF Periods',
    'p5irf.lbl.orth':        'Orthogonalization',
    'p5irf.lbl.ci':          'CI Method',
    'p5irf.lbl.ordering':    'Ordering',
    'p5irf.response':        'Response',
    'p5irf.shock':           'shock',
    'p5irf.axis.horizon':    'Horizon',
    'p5irf.axis.response':   'Response',

    // ── Phase 5 — FEVD ──────────────────────────────────────
    'p5fevd.title':          'Phase 5 — Forecast Error Variance Decomposition',
    'p5fevd.subtitle':       'Stacked variance decomposition with Null Finding highlight',
    'p5fevd.target':         'Target',
    'p5fevd.self_final':     'Self: {pct}% at final horizon',
    'p5fevd.axis.horizon':   'Horizon',
    'p5fevd.axis.variance':  'Variance %',

    // ── Phase labels (summary) ──────────────────────────────
    'phase.p1':              'Phase 1 — Stationarity',
    'phase.p2':              'Phase 2 — Granger',
    'phase.p3':              'Phase 3 — Cointegration',
    'phase.p3b':             'Phase 3b — Toda-Yamamoto',
    'phase.p4':              'Phase 4 — Forecast',
    'phase.p5':              'Phase 5 — IRF/FEVD',
  },

  vi: {
    // ── Layout ──────────────────────────────────────────────
    'nav.overview':          'TỔNG QUAN',
    'nav.summary':           'Bản tóm tắt',
    'nav.causality':         'PHÂN TÍCH NHÂN QUẢ',
    'nav.phase1':            'Giai đoạn 1 — Tính ổn định',
    'nav.phase2':            'Giai đoạn 2 — Granger',
    'nav.phase3':            'Giai đoạn 3 — Đồng tích hợp',
    'nav.phase3b':           'Giai đoạn 3b — Toda-Yamamoto',
    'nav.forecasting':       'DỰ BÁO',
    'nav.phase4':            'Giai đoạn 4 — Dự báo',
    'nav.phase5_irf':        'Giai đoạn 5 — IRF',
    'nav.phase5_fevd':       'Giai đoạn 5 — FEVD',
    'nav.footer':            'Pipeline 3A · VAR trên mức',
    'header.read_only':      'CHỈ ĐỌC',
    'header.export_pdf':     'Xuất PDF',
    'header.full_report':    'Báo cáo tổng hợp',
    'stepper.1':             'Tính ổn định',
    'stepper.2':             'Granger',
    'stepper.3':             'Đồng tích hợp',
    'stepper.4':             'Dự báo',
    'stepper.5':             'IRF & FEVD',

    // ── Common ──────────────────────────────────────────────
    'common.loading':        'Đang tải dữ liệu...',
    'common.error_title':    'Không thể tải dữ liệu',
    'common.yes':            'Có',
    'common.no':             'Không',
    'common.reject':         'Bác bỏ',
    'common.fail_to_reject': 'Không bác bỏ',
    'common.sig':            'CYN',
    'common.ns':             'KYN',
    'common.na':             'N/A',
    'common.match':          'Khớp',
    'common.mismatch':       'Không khớp',
    'common.stationary':     'Dừng',
    'common.non_stationary': 'Không dừng',
    'common.contradictory':  'Mâu thuẫn',
    'common.warnings':       'Cảnh báo',
    'common.null_finding':   'Phát hiện rỗng',

    // ── Notation Legend ─────────────────────────────────────
    'legend.title':            'Chú giải ký hiệu',
    'legend.variables':        'Biến hệ thống',
    'legend.pv':               'Sản lượng sản xuất',
    'legend.dr':               'Tỷ lệ trễ đơn hàng',
    'legend.od':               'Nhu cầu đặt hàng',
    'legend.stat_notation':    'Ký hiệu thống kê',
    'legend.pvalue_def':       '$p$-value: xác suất quan sát thống kê kiểm định dưới giả thuyết $H_0$. $p$ càng nhỏ = bằng chứng bác bỏ $H_0$ càng mạnh.',
    'legend.fstat_def':        '$F$-statistic: thống kê kiểm định nhân quả Granger (F-test so sánh mô hình ràng buộc với không ràng buộc).',
    'legend.lag_def':          'Lag $p$: số kỳ quá khứ đưa vào mô hình. Chọn theo tiêu chí thông tin AIC/BIC.',
    'legend.rank_def':         'Rank $r$: số quan hệ đồng tích hợp giữa các biến (kiểm định Johansen).',
    'legend.adf_def':          'ADF: kiểm định Augmented Dickey-Fuller. $H_0$: có nghiệm đơn vị (không dừng). Bác bỏ = dừng.',
    'legend.kpss_def':         'KPSS: kiểm định Kwiatkowski-Phillips-Schmidt-Shin. $H_0$: chuỗi dừng. Bác bỏ = không dừng.',
    'legend.significance':     'Mức ý nghĩa thống kê',
    'legend.sig_stars':        '$^{***}$ có ý nghĩa tại 1% · $^{**}$ có ý nghĩa tại 5% · $^{*}$ có ý nghĩa tại 10%',
    'legend.ci_def':           '95% CI: khoảng tin cậy 95% — giá trị thực nằm trong khoảng này với xác suất 95%.',

    // ── Summary ─────────────────────────────────────────────
    'summary.title':         'Tổng quan hệ thống',
    'summary.subtitle':      'Cấu hình mô hình, chỉ số KPI, và trạng thái pipeline',
    'summary.kpi.route':     'Lộ trình mô hình',
    'summary.kpi.obs':       'Số quan sát',
    'summary.kpi.granger':   'Granger có ý nghĩa',
    'summary.kpi.dr_self':   'DelayRate tự giải thích %',
    'summary.kpi.lag_sub':   'Bậc trễ p',
    'summary.kpi.eff_t':     'T hiệu dụng',
    'summary.kpi.causal':    'Cặp nhân quả (p < 0.05)',
    'summary.kpi.fevd_nf':   'FEVD phát hiện rỗng',
    'summary.model_config':  'Cấu hình mô hình',
    'summary.phase_status':  'Trạng thái Pipeline',
    'summary.lbl.route':     'Lộ trình',
    'summary.lbl.lag':       'Bậc trễ',
    'summary.lbl.vars':      'Các biến',

    // ── Phase 1 — Stationarity ──────────────────────────────
    'p1.title':              'Giai đoạn 1 — Kiểm định nghiệm đơn vị',
    'p1.subtitle':           'Kết quả ADF và KPSS với Zivot-Andrews làm tiebreaker',
    'p1.col.variable':       'Biến',
    'p1.col.level':          'Mức',
    'p1.col.adf_stat':       'T.kê ADF',
    'p1.col.adf_pval':       'p-val ADF',
    'p1.col.adf':            'ADF',
    'p1.col.kpss_stat':      'T.kê KPSS',
    'p1.col.kpss':           'KPSS',
    'p1.col.verdict':        'Kết luận',
    'p1.sig_level':          'Mức ý nghĩa',
    'p1.adf_maxlag':         'Lag tối đa ADF (Schwert)',
    'p1.observations':       'Số quan sát',

    // ── Phase 2 — Granger ───────────────────────────────────
    'p2.title':              'Giai đoạn 2 — Nhân quả Granger',
    'p2.subtitle':           'Heatmap và bảng kết quả kiểm định nhân quả Granger theo cặp',
    'p2.sig_pairs':          'Cặp có ý nghĩa',
    'p2.lag_order':          'Bậc trễ',
    'p2.sig_level':          'Mức ý nghĩa',
    'p2.heatmap_title':      'Heatmap nhân quả (p-values)',
    'p2.col.pair':           'Nguyên nhân → Kết quả',
    'p2.col.fstat':          'F-stat',
    'p2.col.pvalue':         'p-value',
    'p2.col.significant':    'Có ý nghĩa',

    // ── Phase 3 — Cointegration ─────────────────────────────
    'p3.title':              'Giai đoạn 3 — Đồng tích hợp Johansen',
    'p3.subtitle':           'Xác định bậc đồng tích hợp và lựa chọn lộ trình mô hình',
    'p3.route_label':        'Lộ trình',
    'p3.coint_rank':         'Bậc đồng tích hợp r',
    'p3.col.h0':             'H0: hạng ≤ r',
    'p3.col.trace':          'Thống kê dấu vết',
    'p3.col.critical':       'Nghiêm trọng (5%)',
    'p3.col.decision':       'Phán quyết',
    'p3.skipped_title':      'Johansen test — không có dữ liệu Trace/Max-Eigenvalue',
    'p3.skipped_default':    'Pipeline không tạo kết quả kiểm định Johansen cho dataset này.',

    // ── Phase 3b — Toda-Yamamoto ────────────────────────────
    'p3b.title':             'Giai đoạn 3b — Toda-Yamamoto (Cross-Check)',
    'p3b.subtitle':          'Phân tích mức đồng thuận Granger và Toda-Yamamoto',
    'p3b.agreement':         'Đồng thuận Granger–TY',
    'p3b.agreement_sub':     'Tỷ lệ cặp biến mà cả hai phương pháp cho kết quả giống nhau',
    'p3b.col.pair':          'Cặp biến',
    'p3b.col.granger':       'Granger',
    'p3b.col.ty':            'Toda-Yamamoto',
    'p3b.col.agreement':     'Đồng thuận',

    // ── Phase 4 — Forecast ──────────────────────────────────
    'p4.title':              'Giai đoạn 4 — Dự báo VAR',
    'p4.subtitle':           'Dự báo 4 tuần với khoảng tin cậy 95%',
    'p4.lbl.route':          'Lộ trình',
    'p4.lbl.lag':            'Bậc trễ',
    'p4.lbl.logl':           'Log-L',
    'p4.lbl.teff':           'T_hd',
    'p4.chart_info':         'kỳ · 95% CI',
    'p4.tooltip.week':       'Tuần',
    'p4.tooltip.point':      'Điểm',

    // ── Phase 5 — IRF ───────────────────────────────────────
    'p5irf.title':           'Giai đoạn 5 — Hàm phản ứng xung',
    'p5irf.subtitle':        'Phản ứng xung trực giao với dải tin cậy 95%',
    'p5irf.lbl.periods':     'Số kỳ IRF',
    'p5irf.lbl.orth':        'Trực giao hóa',
    'p5irf.lbl.ci':          'Phương pháp CI',
    'p5irf.lbl.ordering':    'Thứ tự',
    'p5irf.response':        'Phản ứng',
    'p5irf.shock':           'sốc',
    'p5irf.axis.horizon':    'Horizon',
    'p5irf.axis.response':   'Phản ứng',

    // ── Phase 5 — FEVD ──────────────────────────────────────
    'p5fevd.title':          'Giai đoạn 5 — Phân rã phương sai sai số dự báo',
    'p5fevd.subtitle':       'Phân rã phương sai dạng xếp chồng với phát hiện rỗng',
    'p5fevd.target':         'Mục tiêu',
    'p5fevd.self_final':     'Tự giải thích: {pct}% tại horizon cuối',
    'p5fevd.axis.horizon':   'Horizon',
    'p5fevd.axis.variance':  'Phương sai %',

    // ── Phase labels (summary) ──────────────────────────────
    'phase.p1':              'GĐ 1 — Tính ổn định',
    'phase.p2':              'GĐ 2 — Granger',
    'phase.p3':              'GĐ 3 — Đồng tích hợp',
    'phase.p3b':             'GĐ 3b — Toda-Yamamoto',
    'phase.p4':              'GĐ 4 — Dự báo',
    'phase.p5':              'GĐ 5 — IRF/FEVD',
  },
};

let currentLang = localStorage.getItem('dashboard_lang') || 'vi';
const langChangeCallbacks = [];

export function t(key) {
  return translations[currentLang]?.[key]
      ?? translations['en']?.[key]
      ?? key;
}

export function getLang() {
  return currentLang;
}

export function onLangChange(callback) {
  langChangeCallbacks.push(callback);
}

export function setLang(lang) {
  if (lang !== 'en' && lang !== 'vi') return;
  currentLang = lang;
  localStorage.setItem('dashboard_lang', lang);
  document.documentElement.lang = lang;
  applyLang();
  langChangeCallbacks.forEach(cb => cb(lang));
}

export function applyLang() {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    const val = t(key);
    if (val !== key) el.textContent = val;
  });

  document.querySelectorAll('[data-lang]').forEach(el => {
    const elLang = el.getAttribute('data-lang');
    el.style.display = elLang === currentLang ? '' : 'none';
  });

  const toggle = document.getElementById('lang-toggle');
  if (toggle) toggle.textContent = currentLang === 'en' ? 'VI' : 'EN';

  if (window.renderMath) window.renderMath();
}

export function renderNotationLegend(containerId, options = {}) {
  const el = document.getElementById(containerId);
  if (!el) return;

  const showVars = options.variables !== false;
  const showStats = options.statistics || [];
  const showSigStars = options.significance !== false;

  let html = `
    <div class="explainer-card">
      <div class="explainer-header" onclick="toggleExplainer('${containerId}-body')">
        <div class="explainer-header-left">
          <div class="explainer-icon" style="background-color: rgba(6, 182, 212, 0.12); color: var(--color-accent-cyan);">
            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A2 2 0 013 12V7a4 4 0 014-4z"/>
            </svg>
          </div>
          <div>
            <div class="explainer-title">${t('legend.title')}</div>
          </div>
        </div>
        <svg id="${containerId}-body-icon" class="explainer-chevron" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
        </svg>
      </div>
      <div id="${containerId}-body" class="explainer-body hidden math-content">`;

  if (showVars) {
    html += `
        <div class="mb-4">
          <p class="text-xs font-semibold uppercase tracking-wider mb-2" style="color: var(--color-text-muted);">
            ${t('legend.variables')}
          </p>
          <div class="grid grid-cols-1 sm:grid-cols-3 gap-2 text-sm" style="color: var(--color-text-secondary);">
            <span><span class="inline-block h-2.5 w-2.5 rounded-full mr-2" style="background: #3b82f6;"></span>
              $PV$ — ${t('legend.pv')}</span>
            <span><span class="inline-block h-2.5 w-2.5 rounded-full mr-2" style="background: #f97316;"></span>
              $DR$ — ${t('legend.dr')}</span>
            <span><span class="inline-block h-2.5 w-2.5 rounded-full mr-2" style="background: #22c55e;"></span>
              $OD$ — ${t('legend.od')}</span>
          </div>
        </div>`;
  }

  if (showStats.length > 0) {
    const statDefs = {
      'p-value': 'legend.pvalue_def',
      'f-stat':  'legend.fstat_def',
      'lag':     'legend.lag_def',
      'rank':    'legend.rank_def',
      'adf':     'legend.adf_def',
      'kpss':    'legend.kpss_def',
      'ci':      'legend.ci_def',
    };
    html += `
        <div class="mb-4">
          <p class="text-xs font-semibold uppercase tracking-wider mb-2" style="color: var(--color-text-muted);">
            ${t('legend.stat_notation')}
          </p>
          <ul class="space-y-1.5 text-sm" style="color: var(--color-text-secondary);">
            ${showStats.map(s => `<li>${t(statDefs[s] || s)}</li>`).join('')}
          </ul>
        </div>`;
  }

  if (showSigStars) {
    html += `
        <div>
          <p class="text-xs font-semibold uppercase tracking-wider mb-2" style="color: var(--color-text-muted);">
            ${t('legend.significance')}
          </p>
          <p class="text-sm" style="color: var(--color-text-secondary);">
            ${t('legend.sig_stars')}
          </p>
        </div>`;
  }

  html += `
      </div>
    </div>`;

  el.innerHTML = html;
  if (window.renderMath) window.renderMath();
}
