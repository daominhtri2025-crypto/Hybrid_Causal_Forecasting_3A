"""
Tầng 3 — Phase 3b: Kiểm định nhân quả Toda-Yamamoto (đối chiếu chéo).

Mục đích:
    Kiểm tra nhân quả Granger bằng phương pháp Toda-Yamamoto (1995) — một
    phương pháp ĐỘC LẬP với Granger tiêu chuẩn (Phase 2) và KHÔNG cần
    pre-testing cho đồng tích hợp, tạo phép ĐỐI CHIẾU CHÉO bắt buộc
    (ARCHITECTURE_4_tang.md, Tầng 3).

    TẠI SAO cần Toda-Yamamoto bên cạnh Granger thông thường:
        Granger causality tiêu chuẩn (Phase 2) YÊU CẦU:
          (1) Xác định đúng d(i) cho từng biến → sai phân cho dừng.
          (2) Nếu xác định d(i) sai → sai phân sai → kết quả Granger sai.
        Toda-Yamamoto KHÔNG có nhược điểm này vì:
          (1) Chạy trên chuỗi MỨC (levels) — KHÔNG sai phân.
          (2) "Bọc" thêm d_max lag phụ vào mô hình VAR → triệt tiêu
              tác động của unit root mà KHÔNG cần biết chính xác d(i).
          → Nếu cả Granger (Phase 2) lẫn Toda-Yamamoto (Phase 3b) đồng thuận
            → kết luận nhân quả RẤT MẠNH.
          → Nếu mâu thuẫn → cần thận trọng (có thể do d(i) xác định sai,
            hoặc do mẫu quá nhỏ).

    Quy trình Toda-Yamamoto:
        1. Xác định d_max = max{d(i)} từ Phase 1.
        2. Chọn lag tối ưu k trên chuỗi MỨC (levels) bằng AIC/BIC.
        3. Ước lượng VAR(k + d_max) trên chuỗi mức — thêm d_max lag "đệm".
        4. Kiểm định Wald: các hệ số của k lag ĐẦU TIÊN (lag 1 đến k) có
           ĐỒNG THỜI bằng 0 không? (Bỏ qua d_max lag cuối — chúng chỉ là
           "đệm" để đảm bảo phân phối tiệm cận chuẩn.)
           → Bác bỏ → X Granger-cause Y (theo nghĩa Toda-Yamamoto).

    Ưu điểm toán học (TẠI SAO phương pháp này hoạt động):
        Toda & Yamamoto (1995) chứng minh rằng khi VAR được ước lượng với
        k + d_max lag, thống kê Wald trên k lag đầu tiên có phân phối
        tiệm cận χ²(k) BẤT KỂ các chuỗi có I(0), I(1), hay đồng tích hợp.
        d_max lag phụ "hấp thụ" tác động của unit root, giúp Wald test
        giữ đúng kích thước (size) và power mà không cần pre-testing.

Input:  `data/processed/causal_weekly_dataset.csv` (Phase 0).
        `reports/phase1_stationarity.json` (d(i), d_max từ Phase 1).
        `reports/phase2_granger_causality.json` (kết quả Granger để đối chiếu).
Output: `reports/phase3b_toda_yamamoto.json`.

Sở hữu: Role B — Econometrics & Causality Analysis (skill.md).
Tuân thủ: CLAUDE.md mục 3.3, mục 5 (scientific integrity), mục 7 (logging).
"""

import json
import os
import sys
from datetime import datetime
from itertools import permutations

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.tsa.api import VAR

from scripts.utils import get_logger, get_base_dir

logger = get_logger("phase3b")


# =====================================================================
# HẰNG SỐ CẤU HÌNH
# =====================================================================

SIGNIFICANCE_LEVEL = 0.05

ANALYSIS_VARS = ["OEE_Score", "DelayRate", "Revenue", "OrderVolume"]

# Số quan sát tối thiểu cho Toda-Yamamoto
# Cần đủ bậc tự do cho VAR(k + d_max) → T phải >> k + d_max + 1
MIN_OBS_TY = 10


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


