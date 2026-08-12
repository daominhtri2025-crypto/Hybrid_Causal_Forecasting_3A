"""
Tầng 3 — Phase 3: Kiểm định đồng tích hợp Johansen (Johansen Cointegration).

Mục đích:
    Xác định RANK đồng tích hợp (cointegration rank r) giữa các biến trong
    hệ thống, bằng thủ tục tuần tự Johansen (1991, 1995).

    Đồng tích hợp là gì:
        Khi các chuỗi thời gian đều không dừng (I(1)) riêng lẻ, nhưng tồn
        tại TỔ HỢP TUYẾN TÍNH giữa chúng là dừng (I(0)) → các chuỗi này
        có quan hệ cân bằng dài hạn (long-run equilibrium). Ví dụ:
          - ProductionVolume và DelayRate có thể lệch nhau ngắn hạn, nhưng
            luôn quay về quan hệ cân bằng dài hạn.
          - Số tổ hợp tuyến tính dừng = cointegration rank r.

    TẠI SAO rank r quan trọng:
        Rank r quyết định MÔ HÌNH nào được dùng ở Tầng 4:
          - 0 < r < n (có đồng tích hợp nhưng chưa full rank):
              → Dùng VECM (Vector Error Correction Model) — mô hình có
              thành phần hiệu chỉnh sai số (error correction term) nắm bắt
              quan hệ cân bằng dài hạn.
          - r = 0 (KHÔNG có đồng tích hợp):
              → Dùng VAR trên chuỗi ĐÃ SAI PHÂN (first differences).
          - r = n (full rank — tất cả biến đều dừng):
              → Dùng VAR trên chuỗi MỨC (levels) — không cần VECM.
        (ARCHITECTURE_4_tang.md, Tầng 4, Phase 5)

    Thủ tục tuần tự Johansen (sequential testing procedure):
        1. Bắt đầu với H0: r = 0 (không có đồng tích hợp).
        2. Nếu bác bỏ → chuyển sang H0: r ≤ 1.
        3. Tiếp tục cho đến khi KHÔNG bác bỏ được → r = số H0 cuối cùng
           không bị bác bỏ.
        Dùng CẢ HAI thống kê: Trace và Max-Eigenvalue, và so sánh kết quả.

    ĐIỀU KIỆN ÁP DỤNG:
        Johansen cointegration chỉ có ý nghĩa khi các biến là I(1) —
        tức không dừng ở mức (level) nhưng dừng sau sai phân bậc 1. Nếu
        tất cả biến đều I(0) (dừng sẵn), không cần kiểm tra đồng tích hợp
        → dùng VAR trên chuỗi mức luôn.

Input:  `data/processed/causal_weekly_dataset.csv` (Phase 0 output).
        `reports/phase1_stationarity.json` (d(i) từ Phase 1).
Output: `reports/phase3_cointegration.json` — chứa rank r, eigenvalues,
        trace/max-eigen statistics, và route VECM/VAR.

Sở hữu: Role B — Econometrics & Causality Analysis (skill.md).
Tuân thủ: CLAUDE.md mục 3.3 (đọc d(i) từ Phase 1), mục 5 (scientific integrity).
"""

import json
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd
from statsmodels.tsa.vector_ar.vecm import coint_johansen, VECM, select_coint_rank
from statsmodels.tsa.api import VAR

from scripts.utils import get_logger, get_base_dir

logger = get_logger("phase3")


# =====================================================================
# HẰNG SỐ CẤU HÌNH
# =====================================================================

SIGNIFICANCE_LEVEL = 0.05

ANALYSIS_VARS = ["ProductionVolume", "DelayRate", "OrderDemand"]

# Loại deterministic trend trong mô hình Johansen:
#   -1 = no deterministic terms
#    0 = constant (restricted to cointegrating space)
#    1 = constant (unrestricted) ← phù hợp nhất cho dữ liệu kinh tế
#                                   không có trend xác định
#    2 = constant + trend (restricted)
# Dùng det_order=1 (unrestricted constant): phù hợp khi dữ liệu có thể
# có mean khác 0 nhưng KHÔNG có trend tuyến tính xác định. Đây là lựa chọn
# phổ biến nhất cho dữ liệu kinh tế (Lütkepohl, 2005).
DET_ORDER = 1

