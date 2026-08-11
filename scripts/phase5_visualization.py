"""
Phase 5 — Trực quan hóa Hàm phản ứng xung (IRF) và Phân rã phương sai (FEVD)

Mục đích:
  Tạo 2 biểu đồ cốt lõi phục vụ Chương 4 (Kết quả thực nghiệm) luận án:
    (1) Impulse Response Function (IRF) — phản ứng của DelayRate khi có cú sốc
        1 SD từ OEE_Score và OrderVolume (orthogonalized, Cholesky ordering).
    (2) Forecast Error Variance Decomposition (FEVD) — phân rã phương sai sai
        số dự báo của DelayRate theo đóng góp từ từng biến qua 12 tuần.

  Hỗ trợ cả hai route từ Phase 3:
    - route = "VECM": fit VECM → IRF/FEVD (có error correction term)
    - route = "VAR_on_levels": fit VAR trên levels → IRF/FEVD (không đồng tích hợp)

Cơ sở toán học:
  ═══════════════

  (A) Orthogonalized IRF (Lütkepohl 2005, Mục 2.3.2, 9.1–9.2):
  ──────────────────────────────────────────────────────────────
      Θ_h = Ψ_h · P

      Trong đó:
        Ψ_h: ma trận hệ số MA (Moving Average) bậc h — từ biểu diễn VMA(∞)
             của process LEVELS (Ψ_0 = I).
        P:   lower Cholesky factor của Σ_u (ma trận hiệp phương sai innovation).
             P cho phép trực giao hóa (orthogonalize) các shock — loại bỏ
             tương quan đồng thời (contemporaneous correlation) giữa các biến.

      Cholesky Ordering (thứ tự nhận dạng cấu trúc):
        Biến đứng TRƯỚC trong ordering được coi là "ngoại sinh hơn": shock của
        nó ảnh hưởng đồng thời lên TẤT CẢ biến phía sau, nhưng KHÔNG bị ảnh
        hưởng ngược lại ở cùng thời điểm (recursive causal assumption).

        Ordering đề xuất (dựa trên kết quả α — half-life từ Khung VECM):
          OrderVolume → OEE_Score → Revenue → DelayRate

        Lý do:
          - OrderVolume: ngoại sinh nhất — khối lượng đơn hàng xác định bởi thị
            trường, hệ thống sản xuất không kiểm soát được.
          - OEE_Score: near-weakly-exogenous (half-life ~86 tuần) — driver chậm
            thay đổi, phản ánh năng lực sản xuất nền tảng.
          - Revenue: phản ứng trung bình (half-life vừa phải) — kết quả tài
            chính phụ thuộc cả volume lẫn hiệu suất.
          - DelayRate: nội sinh nhất — fast responder (half-life ~0.7 tuần),
            biến "hấp thụ" mọi cú sốc từ hệ thống.

  (B) FEVD (Lütkepohl 2005, Mục 2.3.3):
  ──────────────────────────────────────
      FEVD_h(i, j) = Σ_{t=0}^{h-1} [Θ_{t}(i,j)]² / Σ_{t=0}^{h-1} Σ_k [Θ_{t}(i,k)]²

      Đo tỷ lệ (%) phương sai sai số dự báo của biến i ở tầm h do shock
      cấu trúc j gây ra. Tổng FEVD(i, :, h) = 100% ∀ i, h.

      Ý nghĩa: nếu OEE shock giải thích 6% variance của DelayRate, nghĩa là
      thay đổi hiệu suất sản xuất có tác động nhân quả trực tiếp — không phải
      noise ngẫu nhiên — lên tỷ lệ giao hàng trễ.

Tham khảo:
  - Lütkepohl, H. (2005). New Introduction to Multiple Time Series Analysis.
    Springer. Chương 2.3, 9.1–9.2.
  - Sims, C.A. (1980). Macroeconomics and Reality. Econometrica, 48(1), 1–48.
  - Johansen, S. (1995). Likelihood-Based Inference in Cointegrated VAR Models.
    Oxford University Press.

Input:
  - data/processed/causal_weekly_dataset.csv (dữ liệu tuần — output Phase 0)
  - reports/phase3_cointegration.json (coint_rank, k_ar_diff — Tầng 3)

Output:
  - data/processed/figures/irf_delayrate_response.png (biểu đồ IRF, DPI=300)
  - data/processed/figures/fevd_delayrate_decomposition.png (biểu đồ FEVD, DPI=300)
  - reports/phase5_irf_fevd_results.json (số liệu IRF + FEVD — machine-readable)

Tuân thủ: CLAUDE.md mục 2 (bất biến dữ liệu), 3.1 (comment tiếng Việt),
          3.3 (không hard-code — đọc từ Phase 3 JSON), 3.5 (reproducibility),
          7 (logging chuẩn).
"""