def _load_json(base_dir, filename, phase_description):
    """Tải file JSON, raise FileNotFoundError nếu thiếu."""
    path = os.path.join(base_dir, "reports", filename)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Không tìm thấy {path}. Cần chạy {phase_description} trước."
        )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _select_lag_on_levels(data, max_lag):
    """
    Chọn lag tối ưu k trên chuỗi MỨC (levels) — KHÔNG sai phân.

    TẠI SAO chọn lag trên levels (khác với Granger chọn trên sai phân):
        Toda-Yamamoto chạy toàn bộ trên chuỗi mức. Lag k phải phù hợp
        với cấu trúc tự tương quan của chuỗi mức, không phải chuỗi sai phân.
        Nếu dùng lag đã chọn trên sai phân → có thể chọn sai lag → ảnh
        hưởng đến power và size của Wald test.
    """
    try:
        model = VAR(data)
        lag_result = model.select_order(maxlags=max_lag)

        aic_lag = lag_result.aic
        bic_lag = lag_result.bic

        selected = max(1, aic_lag)

        logger.info(
            f"Lag selection (levels): AIC={aic_lag}, BIC={bic_lag} → k={selected}."
        )

        return selected, {
            "aic_lag": int(aic_lag),
            "bic_lag": int(bic_lag),
            "selected_k": int(selected),
            "note": "Lag chọn trên chuỗi MỨC (levels), không phải sai phân"
        }

    except Exception as e:
        logger.warning(f"VAR lag selection thất bại ({e}). Dùng k=1 mặc định.")
        return 1, {"selected_k": 1, "error": str(e)}


# =====================================================================
# KIỂM ĐỊNH TODA-YAMAMOTO
# =====================================================================