# Số quan sát tối thiểu cho Johansen (cần đủ bậc tự do cho VAR nền tảng)
MIN_OBS_JOHANSEN = 12


# =====================================================================
# HÀM TIỆN ÍCH
# =====================================================================

def _safe_float(value):
    """Chuyển numpy scalar sang Python float cho JSON serialization."""
    if isinstance(value, (np.floating, np.integer)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def _load_phase1_results(base_dir):
    """Tải kết quả Phase 1 để đọc d(i)."""
    path = os.path.join(base_dir, "reports", "phase1_stationarity.json")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Không tìm thấy {path}. "
            f"Cần chạy Phase 1 (phase1_stationarity.py) trước."
        )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _check_applicability(d_values):
    """
    Kiểm tra điều kiện áp dụng Johansen cointegration.

    TẠI SAO chỉ áp dụng khi có biến I(1):
        Đồng tích hợp theo Johansen (1991) yêu cầu các biến phải CÙNG bậc
        tích hợp I(1). Nếu tất cả biến I(0) → đã dừng → không cần đồng
        tích hợp. Nếu có biến I(2) → cần xử lý đặc biệt (CI(2,1) theo
        Johansen 1995) — phức tạp hơn và hiếm gặp.

    Trong thực tế, nhiều nhà kinh tế lượng vẫn chạy Johansen khi các biến
    có bậc tích hợp KHÁC NHAU (mixed I(0) và I(1)), nhưng ghi rõ giới hạn.
    Pipeline này vẫn chạy kiểm định, kèm cảnh báo nếu không đủ biến I(1).
    """
    i1_vars = [var for var, d in d_values.items() if d == 1]
    i0_vars = [var for var, d in d_values.items() if d == 0]
    i2_vars = [var for var, d in d_values.items() if d >= 2]

    logger.info(
        f"Phân loại bậc tích hợp: "
        f"I(0)={i0_vars}, I(1)={i1_vars}, I(2+)={i2_vars}"
    )

    if not i1_vars:
        logger.warning(
            "KHÔNG có biến nào là I(1) — Johansen cointegration KHÔNG ÁP DỤNG. "
            "Tất cả biến đều I(0) → dùng VAR trên chuỗi mức (levels). "
            "Rank r sẽ được gán = n (full rank)."
        )
        return "all_stationary", i1_vars, i0_vars

    if len(i1_vars) < 2:
        logger.warning(
            f"Chỉ có {len(i1_vars)} biến I(1) ({i1_vars}) — Johansen cần "
            f"ÍT NHẤT 2 biến I(1) để kiểm tra đồng tích hợp. "
            f"Vẫn chạy nhưng kết quả hạn chế."
        )
        return "insufficient_i1", i1_vars, i0_vars

    if i2_vars:
        logger.warning(
            f"Có biến I(2+): {i2_vars}. Johansen tiêu chuẩn giả định I(1). "
            f"Vẫn chạy nhưng kết quả cần diễn giải thận trọng."
        )
        return "mixed_order", i1_vars, i0_vars

    return "applicable", i1_vars, i0_vars


def _select_lag_for_johansen(data, max_lag):
    """
    Chọn lag cho mô hình VAR nền tảng của Johansen.

    TẠI SAO cần chọn lag riêng cho Johansen:
        Johansen test dựa trên mô hình VECM/VAR nền. Nếu lag quá ít → phần
        dư có tự tương quan → thống kê trace/max-eigen bị sai lệch. Nếu lag
        quá nhiều → mất bậc tự do → power giảm. AIC/BIC giúp cân bằng.

    Lưu ý: lag trong VECM = lag_VAR - 1 (vì VECM đã sai phân 1 lần).
    """
    try:
        model = VAR(data)
        lag_result = model.select_order(maxlags=max_lag)

        aic_lag = lag_result.aic
        bic_lag = lag_result.bic

        # Dùng AIC, đảm bảo ít nhất 1
        selected = max(1, aic_lag)

        logger.info(
            f"Lag selection (VAR base): AIC={aic_lag}, BIC={bic_lag} → "
            f"dùng lag={selected} cho Johansen."
        )

        return selected, {
            "aic_lag": int(aic_lag),
            "bic_lag": int(bic_lag),
            "selected_lag": int(selected),
            "note": "Lag này là lag của VAR gốc; VECM dùng lag-1 = lag VAR-1"
        }

    except Exception as e:
        logger.warning(f"VAR lag selection thất bại ({e}). Dùng lag=1 mặc định.")
        return 1, {"selected_lag": 1, "error": str(e)}