import os
import sys
import json
import warnings
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator, PercentFormatter
from scipy import linalg as la
from statsmodels.tsa.vector_ar.vecm import VECM
from statsmodels.tsa.api import VAR as VARModel
from statsmodels.tsa.vector_ar.irf import IRAnalysis

# ── Import tiện ích dùng chung (CLAUDE.md mục 7.1) ──
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import get_logger, get_base_dir

# ══════════════════════════════════════════════════════════════════════
# HẰNG SỐ
# ══════════════════════════════════════════════════════════════════════

# Thứ tự biến gốc — KHỚP với Tầng 3 và Tầng 4
ANALYSIS_VARIABLES = ["OEE_Score", "DelayRate", "Revenue", "OrderVolume"]

# Cholesky ordering: ngoại sinh → nội sinh (dựa trên kết quả half-life α)
CHOLESKY_ORDER = ["OrderVolume", "OEE_Score", "Revenue", "DelayRate"]

# Thời gian mô phỏng dư chấn
IRF_PERIODS = 12

# Seed cho reproducibility (CLAUDE.md mục 3.5)
np.random.seed(42)

# Nhãn hiển thị tiếng Việt cho biểu đồ
DISPLAY_NAMES = {
    "OEE_Score": "OEE Score",
    "DelayRate": "Delay Rate",
    "Revenue": "Doanh thu (Revenue)",
    "OrderVolume": "Khối lượng đơn hàng (Order Volume)",
}

# ══════════════════════════════════════════════════════════════════════
# STYLE CONFIGURATION — chuẩn học thuật (Academic Style)
# ══════════════════════════════════════════════════════════════════════

# Palette phân biệt rõ ràng trên cả in đen trắng lẫn màn hình
COLORS = {
    "OEE_Score":   "#1B5E4B",   # xanh đậm — driver chính
    "DelayRate":   "#C44E52",   # đỏ gạch — target variable
    "Revenue":     "#4C72B0",   # xanh dương — biến tài chính
    "OrderVolume": "#DD8452",   # cam — biến ngoại sinh
}

# Hatching patterns cho FEVD (hỗ trợ in đen trắng)
HATCHES = {
    "OEE_Score":   "//",
    "DelayRate":   "",
    "Revenue":     "\\\\",
    "OrderVolume": "xx",
}


def _setup_academic_style():
    """
    Cấu hình matplotlib cho biểu đồ đạt chuẩn công bố khoa học.
    Font serif + lưới mờ + kích thước label phù hợp tạp chí.
    """
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["DejaVu Serif", "Times New Roman", "Georgia"],
        "font.size": 10,
        "axes.titlesize": 11,
        "axes.labelsize": 10,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.fontsize": 9,
        "figure.dpi": 100,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "axes.grid": True,
        "grid.alpha": 0.3,
        "grid.linewidth": 0.5,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 0.8,
        "lines.linewidth": 1.5,
    })


# ══════════════════════════════════════════════════════════════════════
# HÀM TIỆN ÍCH
# ══════════════════════════════════════════════════════════════════════

def _safe_float(val):
    """Chuyển numpy scalar → Python native type (JSON-safe)."""
    if isinstance(val, (np.floating, float)):
        return float(val)
    if isinstance(val, (np.integer, int)):
        return int(val)
    if isinstance(val, np.bool_):
        return bool(val)
    return val


