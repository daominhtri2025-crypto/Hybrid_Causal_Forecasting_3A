"""
Tầng 4 — Dự báo bằng VECM hoặc VAR trên mức gốc (tùy route từ Phase 3)

Mục đích:
  Xây dựng mô hình dự báo với tham số KHÓA CỨNG từ Tầng 3 (Phase 3).
  Tùy theo kết quả Johansen cointegration test:
    - route = "VECM": dùng VECM (coint_rank < n_vars → có đồng tích hợp)
    - route = "VAR_on_levels": dùng VAR trên levels (rank = n → full rank,
      không có đồng tích hợp)
  Dự báo h = 4 chu kỳ (tuần) tiếp theo, kèm khoảng tin cậy 95%.

Cơ sở toán học — VECM (Vector Error Correction Model):
  ═══════════════════════════════════════════════════════

  VECM là dạng tái tham số hóa (reparameterization) của mô hình VAR(p) dành
  cho hệ thống biến có ĐỒNG TÍCH HỢP (cointegration). Thay vì ước lượng VAR
  trên mức gốc (levels), VECM phân tách rõ ràng 2 thành phần:

  (1) QUAN HỆ DÀI HẠN — Cointegrating Equation (CE):
      ─────────────────────────────────────────────────
      β'·y_{t-1} = Error Correction Term (ECT)

      Ma trận β (n × r) chứa r vector đồng tích hợp — mỗi vector mô tả MỘT
      quan hệ cân bằng dài hạn giữa các biến. Ở trạng thái cân bằng,
      β'·y_t ≈ 0. Khi hệ thống lệch khỏi cân bằng → ECT ≠ 0 → tín hiệu
      kích hoạt cơ chế tự điều chỉnh.

      Ví dụ: nếu OEE tăng bất thường (lệch cân bằng), ECT > 0, hệ thống
      sẽ điều chỉnh OEE giảm lại hoặc các biến khác tăng lên để khôi phục
      trạng thái cân bằng — TỐC ĐỘ điều chỉnh do ma trận α quyết định.

  (2) QUAN HỆ NGẮN HẠN — Short-run Dynamics:
      ──────────────────────────────────────────
      Δy_t = α·(β'·y_{t-1}) + Γ₁·Δy_{t-1} + ... + Γ_k·Δy_{t-k} + c + u_t

      - α (n × r): ma trận tốc độ điều chỉnh (adjustment/loading coefficients)
        + α_ij < 0: biến i tự GIẢM khi ECT_j > 0 → error correcting
        + |α_ij| lớn: phản ứng nhanh (điều chỉnh mạnh mẽ)
        + α_ij ≈ 0: biến i gần như không phản ứng với lệch cân bằng j

      - Γ_j (n × n): hệ số trễ ngắn hạn — tác động của Δy_{t-j} lên Δy_t.
        Nắm bắt quán tính (momentum) ngắn hạn giữa các biến.

      - c: hằng số KHÔNG HẠN CHẾ (unrestricted constant, nằm NGOÀI cointegrating
        relation). Cho phép các biến có xu hướng tuyến tính trong mức gốc.
        Tương ứng det_order=1 trong Johansen test Phase 3 (Lütkepohl 2005, Ch.6).

      - u_t ~ N(0, Σ_u): nhiễu trắng (white noise innovation). Ma trận Σ_u
        dùng để tính khoảng tin cậy dự báo qua biểu diễn MA (Moving Average).

  Khoảng tin cậy dự báo (Lütkepohl 2005, Mục 6.5):
  ──────────────────────────────────────────────────
      Sai số dự báo tại tầm h: e_{T+h|T} = Σ_{i=0}^{h-1} Ψ_i · u_{T+h-i}
      Phương sai:  Var(e_{T+h|T}) = Σ_{i=0}^{h-1} Ψ_i · Σ_u · Ψ_i'
      CI 95%:      forecast ± 1.96 × √(diag(Var))

      Trong đó Ψ_i là ma trận hệ số MA (Moving Average) — chính là các
      impulse response functions (IRF) của process LEVELS.

  Tham khảo:
    - Johansen, S. (1995). Likelihood-Based Inference in Cointegrated VAR Models.
    - Lütkepohl, H. (2005). New Introduction to Multiple Time Series Analysis.
    - Pfaff, B. (2008). Analysis of Integrated and Cointegrated Time Series with R.

Input:
  - data/processed/causal_weekly_dataset.csv (output Phase 0 — Tầng 2)
  - reports/phase3_cointegration.json (coint_rank, k_ar_diff, route — Tầng 3)

Output:
  - reports/forecasts/vecm_forecast.csv (dự báo h=4 tuần kèm CI 95%)
  - reports/tang4_vecm_results.json (tham số mô hình, cointegrating equations,
    short-run dynamics, diagnostics)

Tuân thủ: CLAUDE.md mục 2 (bất biến dữ liệu), 3.1 (comment tiếng Việt),
          3.3 (không hard-code — đọc từ Phase trước), 7 (logging chuẩn).
"""

import os
import sys
import json
import warnings
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from statsmodels.tsa.vector_ar.vecm import VECM
from statsmodels.tsa.api import VAR as VARModel

# ── Import tiện ích dùng chung (CLAUDE.md mục 7.1) ──
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import get_logger, get_base_dir

# ══════════════════════════════════════════════════════════════════════
# HẰNG SỐ CỐ ĐỊNH — không phụ thuộc kết quả Phase nào
# ══════════════════════════════════════════════════════════════════════
FORECAST_HORIZON = 4       # dự báo 4 tuần tiếp theo
CONFIDENCE_LEVEL = 0.95    # khoảng tin cậy 95%
Z_SCORE_95 = 1.96          # z-score hai phía cho phân phối chuẩn

# Thứ tự biến CỐ ĐỊNH — khớp với Tầng 3 (Phase 1–3b)
ANALYSIS_VARIABLES = ["OEE_Score", "DelayRate", "Revenue", "OrderVolume"]

# Seed cho reproducibility (CLAUDE.md mục 3.5)
np.random.seed(42)


# ══════════════════════════════════════════════════════════════════════
# HÀM TIỆN ÍCH
# ══════════════════════════════════════════════════════════════════════

def _safe_float(val):
    """
    Chuyển numpy scalar → Python native type để json.dump() không lỗi.
    Bài học từ Tầng 3: numpy.bool_ và numpy.float64 gây ra bug nghiêm trọng
    khi serialize bằng json.dump(default=str) — "False" (string) ≠ false (JSON).
    """
    if isinstance(val, (np.floating, float)):
        return float(val)
    if isinstance(val, (np.integer, int)):
        return int(val)
    if isinstance(val, np.bool_):
        return bool(val)
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    return val