# =====================================================================
# KIỂM ĐỊNH JOHANSEN
# =====================================================================

def _run_johansen_test(data, lag, var_names):
    """
    Chạy kiểm định đồng tích hợp Johansen theo thủ tục tuần tự.

    Sử dụng cả 2 thống kê:
        1. Trace statistic: kiểm tra H0: rank ≤ r vs H1: rank > r
           (kiểm tra "có NHIỀU HƠN r vector đồng tích hợp?")
        2. Max-eigenvalue statistic: kiểm tra H0: rank = r vs H1: rank = r+1
           (kiểm tra "có ĐÚNG r+1 vector thay vì r?")

    Thủ tục tuần tự (sequential testing):
        - Bắt đầu r = 0: nếu bác bỏ → tiếp tục.
        - r = 1: nếu bác bỏ → tiếp tục.
        - ...cho đến khi KHÔNG bác bỏ → r = giá trị đó.

    TẠI SAO dùng cả Trace lẫn Max-Eigenvalue:
        Khi 2 thống kê cho CÙNG rank → kết luận mạnh. Khi khác nhau →
        ưu tiên Trace (Johansen & Juselius 1990 khuyến nghị Trace ổn định
        hơn trong finite sample), nhưng ghi rõ cả 2 kết quả.

    Tham số:
        data: ndarray hoặc DataFrame — dữ liệu mức (levels), chưa sai phân.
              Johansen tự sai phân trong nội bộ.
        lag: int — lag của VAR gốc (VECM lag = lag - 1).
        var_names: list[str] — tên các biến (cho logging).
    """
    n_vars = data.shape[1]

    # coint_johansen yêu cầu k_ar_diff = lag_VAR - 1 (lag của VECM)
    k_ar_diff = max(0, lag - 1)

    logger.info(
        f"Chạy Johansen test: {n_vars} biến, k_ar_diff={k_ar_diff} "
        f"(lag VAR={lag}), det_order={DET_ORDER}."
    )

    try:
        result = coint_johansen(data, det_order=DET_ORDER, k_ar_diff=k_ar_diff)
    except Exception as e:
        logger.warning(f"Johansen test thất bại: {e}")
        return None

    # Trích xuất kết quả
    trace_stats = result.lr1        # Trace statistics
    max_eigen_stats = result.lr2    # Max-eigenvalue statistics
    eigenvalues = result.eig        # Eigenvalues
    trace_cvs = result.cvt          # Critical values (trace) — [90%, 95%, 99%]
    max_cvs = result.cvm            # Critical values (max-eigen)

    # Thủ tục tuần tự cho Trace statistic
    trace_rank = n_vars  # mặc định full rank
    trace_details = []

    for r in range(n_vars):
        stat = _safe_float(trace_stats[r])
        # Cột 1 = critical value 95% (index 1 trong cvt)
        cv_95 = _safe_float(trace_cvs[r, 1])
        cv_90 = _safe_float(trace_cvs[r, 0])
        cv_99 = _safe_float(trace_cvs[r, 2])
        reject = stat > cv_95

        detail = {
            "h0": f"r ≤ {r}",
            "statistic": stat,
            "critical_values": {"90%": cv_90, "95%": cv_95, "99%": cv_99},
            "reject_h0_at_5pct": reject
        }
        trace_details.append(detail)

        logger.info(
            f"  Trace H0: r≤{r}: stat={stat:.4f} vs cv_95={cv_95:.4f} "
            f"→ {'BÁC BỎ' if reject else 'GIỮ'} H0"
        )

        if not reject:
            trace_rank = r
            break

    # Thủ tục tuần tự cho Max-Eigenvalue statistic
    max_eigen_rank = n_vars
    max_eigen_details = []

    for r in range(n_vars):
        stat = _safe_float(max_eigen_stats[r])
        cv_95 = _safe_float(max_cvs[r, 1])
        cv_90 = _safe_float(max_cvs[r, 0])
        cv_99 = _safe_float(max_cvs[r, 2])
        reject = stat > cv_95

        detail = {
            "h0": f"r = {r}",
            "statistic": stat,
            "critical_values": {"90%": cv_90, "95%": cv_95, "99%": cv_99},
            "reject_h0_at_5pct": reject
        }
        max_eigen_details.append(detail)

        logger.info(
            f"  Max-eigen H0: r={r}: stat={stat:.4f} vs cv_95={cv_95:.4f} "
            f"→ {'BÁC BỎ' if reject else 'GIỮ'} H0"
        )

        if not reject:
            max_eigen_rank = r
            break

    # Quyết định rank cuối cùng
    # Ưu tiên Trace nếu 2 thống kê mâu thuẫn (Johansen & Juselius 1990)
    if trace_rank == max_eigen_rank:
        final_rank = trace_rank
        rank_agreement = "consistent"
        logger.info(
            f"Trace và Max-Eigenvalue ĐỒNG THUẬN: rank r = {final_rank}."
        )
    else:
        final_rank = trace_rank
        rank_agreement = "inconsistent"
        logger.warning(
            f"Trace (r={trace_rank}) và Max-Eigenvalue (r={max_eigen_rank}) "
            f"KHÔNG ĐỒNG THUẬN. Ưu tiên Trace → rank r = {final_rank} "
            f"(Johansen & Juselius 1990 khuyến nghị Trace ổn định hơn "
            f"trong finite sample)."
        )

    # Xác định route VECM/VAR
    if final_rank == 0:
        route = "VAR_on_differences"
        route_explanation = (
            "r = 0 (không đồng tích hợp): không có quan hệ cân bằng dài hạn "
            "→ dùng VAR trên chuỗi ĐÃ SAI PHÂN."
        )
    elif final_rank == n_vars:
        route = "VAR_on_levels"
        route_explanation = (
            f"r = {n_vars} (full rank): tất cả biến dừng ở mức → "
            f"dùng VAR trên chuỗi MỨC (levels)."
        )
    else:
        route = "VECM"
        route_explanation = (
            f"0 < r = {final_rank} < n = {n_vars}: có {final_rank} vector "
            f"đồng tích hợp → dùng VECM (Vector Error Correction Model) "
            f"với {final_rank} error correction term(s)."
        )

    logger.info(f"Route đề xuất: {route}")
    logger.info(f"  {route_explanation}")

    return {
        "trace_test": {
            "rank": trace_rank,
            "details": trace_details
        },
        "max_eigenvalue_test": {
            "rank": max_eigen_rank,
            "details": max_eigen_details
        },
        "eigenvalues": [_safe_float(e) for e in eigenvalues],
        "rank_agreement": rank_agreement,
        "coint_rank": final_rank,
        "n_variables": n_vars,
        "variable_names": var_names,
        "route": route,
        "route_explanation": route_explanation,
        "det_order": DET_ORDER,
        "k_ar_diff": k_ar_diff
    }


