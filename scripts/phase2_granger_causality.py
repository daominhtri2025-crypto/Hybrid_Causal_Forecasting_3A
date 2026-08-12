"""
Tầng 3 — Phase 2: Kiểm định nhân quả Granger (Granger Causality Testing).

Mục đích:
    Kiểm tra quan hệ nhân quả Granger (Granger, 1969) giữa các cặp biến
    trong hệ thống: ProductionVolume, DelayRate, OrderDemand.

    Nhân quả Granger KHÔNG phải nhân quả thực sự (true causation) — nó chỉ
    kiểm tra xem biến X có giúp DỰ BÁO biến Y tốt hơn hay không, khi đã
    biết quá khứ của chính Y. Cụ thể:
        H0: X KHÔNG Granger-cause Y (các hệ số lag của X trong phương trình
            Y đều bằng 0).
        H1: X Granger-cause Y (ít nhất 1 hệ số lag của X khác 0).
        → Bác bỏ H0 (p < α) ⟹ X có khả năng dự báo Y vượt trên thông tin
          từ quá khứ của chính Y.

    ĐIỀU KIỆN TIÊN QUYẾT: Granger causality yêu cầu các chuỗi phải DỪNG
    (stationary). Nếu chạy trên chuỗi không dừng, kiểm định F có thể cho
    kết quả giả (spurious regression, Granger & Newbold, 1974). Do đó:
    → Đọc d(i) từ Phase 1 → sai phân từng biến theo đúng bậc d(i) trước
    khi chạy Granger.

    TẠI SAO cần Granger bên cạnh Toda-Yamamoto (Phase 3b):
        - Granger trên chuỗi đã sai phân: kiểm định "chuẩn", dễ hiểu,
          được trích dẫn phổ biến nhất trong nghiên cứu thực nghiệm.
        - Toda-Yamamoto trên chuỗi mức: không cần pre-testing d(i) →
          ít nhạy cảm hơn với sai sót ở bước xác định d.
        - Hai phương pháp ĐỘC LẬP đối chiếu chéo: nếu cả hai đồng thuận
          → kết luận mạnh; nếu mâu thuẫn → cần thận trọng khi diễn giải
          (ARCHITECTURE_4_tang.md, Tầng 3).

Input:  `data/processed/causal_weekly_dataset.csv` (Phase 0 output).
        `reports/phase1_stationarity.json` (d(i) từ Phase 1).
Output: `reports/phase2_granger_causality.json`.

Sở hữu: Role B — Econometrics & Causality Analysis (skill.md).
Tuân thủ: CLAUDE.md mục 3.3 (đọc d(i) từ Phase 1, không hard-code),
          mục 7 (logging).
"""

import json
import os
import sys
from datetime import datetime
from itertools import permutations

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import grangercausalitytests
from statsmodels.tsa.api import VAR

from scripts.utils import get_logger, get_base_dir

logger = get_logger("phase2")


# =====================================================================
# HẰNG SỐ CẤU HÌNH
# =====================================================================

SIGNIFICANCE_LEVEL = 0.05

ANALYSIS_VARS = ["ProductionVolume", "DelayRate", "OrderDemand"]

# Số lag tối đa để kiểm tra trong Granger test.
# TẠI SAO maxlag là hàm của kích thước mẫu:
#   Quá nhiều lag → ít bậc tự do → power thấp, F-test không đáng tin.
#   Quá ít lag → bỏ sót quan hệ nhân quả có độ trễ dài.
#   Quy tắc thực tiễn: maxlag ≤ T/3 (để giữ ít nhất 2/3 dữ liệu cho ước lượng).
MAX_LAG_RATIO = 3  # maxlag = max(1, T // MAX_LAG_RATIO)