def _matrix_to_list(arr):
    """Chuyển numpy 2D array → nested list Python (JSON-safe)."""
    if isinstance(arr, np.ndarray):
        return [[_safe_float(v) for v in row] for row in arr]
    return arr


def _compute_forecast_ci(vecm_result, forecast, n_vars, h, logger):
    """
    Tính khoảng tin cậy 95% cho dự báo VECM.

    Phương pháp ưu tiên: biểu diễn MA trích từ IRF (Impulse Response Function)
    để tính CHÍNH XÁC phương sai sai số dự báo tại mỗi tầm.

    Công thức (Lütkepohl 2005, Mục 6.5):
        Var(e_{T+h|T}) = Σ_{i=0}^{h-1} Ψ_i · Σ_u · Ψ_i'

        Ψ_i: ma trận hệ số MA bậc i (= impulse response tại bước i)
             Ψ_0 = I (identity) → tại h=1, Var = Σ_u (chỉ innovation)
        Σ_u: ma trận hiệp phương sai innovation (fitted residuals)

    Fallback: nếu IRF không khả dụng (lỗi số học do mẫu nhỏ), dùng
    xấp xỉ √h — giả định thành phần random walk chi phối sai số dự báo.
    Xấp xỉ này thiên LẠC QUAN (đánh giá thấp) uncertainty ở tầm ngắn,
    nhưng là phương án hợp lý cho mẫu cực nhỏ (N=10).

    Trả về: (lower, upper, se) — arrays shape (h, n_vars)
    """
    se = np.zeros((h, n_vars))
    ci_method = "unknown"

    try:
        # Ưu tiên: IRF cho MA coefficients chính xác
        irf_obj = vecm_result.irf(periods=h)
        # irf_obj.irfs: shape (h+1, n, n) — Ψ_0, Ψ_1, ..., Ψ_h
        # Ψ_0 = I (identity matrix): shock tại t ảnh hưởng ngay tại t
        ma_coeffs = irf_obj.irfs
        sigma_u = vecm_result.sigma_u

        for j in range(h):
            # Phương sai sai số dự báo tại tầm (j+1):
            # Var_{j+1} = Σ_{i=0}^{j} Ψ_i · Σ_u · Ψ_i'
            var_j = np.zeros((n_vars, n_vars))
            for i in range(j + 1):
                psi_i = ma_coeffs[i]
                var_j += psi_i @ sigma_u @ psi_i.T

            # Lấy sai số chuẩn từ đường chéo chính (variance từng biến)
            # np.maximum(..., 0) tránh sqrt số âm do lỗi số học
            se[j] = np.sqrt(np.maximum(np.diag(var_j), 0))

        ci_method = "IRF/MA (Lütkepohl 2005)"
        logger.info(f"CI tính bằng phương pháp {ci_method}.")

    except Exception as e:
        # Fallback: xấp xỉ √h khi IRF không khả dụng
        logger.warning(
            f"IRF không khả dụng ({type(e).__name__}: {e}). "
            f"Dùng xấp xỉ √h cho khoảng tin cậy."
        )
        sigma_u = vecm_result.sigma_u
        # se tại h=1 = √diag(Σ_u) (innovation standard deviation)
        se_1 = np.sqrt(np.maximum(np.diag(sigma_u), 0))
        for j in range(h):
            # Xấp xỉ: sai số tăng như √(horizon) — hợp lệ cho random walk
            se[j] = se_1 * np.sqrt(j + 1)
        ci_method = "sqrt(h) approximation"
        logger.info(f"CI tính bằng xấp xỉ √h (fallback).")

    lower = forecast - Z_SCORE_95 * se
    upper = forecast + Z_SCORE_95 * se

    return lower, upper, se, ci_method


# ══════════════════════════════════════════════════════════════════════
# NHÁNH VAR TRÊN MỨC GỐC — Khi Johansen rank = n (full rank)
# ══════════════════════════════════════════════════════════════════════