# =====================================================================
# PHÂN TÍCH ĐỘ NHẠY
# =====================================================================

def _run_sensitivity_analysis(df, lag, var_names, full_result):
    """
    Loại tuần forward-fill, chạy lại Johansen, so sánh rank.

    Nếu rank thay đổi → route VECM/VAR cũng thay đổi → kết luận kinh tế
    lượng (có/không có quan hệ dài hạn) PHỤ THUỘC vào bước forward-fill.
    """
    interp_cols = [c for c in df.columns if c.startswith("is_filled")]
    if not interp_cols:
        return None

    any_interpolated = df[interp_cols].any(axis=1)
    n_excluded = int(any_interpolated.sum())

    if n_excluded == 0:
        return {
            "description": "Không có tuần forward-fill — kết quả giống hoàn toàn.",
            "discrepancies": []
        }

    df_clean = df.loc[~any_interpolated].copy()

    logger.info(
        f"\n--- SENSITIVITY: loại {n_excluded} tuần forward-fill, "
        f"còn {len(df_clean)} tuần ---"
    )

    if len(df_clean) < MIN_OBS_JOHANSEN:
        logger.warning(
            f"Sensitivity: chỉ còn {len(df_clean)} tuần "
            f"(< {MIN_OBS_JOHANSEN} tối thiểu). Bỏ qua."
        )
        return {
            "description": "Không đủ dữ liệu sạch cho Johansen sensitivity.",
            "n_observations_clean": len(df_clean),
            "discrepancies": []
        }

    clean_data = df_clean[var_names].values
    clean_lag = min(lag, max(1, len(df_clean) // 4))

    clean_result = _run_johansen_test(clean_data, clean_lag, var_names)

    discrepancies = []
    if clean_result is not None and full_result is not None:
        full_rank = full_result["coint_rank"]
        clean_rank = clean_result["coint_rank"]

        if full_rank != clean_rank:
            discrepancy = {
                "full_rank": full_rank,
                "clean_rank": clean_rank,
                "full_route": full_result["route"],
                "clean_route": clean_result["route"],
                "warning": (
                    f"Rank thay đổi từ {full_rank} (đầy đủ) sang "
                    f"{clean_rank} (loại forward-fill) → route cũng thay đổi: "
                    f"{full_result['route']} → {clean_result['route']}. "
                    f"Kết luận CÓ THỂ PHỤ THUỘC vào bước forward-fill."
                )
            }
            discrepancies.append(discrepancy)
            logger.warning(
                f"⚠ SENSITIVITY: rank thay đổi {full_rank} → {clean_rank}!"
            )
        else:
            logger.info(
                f"Sensitivity: rank KHÔNG thay đổi (r={full_rank}) — robust."
            )

    return {
        "description": "So sánh Johansen rank giữa dataset đầy đủ và dataset loại tuần forward-fill.",
        "n_observations_clean": len(df_clean),
        "clean_result": clean_result,
        "discrepancies": discrepancies
    }


# =====================================================================
# HÀM CHÍNH — ĐIỀU PHỐI PHASE 3
# =====================================================================

def run_phase3(input_path=None):
    """
    Hàm chính điều phối Phase 3: Kiểm định đồng tích hợp Johansen.

    Quy trình:
        1. Tải dataset + d(i) từ Phase 1.
        2. Kiểm tra điều kiện áp dụng (cần ít nhất 2 biến I(1)).
        3. Chọn lag cho VAR nền tảng.
        4. Chạy Johansen test (Trace + Max-Eigenvalue).
        5. Xác định rank r → route VECM/VAR.
        6. Phân tích độ nhạy.
        7. Lưu JSON.
    """
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("PHASE 3 — KIỂM ĐỊNH ĐỒNG TÍCH HỢP JOHANSEN (COINTEGRATION)")
    logger.info("=" * 60)

    base_dir = get_base_dir()

    # -----------------------------------------------------------------
    # Bước 1: Tải dữ liệu đầu vào
    # -----------------------------------------------------------------
    if input_path is None:
        input_path = os.path.join(
            base_dir, "data", "processed", "causal_weekly_dataset.csv"
        )

    if not os.path.exists(input_path):
        raise FileNotFoundError(
            f"Không tìm thấy dataset tại {input_path}. Cần chạy Phase 0 trước."
        )

    df = pd.read_csv(input_path).copy()
    df["week_start"] = pd.to_datetime(df["week_start"])
    logger.info(f"Đã tải dataset: {len(df)} tuần.")

    phase1 = _load_phase1_results(base_dir)
    d_values = phase1.get("d_values", {})
    d_max = phase1.get("d_max", 0)
    logger.info(f"Bậc tích hợp từ Phase 1: {d_values}, d_max={d_max}")

    # -----------------------------------------------------------------
    # Bước 2: Kiểm tra điều kiện áp dụng
    # -----------------------------------------------------------------
    applicability, i1_vars, i0_vars = _check_applicability(d_values)

    # Xác định biến nào đưa vào Johansen test
    # Sử dụng TẤT CẢ biến phân tích (kể cả I(0)) — Johansen xử lý được
    # mixed order trong thực tế, và kết quả r=n_vars cho biến I(0) là
    # mong đợi (trivially cointegrated).
    johansen_vars = [v for v in ANALYSIS_VARS if v in df.columns]

    johansen_result = None
    lag_info = None
    route = None

    if applicability == "all_stationary":
        # Tất cả biến I(0) → không cần đồng tích hợp
        n_vars = len(johansen_vars)
        johansen_result = {
            "coint_rank": n_vars,
            "n_variables": n_vars,
            "variable_names": johansen_vars,
            "route": "VAR_on_levels",
            "route_explanation": (
                f"Tất cả {n_vars} biến đều I(0) (dừng) → full rank → "
                f"dùng VAR trên chuỗi mức. Johansen test KHÔNG cần thiết."
            ),
            "skipped": True,
            "skip_reason": "all_stationary"
        }
        logger.info(f"Route: VAR_on_levels (tất cả biến dừng, r = {n_vars})")

    else:
        # Có biến I(1) → chạy Johansen
        data = df[johansen_vars].dropna()

        if len(data) < MIN_OBS_JOHANSEN:
            logger.warning(
                f"Chỉ có {len(data)} quan sát (< {MIN_OBS_JOHANSEN} tối thiểu "
                f"cho Johansen). Vẫn chạy nhưng kết quả CẦN THẬN TRỌNG."
            )

        # Chọn lag
        max_lag = max(1, len(data) // 4)
        lag, lag_info = _select_lag_for_johansen(data.values, max_lag)

        # Chạy Johansen
        johansen_result = _run_johansen_test(data.values, lag, johansen_vars)

        if johansen_result is None:
            logger.warning(
                "Johansen test thất bại. Gán mặc định: r=0 → VAR_on_differences."
            )
            johansen_result = {
                "coint_rank": 0,
                "n_variables": len(johansen_vars),
                "variable_names": johansen_vars,
                "route": "VAR_on_differences",
                "route_explanation": "Johansen test thất bại → mặc định VAR trên sai phân.",
                "skipped": False,
                "test_failed": True
            }

    # -----------------------------------------------------------------
    # Bước 3: Phân tích độ nhạy
    # -----------------------------------------------------------------
    logger.info("\n--- PHÂN TÍCH ĐỘ NHẠY ---")
    sensitivity = None
    if not johansen_result.get("skipped", False):
        lag_for_sensitivity = lag_info["selected_lag"] if lag_info else 1
        sensitivity = _run_sensitivity_analysis(
            df, lag_for_sensitivity, johansen_vars, johansen_result
        )

    # -----------------------------------------------------------------
    # Bước 4: Tóm tắt điểm dừng xác nhận (ARCHITECTURE_4_tang.md)
    # -----------------------------------------------------------------
    coint_rank = johansen_result["coint_rank"]
    route = johansen_result["route"]

    logger.info("=" * 60)
    logger.info("TÓM TẮT PHASE 3 (cho điểm dừng xác nhận):")
    logger.info(f"  - Cointegration rank r = {coint_rank}")
    logger.info(f"  - Số biến n = {len(johansen_vars)}")
    logger.info(f"  - Route đề xuất: {route}")
    logger.info(f"  - {johansen_result.get('route_explanation', '')}")
    if sensitivity and sensitivity.get("discrepancies"):
        logger.warning("  - ⚠ CÓ thay đổi khi loại tuần forward-fill — xem sensitivity analysis!")
    logger.info("=" * 60)

    # -----------------------------------------------------------------
    # Bước 5: Ghi JSON
    # -----------------------------------------------------------------
    output = {
        "metadata": {
            "script": "phase3_cointegration.py",
            "timestamp": datetime.now().isoformat(),
            "input_file": "data/processed/causal_weekly_dataset.csv",
            "phase1_file": "reports/phase1_stationarity.json",
            "n_observations": len(df),
            "significance_level": SIGNIFICANCE_LEVEL,
            "d_values_from_phase1": d_values,
            "d_max": d_max,
            "method": "Johansen cointegration (Trace + Max-Eigenvalue)",
            "det_order": DET_ORDER,
            "det_order_description": "Unrestricted constant (no trend) — Lütkepohl 2005",
            "applicability": applicability
        },
        "lag_selection": lag_info,
        "johansen_result": johansen_result,
        "coint_rank": coint_rank,
        "route": route,
        "route_explanation": johansen_result.get("route_explanation", ""),
        "sensitivity_analysis": sensitivity
    }

    output_dir = os.path.join(base_dir, "reports")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "phase3_cointegration.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    logger.info(f"Kết quả Phase 3 đã lưu: {output_path}")

    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info(f"Phase 3 hoàn tất trong {elapsed:.1f}s.")

    return output_path


# =====================================================================
# ENTRY POINT
# =====================================================================
if __name__ == "__main__":
    try:
        output = run_phase3()
        logger.info(f"Kết quả lưu tại: {output}")
    except Exception:
        logger.exception("Phase 3 thất bại — xem traceback ở trên.")
        sys.exit(1)