# Số quan sát tối thiểu (sau sai phân) để Granger test có ý nghĩa
MIN_OBS_GRANGER = 10


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
    """
    Tải kết quả Phase 1 — bắt buộc để biết d(i) từng biến.

    Theo CLAUDE.md mục 3.3: mọi tham số phụ thuộc kết quả thống kê phải
    được ĐỌC từ file JSON, KHÔNG hard-code hay giả định.

    Raises:
        FileNotFoundError nếu Phase 1 chưa chạy.
    """
    path = os.path.join(base_dir, "reports", "phase1_stationarity.json")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Không tìm thấy {path}. "
            f"Cần chạy Phase 1 (phase1_stationarity.py) trước để xác định "
            f"bậc tích hợp d(i) cho từng biến."
        )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _difference_series(df, d_values):
    """
    Sai phân từng biến theo đúng bậc d(i) từ Phase 1.

    TẠI SAO sai phân riêng theo d(i) của từng biến (thay vì chung 1 bậc):
        Các biến kinh tế có thể có bậc tích hợp KHÁC NHAU (vd: OrderDemand là
        I(1) nhưng DelayRate là I(0)). Nếu sai phân tất cả cùng 1 bậc:
        - Biến I(0) bị sai phân thừa (overdifferencing) → thêm nhiễu,
          mất thông tin tần số thấp.
        - Biến I(1) nếu không sai phân → chuỗi không dừng → Granger test
          cho kết quả giả.

    Tham số:
        df: DataFrame chứa các biến gốc (chưa sai phân).
        d_values: dict {var_name: d(i)} từ Phase 1.

    Trả về:
        DataFrame với các biến đã sai phân theo d(i), đã dropna.
    """
    df_diff = pd.DataFrame(index=df.index)

    for var in ANALYSIS_VARS:
        if var not in df.columns:
            continue

        d = d_values.get(var, 0)
        series = df[var].copy()

        if d == 0:
            # I(0): biến đã dừng → không cần sai phân
            df_diff[var] = series
            logger.info(f"{var}: d=0 (I(0)) → giữ nguyên chuỗi gốc.")
        else:
            # I(d): sai phân d lần
            for _ in range(d):
                series = series.diff()
            df_diff[var] = series
            logger.info(f"{var}: d={d} (I({d})) → đã sai phân {d} lần.")

    # Loại NaN sinh ra từ sai phân
    df_diff = df_diff.dropna()
    logger.info(
        f"Sau sai phân và loại NaN: còn {len(df_diff)} quan sát "
        f"(mất {len(df) - len(df_diff)} do sai phân)."
    )

    return df_diff


def _select_optimal_lag(df_diff, max_lag):
    """
    Chọn lag tối ưu cho mô hình VAR bằng information criteria.

    TẠI SAO dùng AIC (Akaike Information Criterion):
        AIC cân bằng giữa goodness-of-fit và độ phức tạp (số tham số).
        So với BIC (thiên về mô hình đơn giản hơn), AIC ít bỏ sót quan hệ
        nhân quả có lag dài hơn → phù hợp cho mục đích tìm quan hệ nhân quả
        (muốn tránh bỏ sót hơn là tránh dương tính giả).

    Nếu VAR lag selection thất bại (mẫu quá nhỏ), mặc định dùng lag = 1.
    """
    try:
        model = VAR(df_diff)
        lag_result = model.select_order(maxlags=max_lag)

        # Ưu tiên AIC, fallback sang BIC nếu AIC cho lag = 0
        aic_lag = lag_result.aic
        bic_lag = lag_result.bic

        optimal_lag = aic_lag if aic_lag > 0 else (bic_lag if bic_lag > 0 else 1)

        logger.info(
            f"Lag selection: AIC={aic_lag}, BIC={bic_lag} → dùng lag={optimal_lag}."
        )

        return optimal_lag, {
            "aic_lag": int(aic_lag),
            "bic_lag": int(bic_lag),
            "selected_lag": int(optimal_lag),
            "criterion_used": "AIC" if optimal_lag == aic_lag else "BIC"
        }

    except Exception as e:
        logger.warning(
            f"VAR lag selection thất bại ({e}). Dùng lag=1 mặc định."
        )
        return 1, {
            "selected_lag": 1,
            "criterion_used": "default (lag selection failed)",
            "error": str(e)
        }


# =====================================================================
# KIỂM ĐỊNH GRANGER CAUSALITY THEO CẶP
# =====================================================================