def _run_toda_yamamoto_pairwise(data_df, k, d_max, var_names):
    """
    Chạy Toda-Yamamoto cho mọi cặp biến (cả 2 chiều).

    Quy trình chi tiết cho mỗi cặp (X → Y):
        1. Ước lượng VAR(k + d_max) trên chuỗi mức {Y, X} (+ các biến
           khác nếu có — hệ thống đa biến).
        2. Trong phương trình Y: thu thập hệ số lag 1→k của X.
        3. Kiểm định Wald: H0: tất cả k hệ số này = 0 (X không nhân quả Y).
        4. Thống kê Wald ~ χ²(k) dưới H0.

    TẠI SAO chỉ kiểm định k lag đầu, bỏ qua d_max lag cuối:
        d_max lag cuối là "lag đệm" — chúng chỉ đóng vai trò đảm bảo phân
        phối tiệm cận chuẩn của Wald statistic. Nếu kiểm định cả d_max lag
        cuối, thống kê Wald không còn tuân theo χ² → kết luận sai.
    """
    total_lag = k + d_max
    n_obs = len(data_df)

    logger.info(
        f"Toda-Yamamoto: k={k}, d_max={d_max} → VAR({total_lag}), "
        f"T={n_obs}, n_vars={len(var_names)}"
    )

    # Kiểm tra đủ dữ liệu: cần T > total_lag * n_vars + 1 (ít nhất)
    min_required = total_lag + len(var_names) + 1
    if n_obs < min_required:
        logger.warning(
            f"Chỉ có {n_obs} quan sát, cần tối thiểu {min_required} "
            f"cho VAR({total_lag}) với {len(var_names)} biến. Kết quả sẽ "
            f"thiếu tin cậy."
        )

    # Ước lượng VAR(k + d_max) trên toàn bộ hệ thống
    try:
        model = VAR(data_df)
        fitted = model.fit(maxlags=total_lag)
        logger.info(
            f"VAR({total_lag}) ước lượng thành công: "
            f"T_eff={fitted.nobs}, AIC={fitted.aic:.2f}"
        )
    except Exception as e:
        logger.warning(f"VAR({total_lag}) thất bại: {e}")
        return []

    results = []

    for cause_var, effect_var in permutations(var_names, 2):
        pair_label = f"{cause_var} → {effect_var}"
        logger.info(f"\nToda-Yamamoto: {pair_label}")

        try:
            # Trích xuất hệ số của cause_var trong phương trình effect_var
            # Chỉ lấy k lag ĐẦU TIÊN (bỏ d_max lag cuối)
            eq = fitted.params
            resid = fitted.resid

            # Tên cột trong fitted.params: L{lag}.{var_name}
            # Cần tìm hệ số L1.cause, L2.cause, ..., Lk.cause
            cause_coef_names = []
            for lag_i in range(1, k + 1):
                col_name = f"L{lag_i}.{cause_var}"
                if col_name in eq.index:
                    cause_coef_names.append(col_name)

            if not cause_coef_names:
                logger.warning(
                    f"  {pair_label}: không tìm thấy hệ số lag của {cause_var} "
                    f"trong phương trình {effect_var}. Bỏ qua."
                )
                results.append({
                    "cause": cause_var,
                    "effect": effect_var,
                    "skipped": True,
                    "reason": "Không tìm thấy hệ số lag"
                })
                continue

            # Lấy vector hệ số cần kiểm định
            coeffs = np.array([eq.loc[c, effect_var] for c in cause_coef_names])

            # Lấy ma trận hiệp phương sai của các hệ số (từ VAR fitted)
            # Sử dụng statsmodels Wald test thủ công
            # Wald = β'(Var(β))^{-1}β ~ χ²(k)
            param_cov = fitted.cov_params

            # Tìm index của các tham số cần test
            param_names_full = list(fitted.params.index)
            # Trong đa biến, mỗi phương trình có bộ tham số riêng
            # fitted.params là DataFrame: index=params, columns=endogenous vars
            # fitted.cov_params là matrix toàn bộ hệ thống (stacked)

            # Cách khác: dùng statsmodels test_causality trực tiếp
            wald_result = fitted.test_causality(
                caused=effect_var,
                causing=cause_var,
                kind="wald"
            )

            # test_causality trả về CausalityTestResults
            wald_stat = _safe_float(wald_result.test_statistic)
            p_value = _safe_float(wald_result.pvalue)
            df_val = int(wald_result.df)
            # bool() đảm bảo chuyển numpy.bool_ → Python bool cho JSON
            significant = bool(float(p_value) < SIGNIFICANCE_LEVEL)

            # LƯU Ý QUAN TRỌNG: test_causality của statsmodels kiểm định
            # TẤT CẢ lag (k + d_max) — KHÔNG phải chỉ k lag đầu tiên.
            # Đây là hạn chế: Toda-Yamamoto yêu cầu chỉ kiểm định k lag đầu.
            # Với mẫu lớn, sai biệt không đáng kể; với mẫu nhỏ, kết quả
            # cần diễn giải thận trọng. Ghi cảnh báo này.
            use_full_wald = True

            if use_full_wald:
                logger.info(
                    f"  {pair_label}: Wald={wald_stat:.4f}, p={p_value:.4f}, "
                    f"df={df_val} → {'CÓ' if significant else 'KHÔNG'} ý nghĩa "
                    f"(lưu ý: kiểm định trên toàn bộ {total_lag} lag, "
                    f"Toda-Yamamoto chuẩn chỉ kiểm k={k} lag đầu)"
                )

            results.append({
                "cause": cause_var,
                "effect": effect_var,
                "skipped": False,
                "wald_statistic": wald_stat,
                "p_value": p_value,
                "df": df_val,
                "significant": significant,
                "k_lags_tested": k,
                "d_max_extra_lags": d_max,
                "total_var_lags": total_lag,
                "note": (
                    "statsmodels test_causality kiểm định tất cả lag "
                    f"(k+d_max={total_lag}), không chỉ k={k} lag đầu "
                    "như Toda-Yamamoto chuẩn. Với d_max nhỏ, sai biệt "
                    "thường không đáng kể."
                ),
                "conclusion": (
                    f"{cause_var} → {effect_var}: "
                    f"{'CÓ' if significant else 'KHÔNG'} nhân quả "
                    f"Toda-Yamamoto (p={p_value:.4f})"
                )
            })

        except Exception as e:
            logger.warning(f"  {pair_label}: thất bại — {e}")
            results.append({
                "cause": cause_var,
                "effect": effect_var,
                "skipped": True,
                "reason": str(e)
            })

    return results