def _build_cholesky_P(sigma_u, orig_vars, chol_order, logger):
    """
    Xây dựng ma trận Cholesky P với thứ tự biến tùy chỉnh.

    Phương pháp:
      1. Xây permutation matrix Q: ánh xạ orig_vars → chol_order
      2. Reorder Σ_u: Σ_r = Q·Σ_u·Q'
      3. Cholesky decompose: L = chol(Σ_r)
      4. Ánh xạ ngược: P = Q'·L (P·P' = Σ_u ✓)

    Kết quả: orth_irfs[t, i, j] với:
      - i: response variable theo orig_vars
      - j: structural shock theo chol_order
        (j=0 → chol_order[0] shock, j=1 → chol_order[1] shock, v.v.)

    Tham khảo: Lütkepohl (2005), Mục 2.3.2 — Proposition 2.1.
    """
    n = len(orig_vars)
    chol_idx = [orig_vars.index(v) for v in chol_order]

    Q = np.zeros((n, n))
    for new_pos, orig_pos in enumerate(chol_idx):
        Q[new_pos, orig_pos] = 1.0

    sigma_r = Q @ sigma_u @ Q.T

    # Cholesky cần ma trận dương xác định (PD). Với mẫu nhỏ (DoF ≈ 0),
    # sigma_u có thể suy biến hoàn toàn (eigenvalue ≤ 0) — ridge đơn giản
    # không đủ. Giải pháp: phân tích eigenvalue, kẹp (clamp) mọi eigenvalue
    # ≤ 0 lên ngưỡng dương nhỏ, tái tạo ma trận PD rồi Cholesky.
    try:
        L = la.cholesky(sigma_r, lower=True)
    except np.linalg.LinAlgError:
        eigvals, eigvecs = np.linalg.eigh(sigma_r)
        # Ngưỡng clamp: max(eigenvalue) × 1e-8, tối thiểu 1e-12
        clamp_floor = max(np.max(np.abs(eigvals)) * 1e-8, 1e-12)
        n_clamped = int(np.sum(eigvals < clamp_floor))
        eigvals_fixed = np.maximum(eigvals, clamp_floor)
        sigma_r = eigvecs @ np.diag(eigvals_fixed) @ eigvecs.T
        # Đảm bảo đối xứng hoàn hảo sau tính toán số
        sigma_r = (sigma_r + sigma_r.T) / 2.0
        L = la.cholesky(sigma_r, lower=True)
        logger.warning(
            f"sigma_u suy biến — đã kẹp {n_clamped}/{n} eigenvalue "
            f"lên ngưỡng {clamp_floor:.2e} để Cholesky phân rã thành công. "
            f"Eigenvalues gốc: {np.array2string(eigvals, precision=4)}."
        )

    P_full = Q.T @ L

    # Kiểm tra tính đúng đắn: P·P' phải xấp xỉ Σ_u
    recon_err = np.max(np.abs(P_full @ P_full.T - sigma_u))
    if recon_err > 1e-6:
        logger.warning(
            f"Sai số tái tạo Cholesky lớn: {recon_err:.2e}. "
            f"Kiểm tra lại thứ tự biến."
        )
    else:
        logger.info(
            f"Cholesky P xây dựng thành công. "
            f"Sai số tái tạo: {recon_err:.2e}."
        )

    logger.info(f"Cholesky ordering: {' → '.join(chol_order)}")
    logger.info(
        f"  Ý nghĩa: {chol_order[0]} (ngoại sinh nhất) → "
        f"{chol_order[-1]} (nội sinh nhất)"
    )

    return P_full, chol_idx


def _compute_fevd(orth_irfs, n_vars, periods, chol_order, logger):
    """
    Tính FEVD (Forecast Error Variance Decomposition) thủ công từ orth_irfs.

    Công thức (Lütkepohl 2005, eq. 2.3.9):
      FEVD_h(i, j) = Σ_{t=0}^{h-1} [Θ_t(i,j)]² / Σ_{t=0}^{h-1} Σ_k [Θ_t(i,k)]²

    Trả về: dict {biến: list[float]} — phần trăm đóng góp tại mỗi horizon.
    """
    # orth_irfs shape: (periods+1, n_vars, n_vars) — bao gồm t=0
    # Chỉ dùng t=0..periods-1 cho FEVD (h=1..periods)

    # Tính FEVD cho TẤT CẢ biến response (để lưu JSON đầy đủ), không chỉ DelayRate
    fevd_all = {}
    for resp_idx, resp_var in enumerate(ANALYSIS_VARIABLES):
        fevd_var = {}
        for shock_col, shock_name in enumerate(chol_order):
            fracs = []
            for h in range(1, periods + 1):
                # Tử số: variance do shock j từ t=0 đến t=h-1
                numer = sum(
                    orth_irfs[t, resp_idx, shock_col] ** 2 for t in range(h)
                )
                # Mẫu số: tổng variance từ tất cả shocks
                denom = sum(
                    sum(orth_irfs[t, resp_idx, k] ** 2 for k in range(n_vars))
                    for t in range(h)
                )
                frac = numer / denom if denom > 0 else 0.0
                fracs.append(_safe_float(frac))
            fevd_var[shock_name] = fracs
        fevd_all[resp_var] = fevd_var

    # Log FEVD cho DelayRate tại các mốc quan trọng
    dr_fevd = fevd_all["DelayRate"]
    for h in [1, 4, 8, 12]:
        idx = h - 1
        parts = ", ".join(
            f"{name}: {dr_fevd[name][idx] * 100:.1f}%"
            for name in chol_order
        )
        logger.info(f"  FEVD(DelayRate, h={h}): {parts}")

    return fevd_all