def _run_pairwise_granger(df_diff, max_lag):
    """
    Chạy kiểm định Granger causality cho MỌI cặp biến (theo cả 2 chiều).

    Với n biến, có n*(n-1) cặp có hướng (X→Y khác Y→X). Ví dụ:
        - OrderDemand → ProductionVolume: "Nhu cầu đơn hàng có giúp dự báo sản lượng?"
        - ProductionVolume → DelayRate: "Sản lượng có giúp dự báo tỷ lệ trễ?"
    Hai câu hỏi này ĐỘC LẬP — nhân quả Granger KHÔNG đối xứng.

    statsmodels.grangercausalitytests:
        - Input: DataFrame 2 cột [y, x] — kiểm tra "x Granger-cause y?"
        - Trả về dict {lag: (F_test, chi2_test, ...)} cho từng lag từ 1 đến maxlag.
        - Dùng F-test (ssr_ftest) vì mẫu nhỏ → F-distribution chính xác hơn
          chi-square asymptotic.

    Trả về:
        list[dict] — kết quả từng cặp kèm thống kê chi tiết.
    """
    available_vars = [v for v in ANALYSIS_VARS if v in df_diff.columns]
    results = []

    for cause_var, effect_var in permutations(available_vars, 2):
        pair_label = f"{cause_var} → {effect_var}"
        logger.info(f"\nKiểm định Granger: {pair_label}")

        try:
            # grangercausalitytests yêu cầu DataFrame [y, x]
            # trong đó kiểm tra "x Granger-causes y?"
            test_data = df_diff[[effect_var, cause_var]].copy()

            # Kiểm tra đủ dữ liệu cho số lag yêu cầu
            effective_max_lag = min(max_lag, len(test_data) // 3)
            if effective_max_lag < 1:
                logger.warning(
                    f"  {pair_label}: không đủ dữ liệu cho bất kỳ lag nào "
                    f"(chỉ có {len(test_data)} quan sát). Bỏ qua."
                )
                results.append({
                    "cause": cause_var,
                    "effect": effect_var,
                    "skipped": True,
                    "reason": f"Không đủ dữ liệu ({len(test_data)} quan sát)"
                })
                continue

            # Chạy Granger test — verbose=False vì ta tự logging
            test_output = grangercausalitytests(
                test_data, maxlag=effective_max_lag, verbose=False
            )

            # Thu thập kết quả theo từng lag
            lag_results = {}
            best_lag = None
            best_p = 1.0

            for lag in range(1, effective_max_lag + 1):
                if lag not in test_output:
                    continue

                # test_output[lag] = (dict_of_tests, ...)
                tests_dict = test_output[lag][0]

                # Dùng F-test (ssr_ftest) — chính xác hơn chi2 cho mẫu nhỏ
                f_stat, f_p_value, df_denom, df_num = tests_dict["ssr_ftest"]

                lag_results[str(lag)] = {
                    "f_statistic": _safe_float(f_stat),
                    "p_value": _safe_float(f_p_value),
                    "df_numerator": int(df_num),
                    "df_denominator": int(df_denom),
                    "significant": bool(float(f_p_value) < SIGNIFICANCE_LEVEL)
                }

                if float(f_p_value) < best_p:
                    best_p = float(f_p_value)
                    best_lag = lag

            # Kết luận tổng hợp: X Granger-cause Y nếu có BẤT KỲ lag nào
            # cho p < α. Dùng lag có p nhỏ nhất để báo cáo.
            # bool() đảm bảo chuyển numpy.bool_ → Python bool cho JSON
            is_significant = bool(best_p < SIGNIFICANCE_LEVEL)

            if is_significant:
                logger.info(
                    f"  ✓ {pair_label}: CÓ Ý NGHĨA tại lag={best_lag} "
                    f"(p={best_p:.4f} < α={SIGNIFICANCE_LEVEL})"
                )
            else:
                logger.info(
                    f"  ✗ {pair_label}: KHÔNG có ý nghĩa "
                    f"(p_min={best_p:.4f} tại lag={best_lag})"
                )

            results.append({
                "cause": cause_var,
                "effect": effect_var,
                "skipped": False,
                "lag_results": lag_results,
                "best_lag": best_lag,
                "best_p_value": _safe_float(best_p),
                "significant": is_significant,
                "conclusion": (
                    f"{cause_var} Granger-cause {effect_var} "
                    f"tại lag={best_lag} (p={best_p:.4f})"
                    if is_significant
                    else f"{cause_var} KHÔNG Granger-cause {effect_var} "
                         f"(p_min={best_p:.4f})"
                )
            })

        except Exception as e:
            logger.warning(
                f"  {pair_label}: kiểm định thất bại — {e}"
            )
            results.append({
                "cause": cause_var,
                "effect": effect_var,
                "skipped": True,
                "reason": str(e)
            })

    return results


# =====================================================================
# PHÂN TÍCH ĐỘ NHẠY
# =====================================================================

def _run_sensitivity_analysis(df, d_values, max_lag, full_results):
    """
    Loại tuần forward-fill, chạy lại Granger, so sánh với kết quả đầy đủ.

    So sánh dựa trên: cặp nào CÓ ý nghĩa (significant) thay đổi giữa
    2 lần chạy (đầy đủ vs. sạch) → đó là cặp mà kết luận nhân quả PHỤ
    THUỘC vào bước forward-fill ở Phase 0.
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
    n_clean = len(df_clean)

    logger.info(
        f"\n--- SENSITIVITY: loại {n_excluded} tuần forward-fill, còn {n_clean} tuần ---"
    )

    # Sai phân dataset sạch
    df_clean_diff = _difference_series(df_clean, d_values)

    if len(df_clean_diff) < MIN_OBS_GRANGER:
        logger.warning(
            f"Sensitivity: chỉ còn {len(df_clean_diff)} quan sát sau sai phân "
            f"(< {MIN_OBS_GRANGER} tối thiểu). Bỏ qua sensitivity Granger."
        )
        return {
            "description": "Không đủ dữ liệu sạch để chạy sensitivity analysis.",
            "n_observations_clean": n_clean,
            "n_after_diff": len(df_clean_diff),
            "discrepancies": []
        }

    # Chạy lại Granger trên dataset sạch
    clean_max_lag = max(1, len(df_clean_diff) // MAX_LAG_RATIO)
    clean_results = _run_pairwise_granger(df_clean_diff, clean_max_lag)

    # So sánh kết luận significant giữa full và clean
    discrepancies = []
    full_pairs = {
        (r["cause"], r["effect"]): r.get("significant", None)
        for r in full_results if not r.get("skipped", True)
    }
    clean_pairs = {
        (r["cause"], r["effect"]): r.get("significant", None)
        for r in clean_results if not r.get("skipped", True)
    }

    for pair, full_sig in full_pairs.items():
        clean_sig = clean_pairs.get(pair)
        if clean_sig is not None and full_sig != clean_sig:
            discrepancies.append({
                "pair": f"{pair[0]} → {pair[1]}",
                "full_significant": full_sig,
                "clean_significant": clean_sig,
                "warning": (
                    f"Kết luận nhân quả {pair[0]}→{pair[1]} THAY ĐỔI "
                    f"khi loại tuần forward-fill: "
                    f"{'có' if full_sig else 'không'} → "
                    f"{'có' if clean_sig else 'không'} ý nghĩa."
                )
            })
            logger.warning(
                f"⚠ SENSITIVITY: {pair[0]}→{pair[1]} thay đổi kết luận!"
            )

    if not discrepancies:
        logger.info("Sensitivity: kết luận Granger KHÔNG thay đổi — robust.")

    return {
        "description": "So sánh Granger giữa dataset đầy đủ và dataset loại tuần forward-fill.",
        "n_observations_clean": n_clean,
        "n_after_diff": len(df_clean_diff),
        "clean_results": clean_results,
        "discrepancies": discrepancies
    }


# =====================================================================
# HÀM CHÍNH — ĐIỀU PHỐI PHASE 2
# =====================================================================

def run_phase2(input_path=None):
    """
    Hàm chính điều phối Phase 2: Kiểm định nhân quả Granger.

    Quy trình:
        1. Tải dataset tuần + d(i) từ Phase 1.
        2. Sai phân từng biến theo d(i) → đảm bảo chuỗi dừng.
        3. Chọn lag tối ưu (AIC).
        4. Chạy Granger pairwise cho mọi cặp.
        5. Phân tích độ nhạy.
        6. Lưu JSON.
    """
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("PHASE 2 — KIỂM ĐỊNH NHÂN QUẢ GRANGER (GRANGER CAUSALITY)")
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
            f"Không tìm thấy dataset tại {input_path}. "
            f"Cần chạy Phase 0 trước."
        )

    df = pd.read_csv(input_path).copy()
    df["week_start"] = pd.to_datetime(df["week_start"])
    logger.info(f"Đã tải dataset: {len(df)} tuần.")

    # Tải d(i) từ Phase 1 — KHÔNG hard-code (CLAUDE.md mục 3.3)
    phase1 = _load_phase1_results(base_dir)
    d_values = phase1.get("d_values", {})
    logger.info(f"Bậc tích hợp từ Phase 1: {d_values}")

    # -----------------------------------------------------------------
    # Bước 2: Sai phân theo d(i) → đảm bảo chuỗi dừng
    # -----------------------------------------------------------------
    df_diff = _difference_series(df[ANALYSIS_VARS].copy(), d_values)

    if len(df_diff) < MIN_OBS_GRANGER:
        logger.warning(
            f"Chỉ còn {len(df_diff)} quan sát sau sai phân "
            f"(< {MIN_OBS_GRANGER} tối thiểu). Granger test có power rất thấp."
        )

    # -----------------------------------------------------------------
    # Bước 3: Chọn lag tối ưu
    # -----------------------------------------------------------------
    max_lag = max(1, len(df_diff) // MAX_LAG_RATIO)
    logger.info(f"Max lag cho Granger test: {max_lag} (T={len(df_diff)}, ratio=T/{MAX_LAG_RATIO})")

    optimal_lag, lag_info = _select_optimal_lag(df_diff, max_lag)

    # -----------------------------------------------------------------
    # Bước 4: Chạy Granger pairwise
    # -----------------------------------------------------------------
    logger.info("\n--- KIỂM ĐỊNH GRANGER PAIRWISE ---")
    pairwise_results = _run_pairwise_granger(df_diff, optimal_lag)

    # Tóm tắt
    significant_pairs = [
        r for r in pairwise_results
        if not r.get("skipped", True) and r.get("significant", False)
    ]
    logger.info("-" * 40)
    logger.info(f"TÓM TẮT: {len(significant_pairs)} cặp có ý nghĩa Granger "
                f"trên tổng {len(pairwise_results)} cặp kiểm định.")
    for p in significant_pairs:
        logger.info(f"  ✓ {p['cause']} → {p['effect']} (p={p['best_p_value']:.4f})")
    logger.info("-" * 40)

    # -----------------------------------------------------------------
    # Bước 5: Phân tích độ nhạy
    # -----------------------------------------------------------------
    logger.info("\n--- PHÂN TÍCH ĐỘ NHẠY ---")
    sensitivity = _run_sensitivity_analysis(df, d_values, max_lag, pairwise_results)

    # -----------------------------------------------------------------
    # Bước 6: Ghi JSON
    # -----------------------------------------------------------------
    output = {
        "metadata": {
            "script": "phase2_granger_causality.py",
            "timestamp": datetime.now().isoformat(),
            "input_file": "data/processed/causal_weekly_dataset.csv",
            "phase1_file": "reports/phase1_stationarity.json",
            "n_observations_raw": len(df),
            "n_observations_after_diff": len(df_diff),
            "significance_level": SIGNIFICANCE_LEVEL,
            "d_values_from_phase1": d_values,
            "method": "Granger causality (F-test) on differenced series"
        },
        "lag_selection": lag_info,
        "pairwise_results": pairwise_results,
        "summary": {
            "total_pairs_tested": len([r for r in pairwise_results if not r.get("skipped")]),
            "significant_pairs": len(significant_pairs),
            "significant_list": [
                f"{p['cause']} → {p['effect']}" for p in significant_pairs
            ]
        },
        "sensitivity_analysis": sensitivity
    }

    output_dir = os.path.join(base_dir, "reports")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "phase2_granger_causality.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    logger.info(f"Kết quả Phase 2 đã lưu: {output_path}")

    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info(f"Phase 2 hoàn tất trong {elapsed:.1f}s.")

    return output_path


# =====================================================================
# ENTRY POINT
# =====================================================================
if __name__ == "__main__":
    try:
        output = run_phase2()
        logger.info(f"Kết quả lưu tại: {output}")
    except Exception:
        logger.exception("Phase 2 thất bại — xem traceback ở trên.")
        sys.exit(1)