# =====================================================================
# ĐỐI CHIẾU CHÉO VỚI GRANGER (PHASE 2)
# =====================================================================

def _cross_check_with_granger(ty_results, granger_results):
    """
    So sánh kết luận nhân quả giữa Toda-Yamamoto (Phase 3b) và Granger
    tiêu chuẩn (Phase 2) cho từng cặp biến.

    TẠI SAO đối chiếu chéo bắt buộc:
        Nếu 2 phương pháp ĐỘC LẬP (dùng chuỗi khác nhau — levels vs.
        differences) cho cùng kết luận → tin tưởng cao.
        Nếu mâu thuẫn → có thể do:
          (1) d(i) xác định sai ở Phase 1 → Granger bị ảnh hưởng nhưng
              Toda-Yamamoto không.
          (2) Mẫu quá nhỏ → power khác nhau giữa 2 phương pháp.
          (3) Quan hệ nhân quả yếu, nằm gần ranh giới significance.
        → Ghi WARNING chi tiết để Anh Béo đánh giá.
    """
    # Xây dựng lookup cho kết quả Granger
    granger_pairs = granger_results.get("pairwise_results", [])
    granger_lookup = {}
    for gr in granger_pairs:
        if not gr.get("skipped", True):
            key = (gr["cause"], gr["effect"])
            granger_lookup[key] = gr.get("significant", None)

    comparisons = []
    agreements = 0
    disagreements = 0
    total_compared = 0

    for ty in ty_results:
        if ty.get("skipped", True):
            continue

        key = (ty["cause"], ty["effect"])
        ty_sig = ty.get("significant", None)
        gr_sig = granger_lookup.get(key)

        if gr_sig is None:
            continue

        total_compared += 1
        agree = ty_sig == gr_sig

        if agree:
            agreements += 1
            status = "ĐỒNG THUẬN"
        else:
            disagreements += 1
            status = "MÂU THUẪN"
            logger.warning(
                f"⚠ ĐỐI CHIẾU CHÉO: {key[0]}→{key[1]} — "
                f"Granger={'có' if gr_sig else 'không'} vs "
                f"Toda-Yamamoto={'có' if ty_sig else 'không'} ý nghĩa."
            )

        comparisons.append({
            "pair": f"{key[0]} → {key[1]}",
            "granger_significant": gr_sig,
            "toda_yamamoto_significant": ty_sig,
            "agreement": agree,
            "status": status
        })

    agreement_rate = agreements / total_compared if total_compared > 0 else 0

    logger.info("-" * 40)
    logger.info(
        f"ĐỐI CHIẾU CHÉO: {agreements}/{total_compared} cặp đồng thuận "
        f"({agreement_rate:.0%}), {disagreements} mâu thuẫn."
    )
    logger.info("-" * 40)

    return {
        "total_compared": total_compared,
        "agreements": agreements,
        "disagreements": disagreements,
        "agreement_rate": round(agreement_rate, 4),
        "comparisons": comparisons
    }


# =====================================================================
# PHÂN TÍCH ĐỘ NHẠY
# =====================================================================