# ══════════════════════════════════════════════════════════════════════
# VẼ BIỂU ĐỒ
# ══════════════════════════════════════════════════════════════════════

def _plot_irf(orth_irfs, orth_se, chol_order, fig_path, logger):
    """
    Vẽ biểu đồ IRF: phản ứng của DelayRate khi có shock từ OEE và OrderVolume.

    Layout: 2 subplot ngang (1 hàng × 2 cột).
    Mỗi subplot: đường phản ứng ± dải tin cậy 95% (shaded area).

    Trục hoành: tuần (0–12). Trục tung: mức thay đổi DelayRate (đơn vị gốc).
    """
    _setup_academic_style()

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.2), sharey=False)

    response_idx = ANALYSIS_VARIABLES.index("DelayRate")

    # Hai cú sốc cần vẽ: OEE_Score và OrderVolume
    impulse_configs = [
        {
            "var": "OEE_Score",
            "shock_col": chol_order.index("OEE_Score"),
            "title": "(a) Shock từ OEE Score → Delay Rate",
            "color": COLORS["OEE_Score"],
        },
        {
            "var": "OrderVolume",
            "shock_col": chol_order.index("OrderVolume"),
            "title": "(b) Shock từ Order Volume → Delay Rate",
            "color": COLORS["OrderVolume"],
        },
    ]

    # periods+1 điểm trong orth_irfs (t=0..12)
    t_vals = np.arange(IRF_PERIODS + 1)

    for ax, cfg in zip(axes, impulse_configs):
        j = cfg["shock_col"]

        # Đường phản ứng chính
        irf_vals = orth_irfs[:, response_idx, j]

        # Khoảng tin cậy 95% (±1.96 SE)
        se_vals = orth_se[:, response_idx, j]
        upper = irf_vals + 1.96 * se_vals
        lower = irf_vals - 1.96 * se_vals

        # Dải tin cậy (shaded area)
        ax.fill_between(
            t_vals, lower, upper,
            alpha=0.18, color=cfg["color"],
            label="95% CI",
        )

        # Đường phản ứng chính — nét liền, đậm
        ax.plot(
            t_vals, irf_vals,
            color=cfg["color"], linewidth=2.0,
            marker="o", markersize=3.5,
            label=f"Phản ứng DelayRate",
            zorder=5,
        )

        # Đường zero reference — nét đứt xám
        ax.axhline(y=0, color="#888888", linewidth=0.7, linestyle="--", zorder=1)

        ax.set_title(cfg["title"], fontweight="bold", pad=8)
        ax.set_xlabel("Tuần sau cú sốc (Weeks)")
        ax.set_ylabel("Thay đổi Delay Rate")
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.legend(loc="best", framealpha=0.85, edgecolor="#CCCCCC")

    fig.suptitle(
        "Hàm Phản ứng Xung — Orthogonalized IRF (Cholesky decomposition)",
        fontsize=12, fontweight="bold", y=1.02,
    )

    # Ghi chú Cholesky ordering bên dưới biểu đồ
    ordering_text = " → ".join(chol_order)
    fig.text(
        0.5, -0.04,
        f"Cholesky ordering: {ordering_text} (ngoại sinh → nội sinh)",
        ha="center", va="top", fontsize=8, fontstyle="italic",
        color="#666666",
    )

    plt.tight_layout()
    fig.savefig(fig_path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info(f"Đã lưu biểu đồ IRF: {fig_path}")


def _plot_fevd(fevd_data, chol_order, fig_path, logger):
    """
    Vẽ biểu đồ FEVD dạng Stacked Area Chart cho DelayRate qua 12 tuần.

    Trục hoành: tầm dự báo (1–12 tuần).
    Trục tung: phần trăm đóng góp vào phương sai sai số dự báo (0–100%).
    Mỗi vùng (area) = đóng góp của 1 biến, tô màu + hatching.
    """
    _setup_academic_style()

    fig, ax = plt.subplots(figsize=(8, 5))

    dr_fevd = fevd_data["DelayRate"]
    horizons = np.arange(1, IRF_PERIODS + 1)

    # Chuyển sang phần trăm
    # Thứ tự stack: từ dưới lên = DelayRate (lớn nhất) → các biến còn lại
    stack_order = ["DelayRate", "OEE_Score", "OrderVolume", "Revenue"]
    stack_data = np.array([
        [dr_fevd[v][h] * 100 for h in range(IRF_PERIODS)]
        for v in stack_order
    ])

    # Stacked area
    ax.stackplot(
        horizons,
        stack_data,
        labels=[DISPLAY_NAMES.get(v, v) for v in stack_order],
        colors=[COLORS[v] for v in stack_order],
        alpha=0.75,
        edgecolor="white",
        linewidth=0.5,
    )

    # Thêm hatching patterns (hỗ trợ in đen trắng)
    for collection, var in zip(ax.collections, stack_order):
        collection.set_hatch(HATCHES[var])
        collection.set_edgecolor("white")

    ax.set_title(
        "Phân rã phương sai sai số dự báo (FEVD) — Delay Rate",
        fontweight="bold", pad=10,
    )
    ax.set_xlabel("Tầm dự báo (Tuần)")
    ax.set_ylabel("Đóng góp vào phương sai (%)")
    ax.set_xlim(1, IRF_PERIODS)
    ax.set_ylim(0, 100)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.yaxis.set_major_formatter(PercentFormatter(100, decimals=0))

    # Legend bên ngoài để không che biểu đồ
    ax.legend(
        loc="upper left", bbox_to_anchor=(1.02, 1.0),
        framealpha=0.9, edgecolor="#CCCCCC",
        title="Nguồn shock",
        title_fontsize=9,
    )

    # Annotation: đánh dấu giá trị OEE tại h=12
    oee_h12 = dr_fevd["OEE_Score"][IRF_PERIODS - 1] * 100
    delay_h12 = dr_fevd["DelayRate"][IRF_PERIODS - 1] * 100

    # Ghi chú tỷ lệ đóng góp cụ thể tại h=4 và h=12
    for h_mark in [4, 12]:
        idx = h_mark - 1
        oee_pct = dr_fevd["OEE_Score"][idx] * 100
        ov_pct = dr_fevd["OrderVolume"][idx] * 100
        y_pos = dr_fevd["DelayRate"][idx] * 100 + oee_pct / 2
        ax.annotate(
            f"OEE: {oee_pct:.1f}%\nVol: {ov_pct:.1f}%",
            xy=(h_mark, y_pos + ov_pct / 2 + 1),
            fontsize=7.5, ha="center", va="bottom",
            color="#333333",
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#CCCCCC",
                      alpha=0.85),
        )

    # Cholesky ordering footnote
    ordering_text = " → ".join(chol_order)
    fig.text(
        0.5, -0.03,
        f"Cholesky ordering: {ordering_text} (ngoại sinh → nội sinh)",
        ha="center", va="top", fontsize=8, fontstyle="italic",
        color="#666666",
    )

    plt.tight_layout()
    fig.savefig(fig_path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info(f"Đã lưu biểu đồ FEVD: {fig_path}")


# ══════════════════════════════════════════════════════════════════════
# HÀM CHÍNH
# ══════════════════════════════════════════════════════════════════════

def run_phase5(input_csv=None, phase3_json=None):
    """
    Chạy Phase 5: fit lại VECM → trực giao hóa IRF → FEVD → vẽ biểu đồ.

    Pipeline không lưu đối tượng model giữa các Phase (chỉ lưu JSON),
    nên Phase 5 fit lại mô hình (VECM hoặc VAR) với CÙNG tham số khóa
    cứng từ Phase 3 — đảm bảo tái lập (reproducibility) và nhất quán
    với Tầng 4.

    Tham số:
        input_csv:   đường dẫn CSV (mặc định data/processed/causal_weekly_dataset.csv)
        phase3_json: đường dẫn JSON Phase 3 (mặc định reports/phase3_cointegration.json)

    Trả về:
        dict chứa đường dẫn output files và FEVD data.
    """
    logger = get_logger("phase5_viz")
    logger.info("=" * 70)
    logger.info("PHASE 5 — TRỰC QUAN HÓA IRF + FEVD BẮT ĐẦU")
    logger.info("=" * 70)
    start_time = datetime.now()

    base_dir = get_base_dir()

    # ══════════════════════════════════════════════════════════════════
    # BƯỚC 1: Đọc tham số KHÓA CỨNG từ Phase 3 (CLAUDE.md mục 3.3)
    # ══════════════════════════════════════════════════════════════════
    if phase3_json is None:
        phase3_json = os.path.join(base_dir, "reports", "phase3_cointegration.json")

    if not os.path.exists(phase3_json):
        msg = (
            f"Không tìm thấy file Phase 3: {phase3_json} — "
            f"cần chạy Phase 3 trước."
        )
        logger.error(msg)
        raise FileNotFoundError(msg)

    with open(phase3_json, "r", encoding="utf-8") as f:
        phase3 = json.load(f)

    route = phase3["route"]

    if route not in ("VECM", "VAR_on_levels", "VAR_on_differences"):
        msg = (
            f"Phase 3 chỉ định route '{route}' không được hỗ trợ. "
            f"Phase 5 hỗ trợ: VECM, VAR_on_levels, VAR_on_differences."
        )
        logger.error(msg)
        raise ValueError(msg)

    logger.info(f"Tham số KHÓA CỨNG từ Phase 3:")
    logger.info(f"  route      = {route}")

    is_var_route = route in ("VAR_on_levels", "VAR_on_differences")

    if route == "VECM":
        COINT_RANK = phase3["coint_rank"]
        K_AR_DIFF = phase3.get("johansen_result", {}).get("k_ar_diff", 0)
        logger.info(f"  coint_rank = {COINT_RANK}")
        logger.info(f"  k_ar_diff  = {K_AR_DIFF}")
    else:
        LAG_ORDER = phase3.get("lag_selection", {}).get("selected_lag", 1)
        logger.info(f"  lag_order  = {LAG_ORDER}")
        if route == "VAR_on_differences":
            logger.info("  fit_on     = sai phân bậc 1 (Δy)")

    # ══════════════════════════════════════════════════════════════════
    # BƯỚC 2: Đọc dữ liệu và fit mô hình (VECM hoặc VAR, tùy route)
    # ══════════════════════════════════════════════════════════════════
    if input_csv is None:
        input_csv = os.path.join(
            base_dir, "data", "processed", "causal_weekly_dataset.csv"
        )

    logger.info(f"Đọc dữ liệu: {input_csv}")
    df = pd.read_csv(input_csv, parse_dates=["week_start"]).copy()
    n_obs = len(df)
    logger.info(f"Số quan sát: {n_obs} tuần")

    endog = df[ANALYSIS_VARIABLES].values.copy()
    n_vars = len(ANALYSIS_VARIABLES)

    if route == "VECM":
        logger.info(
            f"Fitting VECM(k_ar_diff={K_AR_DIFF}, coint_rank={COINT_RANK}, "
            f"det='co') — tái lập từ Tầng 4..."
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = VECM(
                endog,
                k_ar_diff=K_AR_DIFF,
                coint_rank=COINT_RANK,
                deterministic="co",
            )
            model_result = model.fit()
        is_vecm = True
        logger.info("VECM fit thành công.")

    else:  # VAR_on_levels hoặc VAR_on_differences
        if route == "VAR_on_differences":
            # Sai phân bậc 1: IRF/FEVD trên Δy cho biết phản ứng trong
            # thay đổi (changes), không phải mức (levels) — đây là diễn giải
            # chuẩn khi biến gốc là I(1).
            endog_fit = np.diff(endog, axis=0)
            fit_label = "Δy (sai phân bậc 1)"
        else:
            endog_fit = endog
            fit_label = "levels"

        logger.info(
            f"Fitting VAR(p={LAG_ORDER}, trend='c') trên {fit_label} — "
            f"tái lập từ Tầng 4..."
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            endog_df = pd.DataFrame(endog_fit, columns=ANALYSIS_VARIABLES)
            var_model = VARModel(endog_df)
            model_result = var_model.fit(maxlags=LAG_ORDER, ic=None, trend="c")
        is_vecm = False
        logger.info(f"VAR({model_result.k_ar}) fit thành công trên {fit_label}.")

    # ══════════════════════════════════════════════════════════════════
    # BƯỚC 3: Xây dựng Cholesky P với thứ tự tùy chỉnh
    # ══════════════════════════════════════════════════════════════════
    logger.info("─" * 60)
    logger.info("CHOLESKY ORDERING — TRỰC GIAO HÓA")
    logger.info("─" * 60)

    sigma_u = np.asarray(model_result.sigma_u)
    P_full, chol_idx = _build_cholesky_P(
        sigma_u, ANALYSIS_VARIABLES, CHOLESKY_ORDER, logger
    )

    # ══════════════════════════════════════════════════════════════════
    # BƯỚC 4: Tính IRF trực giao hóa (Orthogonalized IRF)
    # ══════════════════════════════════════════════════════════════════
    logger.info("─" * 60)
    logger.info(f"IMPULSE RESPONSE FUNCTION (IRF) — {IRF_PERIODS} tuần")
    logger.info("─" * 60)

    # Truyền P tùy chỉnh vào IRAnalysis để orth_irfs phản ánh Cholesky ordering
    # vecm=True cho VECM (cần chuyển từ VECM → VAR representation trước IRF)
    # vecm=False cho VAR (IRF tính trực tiếp từ VAR coefficients)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        irf_obj = IRAnalysis(
            model_result, P=P_full, periods=IRF_PERIODS, vecm=is_vecm
        )

    orth_irfs = irf_obj.orth_irfs   # shape: (periods+1, n_vars, n_vars)

    # Standard errors cho khoảng tin cậy (asymptotic — Lütkepohl 2005, Prop. 3.6)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        orth_se = irf_obj.stderr(orth=True)  # shape: (periods+1, n_vars, n_vars)

    logger.info(f"orth_irfs shape: {orth_irfs.shape}")
    logger.info(f"orth_se shape:   {orth_se.shape}")

    # Log IRF cho 2 cặp quan trọng
    resp_idx = ANALYSIS_VARIABLES.index("DelayRate")
    oee_col = CHOLESKY_ORDER.index("OEE_Score")
    ov_col = CHOLESKY_ORDER.index("OrderVolume")

    logger.info("IRF: Phản ứng DelayRate ← OEE shock (1 SD):")
    for t in range(IRF_PERIODS + 1):
        val = orth_irfs[t, resp_idx, oee_col]
        se = orth_se[t, resp_idx, oee_col]
        logger.info(f"  t={t:2d}: {val:+.6f} (SE={se:.6f})")

    logger.info("IRF: Phản ứng DelayRate ← OrderVolume shock (1 SD):")
    for t in range(IRF_PERIODS + 1):
        val = orth_irfs[t, resp_idx, ov_col]
        se = orth_se[t, resp_idx, ov_col]
        logger.info(f"  t={t:2d}: {val:+.6f} (SE={se:.6f})")

    # ══════════════════════════════════════════════════════════════════
    # BƯỚC 5: Tính FEVD (Forecast Error Variance Decomposition)
    # ══════════════════════════════════════════════════════════════════
    logger.info("─" * 60)
    logger.info(f"FORECAST ERROR VARIANCE DECOMPOSITION (FEVD) — DelayRate")
    logger.info("─" * 60)

    fevd_all = _compute_fevd(
        orth_irfs, n_vars, IRF_PERIODS, CHOLESKY_ORDER, logger
    )

    # ══════════════════════════════════════════════════════════════════
    # BƯỚC 6: Vẽ biểu đồ
    # ══════════════════════════════════════════════════════════════════
    logger.info("─" * 60)
    logger.info("VẼ BIỂU ĐỒ (Academic Style, DPI=300)")
    logger.info("─" * 60)

    fig_dir = os.path.join(base_dir, "data", "processed", "figures")
    os.makedirs(fig_dir, exist_ok=True)

    irf_path = os.path.join(fig_dir, "irf_delayrate_response.png")
    _plot_irf(orth_irfs, orth_se, CHOLESKY_ORDER, irf_path, logger)

    fevd_path = os.path.join(fig_dir, "fevd_delayrate_decomposition.png")
    _plot_fevd(fevd_all, CHOLESKY_ORDER, fevd_path, logger)

    # ══════════════════════════════════════════════════════════════════
    # BƯỚC 7: Lưu kết quả JSON (machine-readable)
    # ══════════════════════════════════════════════════════════════════
    logger.info("─" * 60)
    logger.info("LƯU KẾT QUẢ JSON")
    logger.info("─" * 60)

    # Chuẩn bị IRF data cho JSON — chỉ lưu các cặp quan trọng nhất
    irf_json_data = {}
    for shock_var in CHOLESKY_ORDER:
        shock_col = CHOLESKY_ORDER.index(shock_var)
        for resp_var in ANALYSIS_VARIABLES:
            r_idx = ANALYSIS_VARIABLES.index(resp_var)
            key = f"{shock_var}_shock_to_{resp_var}"
            irf_json_data[key] = {
                "irf_values": [
                    _safe_float(orth_irfs[t, r_idx, shock_col])
                    for t in range(IRF_PERIODS + 1)
                ],
                "std_errors": [
                    _safe_float(orth_se[t, r_idx, shock_col])
                    for t in range(IRF_PERIODS + 1)
                ],
                "lower_95": [
                    _safe_float(
                        orth_irfs[t, r_idx, shock_col]
                        - 1.96 * orth_se[t, r_idx, shock_col]
                    )
                    for t in range(IRF_PERIODS + 1)
                ],
                "upper_95": [
                    _safe_float(
                        orth_irfs[t, r_idx, shock_col]
                        + 1.96 * orth_se[t, r_idx, shock_col]
                    )
                    for t in range(IRF_PERIODS + 1)
                ],
            }

    output = {
        "metadata": {
            "script": "phase5_visualization.py",
            "timestamp": datetime.now().isoformat(),
            "input_csv": os.path.relpath(input_csv, base_dir),
            "phase3_json": os.path.relpath(phase3_json, base_dir),
            "n_observations": n_obs,
            "irf_periods": IRF_PERIODS,
            "cholesky_ordering": CHOLESKY_ORDER,
            "cholesky_ordering_rationale": (
                "Ngoại sinh → nội sinh, dựa trên half-life từ ma trận α: "
                "OrderVolume (exogenous, thị trường quyết định) → "
                "OEE_Score (near-weakly-exogenous, half-life ~86 tuần) → "
                "Revenue (phản ứng trung bình) → "
                "DelayRate (fast responder, half-life ~0.7 tuần)"
            ),
            "orthogonalization": "Cholesky (Lütkepohl 2005, Mục 2.3.2)",
            "ci_method": "Asymptotic SE (Lütkepohl 2005, Prop. 3.6)",
            "variables": ANALYSIS_VARIABLES,
        },
        "locked_parameters": (
            {
                "route": "VECM",
                "coint_rank": COINT_RANK,
                "k_ar_diff": K_AR_DIFF,
                "deterministic": "co",
            } if is_vecm else {
                "route": route,
                "lag_order": int(model_result.k_ar),
                "trend": "c",
                "fit_on": "differences" if route == "VAR_on_differences" else "levels",
            }
        ),
        "irf": irf_json_data,
        "fevd": fevd_all,
        "figures": {
            "irf": os.path.relpath(irf_path, base_dir),
            "fevd": os.path.relpath(fevd_path, base_dir),
        },
    }

    json_path = os.path.join(base_dir, "reports", "phase5_irf_fevd_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    logger.info(f"Đã lưu JSON: {json_path}")

    # ══════════════════════════════════════════════════════════════════
    # TỔNG KẾT
    # ══════════════════════════════════════════════════════════════════
    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info("=" * 70)
    logger.info(f"PHASE 5 — IRF + FEVD HOÀN TẤT trong {elapsed:.1f}s")
    logger.info(f"  IRF figure:  {irf_path}")
    logger.info(f"  FEVD figure: {fevd_path}")
    logger.info(f"  JSON output: {json_path}")
    logger.info("=" * 70)

    return {
        "irf_figure": irf_path,
        "fevd_figure": fevd_path,
        "results_json": json_path,
        "fevd_data": fevd_all,
        "model_result": model_result,
    }


# ══════════════════════════════════════════════════════════════════════
# Entry point: chạy độc lập bằng `python phase5_visualization.py`
# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    run_phase5()