def _run_var_on_levels(endog, df, n_obs, n_vars, lag_order,
                       route, input_csv, phase3_json,
                       base_dir, start_time, logger):
    """
    Nhánh VAR — dùng khi Johansen test chỉ định KHÔNG dùng VECM.

    Hai trường hợp:
      (1) VAR_on_levels (rank r = n, full rank): tất cả biến dừng ở mức →
          fit VAR trên levels trực tiếp. Forecast đã ở levels.
      (2) VAR_on_differences (rank r = 0): không đồng tích hợp → fit VAR
          trên sai phân bậc 1 (Δy). Forecast Δy được tích lũy (cumulate)
          lại levels bằng cách cộng vào giá trị cuối cùng đã quan sát.

    Tham khảo: Lütkepohl (2005), Chương 3 — VAR(p).
    """
    use_differences = (route == "VAR_on_differences")

    logger.info("─" * 60)
    if use_differences:
        logger.info("NHÁNH VAR TRÊN SAI PHÂN (DIFFERENCES)")
        logger.info("─" * 60)
        logger.info(f"  Lý do: Johansen rank = 0 → không có đồng tích hợp")
        logger.info(f"  → Dùng VAR(p={lag_order}) trên Δy (sai phân bậc 1)")
    else:
        logger.info("NHÁNH VAR TRÊN MỨC GỐC (LEVELS)")
        logger.info("─" * 60)
        logger.info(f"  Lý do: Johansen rank = n (full rank) → không có đồng tích hợp")
        logger.info(f"  → Dùng VAR(p={lag_order}) trên levels")

    # ── Tính bậc tự do ──
    params_per_eq = n_vars * lag_order + 1  # A_1..A_p + intercept
    effective_obs = n_obs - lag_order
    dof = effective_obs - params_per_eq

    logger.info(f"  Ước tính: {params_per_eq} params/equation, "
                f"~{effective_obs} effective obs, ~{dof} DoF")

    if dof < 5:
        logger.warning(
            f"BẬC TỰ DO ƯỚC TÍNH THẤP ({dof}). "
            f"Ước lượng VAR có thể không ổn định với mẫu nhỏ (N={n_obs})."
        )

    # ── Chuẩn bị dữ liệu đầu vào: levels hoặc sai phân ──
    if use_differences:
        # Sai phân bậc 1: Δy_t = y_t - y_{t-1}
        endog_fit = np.diff(endog, axis=0)  # shape (n_obs-1, n_vars)
        last_level = endog[-1, :].copy()    # y_T — dùng để cumulate forecast
        logger.info(f"  Đã sai phân: {endog_fit.shape[0]} quan sát Δy "
                     f"(từ {n_obs} levels)")
    else:
        endog_fit = endog

    # ── Fit VAR(p) ──
    endog_df = pd.DataFrame(endog_fit, columns=ANALYSIS_VARIABLES)
    model = VARModel(endog_df)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        var_result = model.fit(maxlags=lag_order, ic=None, trend="c")

    data_label = "Δy (sai phân)" if use_differences else "levels"
    logger.info(f"VAR({var_result.k_ar}) fit thành công trên {data_label}.")
    logger.info(f"  AIC = {var_result.aic:.4f}, BIC = {var_result.bic:.4f}")
    logger.info(f"  Log-likelihood = {var_result.llf:.4f}")

    # ── Log hệ số VAR (coefficient matrices) ──
    logger.info("─" * 60)
    logger.info("HỆ SỐ VAR (COEFFICIENT MATRICES)")
    logger.info("─" * 60)

    coef_matrices = {}
    for lag in range(var_result.k_ar):
        A_lag = np.asarray(var_result.coefs[lag])  # shape (n_vars, n_vars)
        coef_matrices[f"A_{lag + 1}"] = _matrix_to_list(A_lag)
        logger.info(f"  A_{lag + 1} — tác động của y_{{t-{lag + 1}}} lên y_t:")
        for v_idx, var_name in enumerate(ANALYSIS_VARIABLES):
            row_str = "  ".join(f"{A_lag[v_idx, j]:+.6f}" for j in range(n_vars))
            logger.info(f"    {var_name}: [{row_str}]")

    # Intercept: coefs_exog shape = (n_vars, n_trend)
    coefs_exog = np.asarray(var_result.coefs_exog)
    intercept = coefs_exog[:, 0] if coefs_exog.shape[1] > 0 else np.zeros(n_vars)
    coef_matrices["intercept"] = [_safe_float(v) for v in intercept]
    logger.info(f"  Intercept: [{', '.join(f'{v:+.6f}' for v in intercept)}]")

    # ── Dự báo + khoảng tin cậy 95% ──
    logger.info("─" * 60)
    logger.info(f"DỰ BÁO {FORECAST_HORIZON} BƯỚC (TUẦN)")
    logger.info("─" * 60)

    # forecast_interval trả về (point, lower, upper) — mỗi shape (h, n_vars)
    # Chuyển endog_fit về numpy array (VAR có thể trả DataFrame nếu input là DataFrame)
    endog_arr = np.asarray(endog_fit)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fc_point, fc_lower, fc_upper = var_result.forecast_interval(
            endog_arr, steps=FORECAST_HORIZON, alpha=1 - CONFIDENCE_LEVEL
        )

    # Xử lý NaN trong CI — xảy ra khi DoF = 0 (mẫu quá nhỏ, variance singular)
    has_nan_ci = np.any(np.isnan(fc_lower)) or np.any(np.isnan(fc_upper))
    if has_nan_ci:
        logger.warning(
            "Khoảng tin cậy chứa NaN (DoF quá thấp để ước lượng variance). "
            "Dùng xấp xỉ √h từ residual std làm fallback."
        )
        # Fallback: dùng residual std × √h
        resid_std = np.std(np.asarray(var_result.resid), axis=0, ddof=0)
        for h_idx in range(FORECAST_HORIZON):
            se_h = resid_std * np.sqrt(h_idx + 1)
            fc_lower[h_idx] = fc_point[h_idx] - Z_SCORE_95 * se_h
            fc_upper[h_idx] = fc_point[h_idx] + Z_SCORE_95 * se_h

    if use_differences:
        # Forecast trên Δy → tích lũy (cumulate) về levels:
        #   ŷ_{T+1} = y_T + Δŷ_{T+1}
        #   ŷ_{T+2} = y_T + Δŷ_{T+1} + Δŷ_{T+2}
        fc_point = last_level + np.cumsum(fc_point, axis=0)
        fc_lower = last_level + np.cumsum(fc_lower, axis=0)
        fc_upper = last_level + np.cumsum(fc_upper, axis=0)
        logger.info("  Đã tích lũy (cumulate) dự báo Δy → levels.")

    # Tính SE từ khoảng tin cậy
    fc_se = (fc_upper - fc_point) / Z_SCORE_95
    ci_method = (
        f"VAR forecast_interval trên {'Δy (cumulated)' if use_differences else 'levels'} "
        f"(Lütkepohl 2005)"
        + (" [fallback √h]" if has_nan_ci else "")
    )

    logger.info(f"Dự báo thành công: shape={fc_point.shape}")

    # ── Tạo dates + DataFrame kết quả ──
    last_date = df["week_start"].max()
    future_dates = [
        last_date + timedelta(weeks=i + 1) for i in range(FORECAST_HORIZON)
    ]

    logger.info("─" * 60)
    logger.info("KẾT QUẢ DỰ BÁO (Point Forecast ± 95% CI)")
    logger.info("─" * 60)

    forecast_records = []
    for h_idx in range(FORECAST_HORIZON):
        record = {"week_start": future_dates[h_idx].strftime("%Y-%m-%d")}
        for v_idx, var in enumerate(ANALYSIS_VARIABLES):
            fc = float(fc_point[h_idx, v_idx])
            lo = float(fc_lower[h_idx, v_idx])
            hi = float(fc_upper[h_idx, v_idx])
            record[f"{var}_forecast"] = fc
            record[f"{var}_lower_95"] = lo
            record[f"{var}_upper_95"] = hi
        forecast_records.append(record)

        logger.info(f"  Tuần {future_dates[h_idx].date()} (T+{h_idx + 1}):")
        for v_idx, var in enumerate(ANALYSIS_VARIABLES):
            fc = float(fc_point[h_idx, v_idx])
            lo = float(fc_lower[h_idx, v_idx])
            hi = float(fc_upper[h_idx, v_idx])
            logger.info(f"    {var:15s}: {fc:>12.4f}  [{lo:>12.4f}, {hi:>12.4f}]")

    forecast_df = pd.DataFrame(forecast_records)

    # ── Lưu CSV dự báo ──
    forecast_dir = os.path.join(base_dir, "reports", "forecasts")
    os.makedirs(forecast_dir, exist_ok=True)
    forecast_csv_path = os.path.join(forecast_dir, "vecm_forecast.csv")
    forecast_df.to_csv(forecast_csv_path, index=False)
    logger.info(f"Đã lưu dự báo CSV: {forecast_csv_path}")

    # ── Lưu JSON chi tiết ──
    sigma_u = np.asarray(var_result.sigma_u)

    output_json = {
        "metadata": {
            "script": "tang4_vecm_forecasting.py",
            "model_type": route,
            "timestamp": datetime.now().isoformat(),
            "input_csv": os.path.relpath(input_csv, base_dir),
            "phase3_json": os.path.relpath(phase3_json, base_dir),
            "n_observations": n_obs,
            "forecast_horizon": FORECAST_HORIZON,
            "confidence_level": CONFIDENCE_LEVEL,
            "ci_method": ci_method,
            "variables": ANALYSIS_VARIABLES,
        },
        "locked_parameters": {
            "route": route,
            "lag_order": int(var_result.k_ar),
            "trend": "c",
            "fit_on": "differences (Δy)" if use_differences else "levels",
            "route_explanation": (
                (
                    "Johansen rank = 0 → không đồng tích hợp → VAR trên sai "
                    "phân bậc 1. Forecast Δy được tích lũy về levels."
                ) if use_differences else (
                    "Johansen rank = n (full rank) → không đồng tích hợp → "
                    "VAR trên levels. Phổ biến khi dữ liệu hỗn hợp I(0)+I(1)."
                )
            ),
        },
        "var_coefficients": coef_matrices,
        "model_diagnostics": {
            "sigma_u": _matrix_to_list(sigma_u),
            "sigma_u_description": (
                "Ma trận hiệp phương sai innovation (n × n). "
                "Đường chéo = variance sai số từng biến."
            ),
            "log_likelihood": _safe_float(float(var_result.llf)),
            "aic": _safe_float(float(var_result.aic)),
            "bic": _safe_float(float(var_result.bic)),
            "effective_observations": int(var_result.nobs),
            "degrees_of_freedom_per_equation": int(var_result.df_resid),
            "total_parameters": int(n_vars * params_per_eq),
        },
        "forecast": {
            "dates": [d.strftime("%Y-%m-%d") for d in future_dates],
            "point_forecasts": {
                var: [float(fc_point[h, v_idx])
                      for h in range(FORECAST_HORIZON)]
                for v_idx, var in enumerate(ANALYSIS_VARIABLES)
            },
            "lower_95": {
                var: [float(fc_lower[h, v_idx])
                      for h in range(FORECAST_HORIZON)]
                for v_idx, var in enumerate(ANALYSIS_VARIABLES)
            },
            "upper_95": {
                var: [float(fc_upper[h, v_idx])
                      for h in range(FORECAST_HORIZON)]
                for v_idx, var in enumerate(ANALYSIS_VARIABLES)
            },
            "standard_errors": {
                var: [float(fc_se[h, v_idx])
                      for h in range(FORECAST_HORIZON)]
                for v_idx, var in enumerate(ANALYSIS_VARIABLES)
            },
        },
        "warnings": [],
    }

    # ── Cảnh báo ──
    if dof < 5:
        output_json["warnings"].append(
            f"Bậc tự do thấp ({dof}/equation). Ước lượng có thể không ổn định."
        )
    if n_obs < 30:
        output_json["warnings"].append(
            f"Mẫu nhỏ ({n_obs} tuần < 30 tối thiểu khuyến nghị). Khoảng "
            f"tin cậy có thể đánh giá THẤP hơn độ bất định thực tế."
        )

    for v_idx, var in enumerate(ANALYSIS_VARIABLES):
        for h_idx in range(FORECAST_HORIZON):
            fc = float(fc_point[h_idx, v_idx])
            if var in ("OEE_Score", "DelayRate") and (fc < 0 or fc > 1):
                output_json["warnings"].append(
                    f"{var} T+{h_idx + 1} = {fc:.4f}: ngoài [0, 1]. "
                    f"VAR không ràng buộc biên — cần diễn giải cẩn thận."
                )
            if var in ("Revenue", "OrderVolume") and fc < 0:
                output_json["warnings"].append(
                    f"{var} T+{h_idx + 1} = {fc:.4f}: âm (vô nghĩa kinh tế). "
                    f"Mô hình tuyến tính không ràng buộc phi âm."
                )

    if output_json["warnings"]:
        logger.warning(f"Có {len(output_json['warnings'])} cảnh báo:")
        for w in output_json["warnings"]:
            logger.warning(f"  ⚠ {w}")

    json_path = os.path.join(base_dir, "reports", "tang4_vecm_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output_json, f, ensure_ascii=False, indent=2)
    logger.info(f"Đã lưu JSON chi tiết: {json_path}")

    # ── Tổng kết ──
    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info("=" * 70)
    route_label = "VAR ON DIFFERENCES" if use_differences else "VAR ON LEVELS"
    logger.info(f"TẦNG 4 — {route_label} FORECASTING HOÀN TẤT trong {elapsed:.1f}s")
    fit_label = "Δy" if use_differences else "levels"
    logger.info(f"  Mô hình: VAR(p={var_result.k_ar}, trend='c') trên {fit_label}")
    logger.info(f"  Dự báo:  {FORECAST_HORIZON} tuần "
                f"({future_dates[0].date()} → {future_dates[-1].date()})")
    logger.info(f"  Output CSV:  {forecast_csv_path}")
    logger.info(f"  Output JSON: {json_path}")
    if output_json["warnings"]:
        logger.info(f"  Cảnh báo: {len(output_json['warnings'])}")
    logger.info("=" * 70)

    return {
        "forecast_csv": forecast_csv_path,
        "results_json": json_path,
        "forecast_df": forecast_df,
        "model_result": var_result,
    }


# ══════════════════════════════════════════════════════════════════════
# HÀM CHÍNH
# ══════════════════════════════════════════════════════════════════════

def run_tang4(input_csv=None, phase3_json=None):
    """
    Chạy Tầng 4: fit VECM → trích xuất phương trình → dự báo → xuất kết quả.

    Tham số:
        input_csv:   đường dẫn CSV (mặc định data/processed/causal_weekly_dataset.csv)
        phase3_json: đường dẫn JSON Phase 3 (mặc định reports/phase3_cointegration.json)

    Trả về:
        dict chứa đường dẫn output và kết quả chính.
    """
    logger = get_logger("tang4_vecm")
    logger.info("=" * 70)
    logger.info("TẦNG 4 — DỰ BÁO VECM (Vector Error Correction Model) BẮT ĐẦU")
    logger.info("=" * 70)
    start_time = datetime.now()

    base_dir = get_base_dir()

    # ══════════════════════════════════════════════════════════════════
    # BƯỚC 1: Đọc tham số KHÓA CỨNG từ Phase 3 (CLAUDE.md mục 3.3)
    # ══════════════════════════════════════════════════════════════════
    # TẠI SAO đọc từ JSON thay vì hard-code?
    # → Đảm bảo nhất quán (consistency) giữa Tầng 3 và Tầng 4. Nếu ai đó
    #   chạy lại Tầng 3 với dữ liệu mới và rank thay đổi, Tầng 4 tự động
    #   cập nhật mà không cần sửa code.

    if phase3_json is None:
        phase3_json = os.path.join(base_dir, "reports", "phase3_cointegration.json")

    logger.info(f"Đọc tham số từ Phase 3: {phase3_json}")

    if not os.path.exists(phase3_json):
        msg = f"Không tìm thấy file Phase 3: {phase3_json} — cần chạy Phase 3 trước."
        logger.error(msg)
        raise FileNotFoundError(msg)

    with open(phase3_json, "r", encoding="utf-8") as f:
        phase3 = json.load(f)

    # ── Trích xuất tham số đã chốt ──
    COINT_RANK = phase3["coint_rank"]   # = 2 (từ Johansen Trace test)
    route = phase3["route"]             # phải là "VECM"

    # Về k_ar_diff — mối quan hệ giữa VAR lag order và VECM k_ar_diff:
    #   VAR(p) ↔ VECM(k_ar_diff = p - 1)
    #   Phase 3 chọn selected_lag = 1 (VAR order p=1)
    #   → k_ar_diff = p - 1 = 0
    #   → Johansen test chạy với k_ar_diff = 0 → xác định rank r = 2
    #
    # k_ar_diff = 0 nghĩa là VECM chỉ có error correction term (αβ'y_{t-1})
    # và constant, KHÔNG có lagged differences (Γ·Δy_{t-1}). Với mẫu nhỏ
    # (N=10), đây là lựa chọn HỢP LÝ NHẤT:
    #   - k_ar_diff=0: 3 params/eq, ~9 eff obs, 6 DoF → ước lượng ổn định
    #   - k_ar_diff=1: 7 params/eq, ~8 eff obs, 1 DoF → OVERFITTING nghiêm
    #     trọng, dự báo bùng nổ (đã kiểm chứng: OEE dự báo lên hàng triệu)
    #
    # Kết luận: dùng k_ar_diff=0 từ Phase 3 JSON — đây KHÔNG phải "tự tìm
    # lại lag" mà là dùng ĐÚNG giá trị đã được Johansen test xác nhận.
    k_ar_diff_from_json = phase3.get("johansen_result", {}).get("k_ar_diff", 0)
    selected_lag_from_json = phase3.get("lag_selection", {}).get("selected_lag", 1)

    # KHÓA CỨNG — đọc từ Phase 3 JSON (CLAUDE.md mục 3.3)
    K_AR_DIFF = k_ar_diff_from_json  # = 0 (VAR lag p=1 → VECM k_ar_diff = p-1 = 0)

    logger.info("Tham số KHÓA CỨNG (Anti-Hallucination):")
    logger.info(f"  coint_rank    = {COINT_RANK} (từ Phase 3 Johansen Trace test)")
    logger.info(f"  k_ar_diff     = {K_AR_DIFF} (từ Phase 3 JSON; "
                f"VAR lag p={selected_lag_from_json} → VECM k_ar_diff = p-1 = "
                f"{K_AR_DIFF})")
    logger.info(f"  deterministic = 'co' (unrestricted constant — khớp Phase 3 "
                f"det_order=1)")
    logger.info(f"  Route: {route} — {phase3.get('route_explanation', '')}")

    if route not in ("VECM", "VAR_on_levels", "VAR_on_differences"):
        msg = (
            f"Phase 3 chỉ định route '{route}' không được hỗ trợ. "
            f"Tầng 4 hỗ trợ: VECM, VAR_on_levels, VAR_on_differences."
        )
        logger.error(msg)
        raise ValueError(msg)

    # ══════════════════════════════════════════════════════════════════
    # BƯỚC 2: Đọc dữ liệu đầu vào (bất biến — .copy())
    # ══════════════════════════════════════════════════════════════════
    if input_csv is None:
        input_csv = os.path.join(
            base_dir, "data", "processed", "causal_weekly_dataset.csv"
        )

    logger.info(f"Đọc dữ liệu: {input_csv}")
    df = pd.read_csv(input_csv, parse_dates=["week_start"]).copy()
    n_obs = len(df)
    date_min = df["week_start"].min().date()
    date_max = df["week_start"].max().date()
    logger.info(f"Số quan sát: {n_obs} tuần, từ {date_min} đến {date_max}")

    # Trích xuất ma trận endogenous (thứ tự cố định, khớp Tầng 3)
    endog = df[ANALYSIS_VARIABLES].values.copy()
    n_vars = len(ANALYSIS_VARIABLES)

    logger.info(f"Ma trận endogenous: {n_obs} × {n_vars} "
                f"({', '.join(ANALYSIS_VARIABLES)})")

    # Log thống kê mô tả nhanh để kiểm tra dữ liệu đầu vào
    for v_idx, var in enumerate(ANALYSIS_VARIABLES):
        col = endog[:, v_idx]
        logger.info(f"  {var}: min={col.min():.4f}, max={col.max():.4f}, "
                     f"mean={col.mean():.4f}, std={col.std():.4f}")

    # ══════════════════════════════════════════════════════════════════
    # PHÂN NHÁNH: VAR routes → xử lý riêng và return sớm
    # ══════════════════════════════════════════════════════════════════
    if route in ("VAR_on_levels", "VAR_on_differences"):
        return _run_var_on_levels(
            endog, df, n_obs, n_vars, selected_lag_from_json,
            route, input_csv, phase3_json, base_dir, start_time, logger
        )

    # ══════════════════════════════════════════════════════════════════
    # BƯỚC 3: Fit VECM với tham số KHÓA CỨNG (chỉ khi route == "VECM")
    # ══════════════════════════════════════════════════════════════════
    # TẠI SAO dùng deterministic='co'?
    # → 'co' = constant outside cointegrating relation = unrestricted constant
    # → Tương ứng det_order=1 đã dùng trong Johansen test Phase 3
    # → Cho phép hằng số trong phương trình VECM (không chỉ trong β'y),
    #   tức E[Δy_t] có thể ≠ 0, tương đương giả định xu hướng tuyến tính
    #   trong mức gốc (levels) — phù hợp với dữ liệu sản xuất thực tế
    #   (OEE, Revenue có thể tăng/giảm theo xu hướng).

    # Tính bậc tự do để cảnh báo trước khi fit:
    # VECM(k_ar_diff=1, r=2, n=4, const=1):
    #   Params/equation = r + n*k_ar_diff + 1 = 2 + 4*1 + 1 = 7
    #   Effective obs ≈ N - k_ar_diff - 1 = 10 - 1 - 1 = 8
    #   DoF ≈ 8 - 7 = 1 (RẤT THẤP — estimates sẽ không ổn định)
    params_per_eq = COINT_RANK + n_vars * K_AR_DIFF + 1
    effective_obs_est = n_obs - K_AR_DIFF - 1
    dof_est = effective_obs_est - params_per_eq

    logger.info(f"Fitting VECM(k_ar_diff={K_AR_DIFF}, coint_rank={COINT_RANK}, "
                f"deterministic='co')...")
    logger.info(f"  Ước tính: {params_per_eq} params/equation, "
                f"~{effective_obs_est} effective obs, ~{dof_est} DoF")

    if dof_est < 5:
        logger.warning(
            f"BẬC TỰ DO ƯỚC TÍNH RẤT THẤP ({dof_est}). "
            f"Ước lượng VECM có thể KHÔNG ỔN ĐỊNH — hệ số và khoảng tin cậy "
            f"cần được diễn giải thận trọng. Đây là hệ quả tất yếu của mẫu "
            f"nhỏ (N={n_obs}), không phải lỗi phương pháp."
        )

    actual_k_ar_diff = K_AR_DIFF
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = VECM(
                endog,
                k_ar_diff=K_AR_DIFF,
                coint_rank=COINT_RANK,
                deterministic="co",
            )
            vecm_result = model.fit()
        logger.info(f"VECM fit thành công với k_ar_diff={K_AR_DIFF}.")

    except Exception as e:
        logger.warning(f"VECM fit thất bại với k_ar_diff={K_AR_DIFF}: {e}")

        # Fallback: thử k_ar_diff từ Phase 3 JSON (=0) khi mẫu quá nhỏ
        # Đây KHÔNG phải "tự động tìm lag" — chỉ là dùng giá trị đã xác định
        # trong Johansen test khi giá trị người dùng yêu cầu không khả thi.
        if K_AR_DIFF != k_ar_diff_from_json:
            logger.warning(
                f"Thử fallback k_ar_diff={k_ar_diff_from_json} "
                f"(giá trị gốc từ Phase 3 Johansen test)..."
            )
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    model = VECM(
                        endog,
                        k_ar_diff=k_ar_diff_from_json,
                        coint_rank=COINT_RANK,
                        deterministic="co",
                    )
                    vecm_result = model.fit()
                actual_k_ar_diff = k_ar_diff_from_json
                logger.info(
                    f"VECM fit thành công với fallback "
                    f"k_ar_diff={k_ar_diff_from_json}."
                )
            except Exception as e2:
                logger.exception(
                    f"VECM fit thất bại cả với "
                    f"k_ar_diff={k_ar_diff_from_json}: {e2}"
                )
                raise
        else:
            logger.exception(f"VECM fit thất bại, không có fallback: {e}")
            raise

    # ══════════════════════════════════════════════════════════════════
    # BƯỚC 4: Trích xuất PHƯƠNG TRÌNH ĐỒNG TÍCH HỢP (Cointegrating Eqs)
    # ══════════════════════════════════════════════════════════════════
    # β (beta): ma trận cointegrating vectors — shape (n_vars, coint_rank)
    #   Mỗi CỘT j là 1 vector đồng tích hợp β_j.
    #   Quan hệ dài hạn: β_j' · y_t ≈ 0 khi hệ thống ở cân bằng.
    #   Ý nghĩa: β_j chỉ ra TỶ LỆ CÂN BẰNG giữa các biến. Nếu β hàng
    #   OEE > 0 và β hàng DelayRate < 0, nghĩa là OEE cao đi kèm Delay thấp
    #   trong dài hạn — một "luật" cân bằng nội tại của hệ thống sản xuất.
    #
    # α (alpha): ma trận loading/adjustment — shape (n_vars, coint_rank)
    #   α[i, j] = tốc độ biến thứ i điều chỉnh về cân bằng thứ j.
    #   Dấu α quyết định HƯỚNG điều chỉnh:
    #     α < 0: biến giảm khi ECT > 0 → error CORRECTING (tự sửa lỗi)
    #     α > 0: biến tăng khi ECT > 0 → error AMPLIFYING (khuếch đại lệch)
    #   |α| quyết định TỐC ĐỘ: |α|=0.5 → điều chỉnh 50% lệch cân bằng/tuần.

    beta = vecm_result.beta    # (n_vars, coint_rank)
    alpha = vecm_result.alpha  # (n_vars, coint_rank)

    logger.info("─" * 60)
    logger.info("PHƯƠNG TRÌNH ĐỒNG TÍCH HỢP (COINTEGRATING EQUATIONS)")
    logger.info("─" * 60)

    coint_equations = []
    for r_idx in range(COINT_RANK):
        beta_r = beta[:, r_idx]
        terms = []
        for v_idx, var_name in enumerate(ANALYSIS_VARIABLES):
            coef = float(beta_r[v_idx])
            terms.append(f"{coef:+.6f}*{var_name}")
        eq_str = " ".join(terms) + " ≈ 0"
        coint_equations.append({
            "index": r_idx + 1,
            "equation": eq_str,
            "coefficients": {
                var: float(beta_r[v_idx])
                for v_idx, var in enumerate(ANALYSIS_VARIABLES)
            },
        })
        logger.info(f"  CE{r_idx + 1}: {eq_str}")

    # ── Tốc độ điều chỉnh α ──
    logger.info("─" * 60)
    logger.info("TỐC ĐỘ ĐIỀU CHỈNH (ADJUSTMENT COEFFICIENTS α)")
    logger.info("─" * 60)

    adjustment_info = {}
    for v_idx, var_name in enumerate(ANALYSIS_VARIABLES):
        alpha_v = [float(alpha[v_idx, r]) for r in range(COINT_RANK)]
        adjustment_info[var_name] = alpha_v
        alpha_str = ", ".join(
            [f"CE{r + 1}: {a:+.6f}" for r, a in enumerate(alpha_v)]
        )
        logger.info(f"  {var_name}: [{alpha_str}]")

        # Diễn giải kinh tế cho từng hệ số α
        for r in range(COINT_RANK):
            a = alpha_v[r]
            if a < -0.1:
                logger.info(
                    f"    → {var_name} phản ứng MẠNH với CE{r + 1} "
                    f"(α={a:.4f} < 0: error correcting — tự điều chỉnh "
                    f"về cân bằng)"
                )
            elif a > 0.1:
                logger.info(
                    f"    → {var_name} KHUẾCH ĐẠI lệch CE{r + 1} "
                    f"(α={a:.4f} > 0: error amplifying — đẩy xa khỏi "
                    f"cân bằng)"
                )
            else:
                logger.info(
                    f"    → {var_name} gần như KHÔNG phản ứng với CE{r + 1} "
                    f"(|α|={abs(a):.4f} ≈ 0: weakly exogenous)"
                )

    # ══════════════════════════════════════════════════════════════════
    # BƯỚC 5: Trích xuất HỆ SỐ NGẮN HẠN (Short-run Dynamics Γ)
    # ══════════════════════════════════════════════════════════════════
    # vecm_result.gamma: ma trận Γ stacked, shape (n_vars * k_ar_diff, n_vars)
    # Mỗi block Γ_i (n_vars × n_vars) mô tả tác động của Δy_{t-i} lên Δy_t.
    #
    # TẠI SAO short-run dynamics quan trọng?
    # → Γ nắm bắt QUÁN TÍNH ngắn hạn: ví dụ nếu Γ[OEE, DelayRate] < 0,
    #   nghĩa là tăng Delay tuần trước → OEE tuần này giảm (tác động trễ 1 tuần).
    #   Đây là thông tin KHÁC với quan hệ dài hạn (β) — một biến có thể
    #   không liên quan dài hạn nhưng tác động ngắn hạn mạnh.

    gamma_info = {}
    if actual_k_ar_diff > 0:
        gamma = vecm_result.gamma  # (n_vars * k_ar_diff, n_vars)

        logger.info("─" * 60)
        logger.info("HỆ SỐ NGẮN HẠN (SHORT-RUN DYNAMICS Γ)")
        logger.info("─" * 60)

        for lag in range(actual_k_ar_diff):
            gamma_lag = gamma[lag * n_vars: (lag + 1) * n_vars, :]
            gamma_info[f"Gamma_{lag + 1}"] = _matrix_to_list(gamma_lag)
            logger.info(
                f"  Γ_{lag + 1} — tác động của Δy_{{t-{lag + 1}}} lên Δy_t:"
            )
            for v_idx, var_name in enumerate(ANALYSIS_VARIABLES):
                row_str = "  ".join(
                    [f"{gamma_lag[v_idx, j]:+.6f}" for j in range(n_vars)]
                )
                logger.info(f"    {var_name}: [{row_str}]")
    else:
        logger.info(
            "k_ar_diff=0 → không có hệ số Γ (mô hình chỉ có error correction "
            "term + constant)."
        )

    # ══════════════════════════════════════════════════════════════════
    # BƯỚC 6: Dự báo h = 4 bước (4 tuần tiếp theo)
    # ══════════════════════════════════════════════════════════════════
    # predict(steps=h) trả về dự báo ở LEVELS (mức gốc), không phải sai phân.
    # Cơ chế: VECM nội bộ tích lũy (cumulate) các Δy dự báo lên mức cuối cùng
    # đã quan sát y_T để ra y_{T+1}, ..., y_{T+h}.

    logger.info("─" * 60)
    logger.info(f"DỰ BÁO {FORECAST_HORIZON} BƯỚC (TUẦN)")
    logger.info("─" * 60)

    try:
        forecast = vecm_result.predict(steps=FORECAST_HORIZON)
        logger.info(f"Dự báo thành công: shape={forecast.shape}")
    except Exception as e:
        logger.exception(f"Dự báo thất bại: {e}")
        raise

    # ══════════════════════════════════════════════════════════════════
    # BƯỚC 7: Tính khoảng tin cậy 95%
    # ══════════════════════════════════════════════════════════════════
    lower, upper, se, ci_method = _compute_forecast_ci(
        vecm_result, forecast, n_vars, FORECAST_HORIZON, logger
    )

    # ══════════════════════════════════════════════════════════════════
    # BƯỚC 8: Tạo ngày dự báo và DataFrame kết quả
    # ══════════════════════════════════════════════════════════════════
    last_date = df["week_start"].max()
    future_dates = [
        last_date + timedelta(weeks=i + 1)
        for i in range(FORECAST_HORIZON)
    ]

    logger.info("─" * 60)
    logger.info("KẾT QUẢ DỰ BÁO (Point Forecast ± 95% CI)")
    logger.info("─" * 60)

    forecast_records = []
    for h_idx in range(FORECAST_HORIZON):
        record = {"week_start": future_dates[h_idx].strftime("%Y-%m-%d")}
        for v_idx, var in enumerate(ANALYSIS_VARIABLES):
            fc = float(forecast[h_idx, v_idx])
            lo = float(lower[h_idx, v_idx])
            hi = float(upper[h_idx, v_idx])
            record[f"{var}_forecast"] = fc
            record[f"{var}_lower_95"] = lo
            record[f"{var}_upper_95"] = hi

        forecast_records.append(record)

        logger.info(f"  Tuần {future_dates[h_idx].date()} (T+{h_idx + 1}):")
        for v_idx, var in enumerate(ANALYSIS_VARIABLES):
            fc = float(forecast[h_idx, v_idx])
            lo = float(lower[h_idx, v_idx])
            hi = float(upper[h_idx, v_idx])
            logger.info(f"    {var:15s}: {fc:>12.4f}  [{lo:>12.4f}, {hi:>12.4f}]")

    forecast_df = pd.DataFrame(forecast_records)

    # ══════════════════════════════════════════════════════════════════
    # BƯỚC 9: Lưu kết quả ra file
    # ══════════════════════════════════════════════════════════════════

    # ── 9a. CSV dự báo → reports/forecasts/ ──
    forecast_dir = os.path.join(base_dir, "reports", "forecasts")
    os.makedirs(forecast_dir, exist_ok=True)

    forecast_csv_path = os.path.join(forecast_dir, "vecm_forecast.csv")
    forecast_df.to_csv(forecast_csv_path, index=False)
    logger.info(f"Đã lưu dự báo CSV: {forecast_csv_path}")

    # ── 9b. JSON chi tiết mô hình → reports/ ──
    sigma_u = vecm_result.sigma_u

    # Log-likelihood (nếu có)
    try:
        llf = float(vecm_result.llf)
    except Exception:
        llf = None

    # Effective observations và DoF thực tế sau fit
    try:
        effective_obs_actual = int(vecm_result.nobs)
    except Exception:
        effective_obs_actual = effective_obs_est

    dof_actual = effective_obs_actual - params_per_eq

    # AIC/BIC tính thủ công: AIC = -2*llf + 2*k, BIC = -2*llf + ln(N)*k
    total_params = n_vars * params_per_eq
    if llf is not None:
        aic = float(-2.0 * llf + 2.0 * total_params)
        bic = float(-2.0 * llf + np.log(effective_obs_actual) * total_params)
    else:
        aic = None
        bic = None

    # ── Tập hợp output JSON ──
    output = {
        "metadata": {
            "script": "tang4_vecm_forecasting.py",
            "timestamp": datetime.now().isoformat(),
            "input_csv": os.path.relpath(input_csv, base_dir),
            "phase3_json": os.path.relpath(phase3_json, base_dir),
            "n_observations": n_obs,
            "forecast_horizon": FORECAST_HORIZON,
            "confidence_level": CONFIDENCE_LEVEL,
            "ci_method": ci_method,
            "variables": ANALYSIS_VARIABLES,
        },
        "locked_parameters": {
            "coint_rank": COINT_RANK,
            "k_ar_diff": actual_k_ar_diff,
            "k_ar_diff_from_phase3_json": k_ar_diff_from_json,
            "selected_lag_from_phase3_json": selected_lag_from_json,
            "k_ar_diff_note": (
                f"VAR lag p={selected_lag_from_json} → VECM k_ar_diff = "
                f"p-1 = {k_ar_diff_from_json}. Giá trị đọc từ Phase 3 JSON."
            ),
            "deterministic": "co",
            "deterministic_description": (
                "Unrestricted constant — constant outside cointegrating "
                "relation (Lütkepohl 2005). Tương ứng det_order=1 "
                "trong Johansen test Phase 3."
            ),
        },
        "cointegrating_equations": {
            "description": (
                f"r = {COINT_RANK} vector đồng tích hợp. "
                f"β'·y_t ≈ 0 khi hệ thống ở cân bằng dài hạn."
            ),
            "beta": _matrix_to_list(beta),
            "beta_row_labels": ANALYSIS_VARIABLES,
            "beta_col_labels": [f"CE{i + 1}" for i in range(COINT_RANK)],
            "alpha": _matrix_to_list(alpha),
            "alpha_row_labels": ANALYSIS_VARIABLES,
            "alpha_col_labels": [f"CE{i + 1}" for i in range(COINT_RANK)],
            "equations": coint_equations,
            "adjustment_speeds": adjustment_info,
        },
        "short_run_dynamics": gamma_info,
        "model_diagnostics": {
            "sigma_u": _matrix_to_list(sigma_u),
            "sigma_u_description": (
                "Ma trận hiệp phương sai innovation (n × n). "
                "Đường chéo = variance sai số từng biến."
            ),
            "log_likelihood": _safe_float(llf),
            "aic": _safe_float(aic),
            "bic": _safe_float(bic),
            "effective_observations": effective_obs_actual,
            "degrees_of_freedom_per_equation": dof_actual,
            "total_parameters": total_params,
        },
        "forecast": {
            "dates": [d.strftime("%Y-%m-%d") for d in future_dates],
            "point_forecasts": {
                var: [float(forecast[h, v_idx])
                      for h in range(FORECAST_HORIZON)]
                for v_idx, var in enumerate(ANALYSIS_VARIABLES)
            },
            "lower_95": {
                var: [float(lower[h, v_idx])
                      for h in range(FORECAST_HORIZON)]
                for v_idx, var in enumerate(ANALYSIS_VARIABLES)
            },
            "upper_95": {
                var: [float(upper[h, v_idx])
                      for h in range(FORECAST_HORIZON)]
                for v_idx, var in enumerate(ANALYSIS_VARIABLES)
            },
            "standard_errors": {
                var: [float(se[h, v_idx])
                      for h in range(FORECAST_HORIZON)]
                for v_idx, var in enumerate(ANALYSIS_VARIABLES)
            },
        },
        "warnings": [],
    }

    # ── Thêm cảnh báo nếu cần ──
    if dof_actual < 5:
        output["warnings"].append(
            f"Bậc tự do rất thấp ({dof_actual}/equation). Ước lượng hệ số "
            f"có thể không ổn định — diễn giải thận trọng."
        )
    if n_obs < 30:
        output["warnings"].append(
            f"Mẫu nhỏ ({n_obs} tuần < 30 khuyến nghị tối thiểu). Khoảng "
            f"tin cậy có thể đánh giá THẤP hơn độ bất định thực tế."
        )
    if actual_k_ar_diff != K_AR_DIFF:
        output["warnings"].append(
            f"Đã fallback từ k_ar_diff={K_AR_DIFF} (user request) sang "
            f"k_ar_diff={actual_k_ar_diff} (Phase 3 JSON) do mẫu quá nhỏ "
            f"cho cấu hình ban đầu."
        )

    # Kiểm tra giá trị dự báo ngoài phạm vi hợp lệ
    for v_idx, var in enumerate(ANALYSIS_VARIABLES):
        for h_idx in range(FORECAST_HORIZON):
            fc = float(forecast[h_idx, v_idx])
            if var in ("OEE_Score", "DelayRate") and (fc < 0 or fc > 1):
                output["warnings"].append(
                    f"{var} T+{h_idx + 1} = {fc:.4f}: ngoài [0, 1]. "
                    f"VECM không ràng buộc biên — cần diễn giải cẩn thận."
                )
            if var in ("Revenue", "OrderVolume") and fc < 0:
                output["warnings"].append(
                    f"{var} T+{h_idx + 1} = {fc:.4f}: âm (vô nghĩa kinh tế). "
                    f"Mô hình tuyến tính không ràng buộc phi âm."
                )

    if output["warnings"]:
        logger.warning(f"Có {len(output['warnings'])} cảnh báo:")
        for w in output["warnings"]:
            logger.warning(f"  ⚠ {w}")

    json_path = os.path.join(base_dir, "reports", "tang4_vecm_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    logger.info(f"Đã lưu JSON chi tiết: {json_path}")

    # ══════════════════════════════════════════════════════════════════
    # TỔNG KẾT
    # ══════════════════════════════════════════════════════════════════
    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info("=" * 70)
    logger.info(f"TẦNG 4 — VECM FORECASTING HOÀN TẤT trong {elapsed:.1f}s")
    logger.info(f"  Mô hình: VECM(k_ar_diff={actual_k_ar_diff}, "
                f"coint_rank={COINT_RANK}, det='co')")
    logger.info(f"  Dự báo:  {FORECAST_HORIZON} tuần "
                f"({future_dates[0].date()} → {future_dates[-1].date()})")
    logger.info(f"  Output CSV:  {forecast_csv_path}")
    logger.info(f"  Output JSON: {json_path}")
    if output["warnings"]:
        logger.info(f"  Cảnh báo: {len(output['warnings'])}")
    logger.info("=" * 70)

    return {
        "forecast_csv": forecast_csv_path,
        "results_json": json_path,
        "forecast_df": forecast_df,
        "vecm_result": vecm_result,
    }


# ══════════════════════════════════════════════════════════════════════
# Entry point: chạy độc lập bằng `python tang4_vecm_forecasting.py`
# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    run_tang4()