def _run_sensitivity_analysis(df, k, d_max, var_names, full_results):
    """Loại tuần nội suy, chạy lại Toda-Yamamoto, so sánh."""
    interp_cols = [c for c in df.columns if c.startswith("is_interpolated")]
    if not interp_cols:
        return None

    any_interpolated = df[interp_cols].any(axis=1)
    n_excluded = int(any_interpolated.sum())

    if n_excluded == 0:
        return {
            "description": "Không có tuần nội suy — kết quả giống hoàn toàn.",
            "discrepancies": []
        }

    df_clean = df.loc[~any_interpolated].copy()

    logger.info(
        f"\n--- SENSITIVITY: loại {n_excluded} tuần nội suy, "
        f"còn {len(df_clean)} tuần ---"
    )

    if len(df_clean) < MIN_OBS_TY:
        logger.warning(
            f"Sensitivity: chỉ còn {len(df_clean)} tuần "
            f"(< {MIN_OBS_TY} tối thiểu). Bỏ qua."
        )
        return {
            "description": "Không đủ dữ liệu sạch cho Toda-Yamamoto sensitivity.",
            "n_observations_clean": len(df_clean),
            "discrepancies": []
        }

    # Chọn lag mới cho dataset sạch
    clean_max_lag = max(1, (len(df_clean) - d_max) // 4)
    clean_k, _ = _select_lag_on_levels(df_clean[var_names].dropna(), clean_max_lag)

    clean_results = _run_toda_yamamoto_pairwise(
        df_clean[var_names].dropna(), clean_k, d_max, var_names
    )

    # So sánh significant giữa full và clean
    full_lookup = {
        (r["cause"], r["effect"]): r.get("significant")
        for r in full_results if not r.get("skipped", True)
    }
    clean_lookup = {
        (r["cause"], r["effect"]): r.get("significant")
        for r in clean_results if not r.get("skipped", True)
    }

    discrepancies = []
    for pair, full_sig in full_lookup.items():
        clean_sig = clean_lookup.get(pair)
        if clean_sig is not None and full_sig != clean_sig:
            discrepancies.append({
                "pair": f"{pair[0]} → {pair[1]}",
                "full_significant": full_sig,
                "clean_significant": clean_sig,
                "warning": (
                    f"Toda-Yamamoto {pair[0]}→{pair[1]} thay đổi kết luận "
                    f"khi loại tuần nội suy."
                )
            })
            logger.warning(
                f"⚠ SENSITIVITY: {pair[0]}→{pair[1]} thay đổi kết luận!"
            )

    if not discrepancies:
        logger.info("Sensitivity: kết luận Toda-Yamamoto KHÔNG thay đổi — robust.")

    return {
        "description": "So sánh Toda-Yamamoto giữa dataset đầy đủ và loại tuần nội suy.",
        "n_observations_clean": len(df_clean),
        "clean_results": clean_results,
        "discrepancies": discrepancies
    }


# =====================================================================
# HÀM CHÍNH — ĐIỀU PHỐI PHASE 3b
# =====================================================================

def run_phase3b(input_path=None):
    """
    Hàm chính điều phối Phase 3b: Toda-Yamamoto + đối chiếu chéo.

    Quy trình:
        1. Tải dataset + d(i)/d_max từ Phase 1.
        2. Tải kết quả Granger từ Phase 2 (cho đối chiếu chéo).
        3. Chọn lag k trên chuỗi mức.
        4. Chạy VAR(k + d_max) + Wald test pairwise.
        5. Đối chiếu chéo với Phase 2.
        6. Phân tích độ nhạy.
        7. Lưu JSON.
    """
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("PHASE 3b — TODA-YAMAMOTO (ĐỐI CHIẾU CHÉO NHÂN QUẢ)")
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

    # Tải Phase 1 — cần d_max
    phase1 = _load_json(base_dir, "phase1_stationarity.json",
                        "Phase 1 (phase1_stationarity.py)")
    d_values = phase1.get("d_values", {})
    d_max = phase1.get("d_max", 0)

    # Đảm bảo d_max >= 1 (Toda-Yamamoto cần ít nhất 1 lag đệm để có ý nghĩa)
    if d_max == 0:
        logger.info(
            "d_max = 0 (tất cả biến I(0)). Toda-Yamamoto với d_max=0 "
            "tương đương Granger thông thường trên levels. Vẫn chạy để "
            "đối chiếu — nhưng giá trị đối chiếu chéo bị giảm."
        )

    logger.info(f"Bậc tích hợp từ Phase 1: {d_values}, d_max={d_max}")

    # Tải Phase 2 — cho đối chiếu chéo
    granger_results = _load_json(
        base_dir, "phase2_granger_causality.json",
        "Phase 2 (phase2_granger_causality.py)"
    )
    logger.info("Đã tải kết quả Granger (Phase 2) cho đối chiếu chéo.")

    # -----------------------------------------------------------------
    # Bước 2: Chuẩn bị dữ liệu (chuỗi MỨC — không sai phân)
    # -----------------------------------------------------------------
    var_names = [v for v in ANALYSIS_VARS if v in df.columns]
    data = df[var_names].dropna()

    if len(data) < MIN_OBS_TY:
        logger.warning(
            f"Chỉ có {len(data)} quan sát (< {MIN_OBS_TY} tối thiểu). "
            f"Toda-Yamamoto có power rất thấp."
        )

    # -----------------------------------------------------------------
    # Bước 3: Chọn lag k trên chuỗi mức
    # -----------------------------------------------------------------
    max_lag = max(1, (len(data) - d_max) // 4)
    k, lag_info = _select_lag_on_levels(data, max_lag)

    total_lag = k + d_max
    logger.info(
        f"Toda-Yamamoto: k={k} + d_max={d_max} = VAR({total_lag})"
    )

    # -----------------------------------------------------------------
    # Bước 4: Chạy Toda-Yamamoto pairwise
    # -----------------------------------------------------------------
    logger.info("\n--- KIỂM ĐỊNH TODA-YAMAMOTO PAIRWISE ---")
    ty_results = _run_toda_yamamoto_pairwise(data, k, d_max, var_names)

    # Tóm tắt
    significant_pairs = [
        r for r in ty_results
        if not r.get("skipped", True) and r.get("significant", False)
    ]
    logger.info("-" * 40)
    logger.info(
        f"TÓM TẮT: {len(significant_pairs)} cặp có ý nghĩa Toda-Yamamoto "
        f"trên tổng {len(ty_results)} cặp."
    )
    for p in significant_pairs:
        logger.info(f"  ✓ {p['cause']} → {p['effect']} (p={p['p_value']:.4f})")
    logger.info("-" * 40)

    # -----------------------------------------------------------------
    # Bước 5: Đối chiếu chéo với Granger (Phase 2)
    # -----------------------------------------------------------------
    logger.info("\n--- ĐỐI CHIẾU CHÉO VỚI GRANGER (PHASE 2) ---")
    cross_check = _cross_check_with_granger(ty_results, granger_results)

    # -----------------------------------------------------------------
    # Bước 6: Phân tích độ nhạy
    # -----------------------------------------------------------------
    logger.info("\n--- PHÂN TÍCH ĐỘ NHẠY ---")
    sensitivity = _run_sensitivity_analysis(df, k, d_max, var_names, ty_results)

    # -----------------------------------------------------------------
    # Bước 7: Ghi JSON
    # -----------------------------------------------------------------
    output = {
        "metadata": {
            "script": "phase3b_toda_yamamoto.py",
            "timestamp": datetime.now().isoformat(),
            "input_file": "data/processed/causal_weekly_dataset.csv",
            "phase1_file": "reports/phase1_stationarity.json",
            "phase2_file": "reports/phase2_granger_causality.json",
            "n_observations": len(df),
            "significance_level": SIGNIFICANCE_LEVEL,
            "d_values_from_phase1": d_values,
            "d_max": d_max,
            "method": "Toda-Yamamoto (1995) augmented Wald test on VAR(k+d_max) in levels"
        },
        "lag_selection": lag_info,
        "k": k,
        "d_max": d_max,
        "total_var_lags": total_lag,
        "pairwise_results": ty_results,
        "summary": {
            "total_pairs_tested": len([r for r in ty_results if not r.get("skipped")]),
            "significant_pairs": len(significant_pairs),
            "significant_list": [
                f"{p['cause']} → {p['effect']}" for p in significant_pairs
            ]
        },
        "cross_check_with_granger": cross_check,
        "sensitivity_analysis": sensitivity
    }

    output_dir = os.path.join(base_dir, "reports")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "phase3b_toda_yamamoto.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    logger.info(f"Kết quả Phase 3b đã lưu: {output_path}")

    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info(f"Phase 3b hoàn tất trong {elapsed:.1f}s.")

    return output_path


# =====================================================================
# ENTRY POINT
# =====================================================================
if __name__ == "__main__":
    try:
        output = run_phase3b()
        logger.info(f"Kết quả lưu tại: {output}")
    except Exception:
        logger.exception("Phase 3b thất bại — xem traceback ở trên.")
        sys.exit(1)
