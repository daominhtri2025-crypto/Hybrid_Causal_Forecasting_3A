"""
Tầng 3 — Phase 1: Kiểm định tính dừng (Stationarity Testing).

Mục đích:
    Xác định bậc tích hợp d(i) riêng cho TỪNG biến trong hệ thống nhân quả
    bằng phương pháp kiểm định kép ADF + KPSS (dual confirmation strategy,
    theo Pfaff 2008, "Analysis of Integrated and Cointegrated Time Series
    with R"). Kết quả d(i) là INPUT BẮT BUỘC cho Phase 2 (Granger — cần
    sai phân đúng bậc), Phase 3 (Johansen — yêu cầu I(1)), và Phase 3b
    (Toda-Yamamoto — cần d_max).

    Phương pháp kiểm định kép (TẠI SAO dùng cả ADF lẫn KPSS):
      - ADF (Augmented Dickey-Fuller):
          H0: chuỗi có nghiệm đơn vị (unit root) → KHÔNG dừng
          → Bác bỏ H0 (p < α) ⟹ kết luận chuỗi DỪNG.
      - KPSS (Kwiatkowski-Phillips-Schmidt-Shin):
          H0: chuỗi DỪNG (stationary)
          → Bác bỏ H0 (p < α) ⟹ kết luận chuỗi KHÔNG dừng.
      - Hai kiểm định có giả thuyết H0 NGƯỢC nhau → kết hợp giảm rủi ro
        kết luận sai do Type I / Type II error của một kiểm định đơn lẻ.

    Ma trận quyết định kết hợp ADF + KPSS:
      ┌──────────────┬─────────────┬──────────────────────────┐
      │              │ KPSS giữ H0 │ KPSS bác bỏ H0           │
      │              │ (dừng)      │ (không dừng)              │
      ├──────────────┼─────────────┼──────────────────────────┤
      │ ADF bác bỏ   │ ✅ XÁC NHẬN │ ⚠ Mâu thuẫn              │
      │ H0 (dừng)    │   DỪNG      │ (có thể dừng quanh trend)│
      ├──────────────┼─────────────┼──────────────────────────┤
      │ ADF giữ H0   │ ❓ Không     │ ✅ XÁC NHẬN              │
      │ (ko dừng)    │ kết luận    │   KHÔNG DỪNG             │
      └──────────────┴─────────────┴──────────────────────────┘

    Bậc tích hợp d(i) được xác định bằng cách sai phân tuần tự: nếu chuỗi
    gốc (level) không dừng → sai phân bậc 1 → kiểm định lại → nếu vẫn
    không dừng → sai phân bậc 2 → kiểm định lại. Chuỗi kinh tế hiếm khi
    cần d > 2 (Enders, 2014).

Input:  `data/processed/causal_weekly_dataset.csv` (output của Phase 0).
Output: `reports/phase1_stationarity.json` — chứa d(i) từng biến, toàn bộ
        thống kê kiểm định, và kết quả phân tích độ nhạy.

Sở hữu: Role B — Econometrics & Causality Analysis (skill.md).
Tuân thủ: CLAUDE.md mục 3 (coding), mục 7 (logging), mục 5 (scientific integrity).
"""

import json
import os
import sys
import warnings
from datetime import datetime

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller, kpss, zivot_andrews

from scripts.utils import get_logger, get_base_dir

logger = get_logger("phase1")


# =====================================================================
# HẰNG SỐ CẤU HÌNH
# =====================================================================

# Mức ý nghĩa thống kê α = 0.05 — tiêu chuẩn phổ biến trong kinh tế
# lượng và khoa học xã hội (Fisher, 1925). Ngưỡng này cân bằng giữa rủi
# ro Type I (bác bỏ nhầm H0) và Type II (giữ nhầm H0).
SIGNIFICANCE_LEVEL = 0.05

# Bốn biến phân tích trong hệ thống nhân quả — đúng theo output Phase 0
ANALYSIS_VARS = ["OEE_Score", "DelayRate", "Revenue", "OrderVolume"]

# Số quan sát tối thiểu để kiểm định ADF/KPSS cho kết quả đáng tin cậy.
# Với ít hơn 8 quan sát, power của kiểm định quá thấp để kết luận có ý
# nghĩa — vẫn chạy nhưng gắn cờ cảnh báo.
MIN_OBS_STATIONARITY = 8

# Bậc sai phân tối đa d_max = 2 — chuỗi kinh tế thực nghiệm hiếm khi
# cần sai phân hơn 2 lần (Enders, "Applied Econometric Time Series", 2014).
MAX_INTEGRATION_ORDER = 2

# Ngưỡng cảnh báo mẫu nhỏ — nếu T < giá trị này, ghi WARNING rõ ràng
# rằng kết quả cần được diễn giải thận trọng.
RECOMMENDED_MIN_OBS = 30


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


def _safe_dict(d):
    """Chuyển đổi toàn bộ giá trị trong dict sang kiểu Python native."""
    return {str(k): _safe_float(v) for k, v in d.items()}


# =====================================================================
# KIỂM ĐỊNH ADF (Augmented Dickey-Fuller)
# =====================================================================

def _run_adf_test(series, var_name, diff_label="level"):
    """
    Chạy kiểm định ADF trên chuỗi thời gian.

    Tham số:
        series: pd.Series — chuỗi cần kiểm định (đã sai phân nếu cần).
        var_name: str — tên biến (dùng cho logging).
        diff_label: str — mô tả bậc sai phân ("level", "first_diff", "second_diff").

    Trả về:
        dict chứa test statistic, p-value, số lag đã dùng, giá trị tới hạn,
        và kết luận bác bỏ/giữ H0.

    Lý do dùng regression='c' (constant, không có trend):
        Các biến trong pipeline này (OEE_Score, DelayRate, Revenue, OrderVolume)
        dao động quanh mức trung bình, không có xu hướng tuyến tính rõ ràng
        trong dữ liệu tuần ngắn hạn. Nếu có trend, ADF với 'c' sẽ thiên
        về kết luận "không dừng" — đây là hướng bảo thủ (an toàn hơn so với
        bỏ sót unit root).

    Lý do dùng autolag='AIC':
        AIC (Akaike Information Criterion) tự động chọn số lag phù hợp để
        loại bỏ tự tương quan trong phần dư, tránh cả 2 rủi ro: quá ít lag
        (phần dư còn tự tương quan → test sai) và quá nhiều lag (mất bậc tự
        do → giảm power).
    """
    # Loại bỏ NaN trước khi chạy kiểm định
    clean = series.dropna()

    if len(clean) < 3:
        logger.warning(
            f"[ADF] {var_name} ({diff_label}): chỉ còn {len(clean)} quan sát "
            f"sau khi loại NaN — KHÔNG ĐỦ để chạy ADF (tối thiểu 3). Bỏ qua."
        )
        return None

    try:
        result = adfuller(clean, regression="c", autolag="AIC")
        adf_stat, p_value, lags_used, nobs, crit_values, ic_best = result

        reject_h0 = p_value < SIGNIFICANCE_LEVEL

        logger.info(
            f"[ADF] {var_name} ({diff_label}): statistic={adf_stat:.4f}, "
            f"p-value={p_value:.4f}, lags={lags_used}, n_eff={nobs} "
            f"→ {'BÁC BỎ' if reject_h0 else 'GIỮ'} H0 (unit root) "
            f"tại α={SIGNIFICANCE_LEVEL}"
        )

        return {
            "statistic": _safe_float(adf_stat),
            "p_value": _safe_float(p_value),
            "lags_used": int(lags_used),
            "n_obs_effective": int(nobs),
            "critical_values": _safe_dict(crit_values),
            "ic_best": _safe_float(ic_best),
            "reject_h0": bool(reject_h0),
            "interpretation": "dừng (stationary)" if reject_h0
                              else "không dừng (non-stationary)",
            # Lưu chuỗi gốc để _dual_confirmation có thể truyền cho
            # Zivot-Andrews khi cần tiebreaker (không serialize vào JSON)
            "series_used": clean,
        }

    except Exception as e:
        logger.warning(
            f"[ADF] {var_name} ({diff_label}): kiểm định thất bại — {e}. "
            f"Có thể do chuỗi quá ngắn ({len(clean)} quan sát) hoặc phương "
            f"sai bằng 0."
        )
        return None


# =====================================================================
# KIỂM ĐỊNH KPSS (Kwiatkowski-Phillips-Schmidt-Shin)
# =====================================================================

def _run_kpss_test(series, var_name, diff_label="level"):
    """
    Chạy kiểm định KPSS trên chuỗi thời gian.

    Tham số:
        series: pd.Series — chuỗi cần kiểm định.
        var_name: str — tên biến (dùng cho logging).
        diff_label: str — mô tả bậc sai phân.

    Trả về:
        dict chứa test statistic, p-value, giá trị tới hạn, kết luận.

    Lý do dùng regression='c' (level stationarity):
        Nhất quán với ADF (cũng dùng 'c'). Kiểm định KPSS với 'c' kiểm tra
        xem chuỗi có dừng quanh một hằng số (level) hay không — phù hợp với
        dữ liệu kinh tế ngắn hạn không có trend xác định.

    Xử lý nlags:
        Dùng 'auto' (công thức Schwert 1989) nhưng giới hạn trên để tránh
        trường hợp mẫu nhỏ bị chọn quá nhiều lag (làm cạn bậc tự do).
    """
    clean = series.dropna()

    if len(clean) < 3:
        logger.warning(
            f"[KPSS] {var_name} ({diff_label}): chỉ còn {len(clean)} quan "
            f"sát — KHÔNG ĐỦ để chạy KPSS. Bỏ qua."
        )
        return None

    try:
        # Tắt InterpolationWarning của KPSS (xảy ra khi test statistic nằm
        # ngoài bảng giá trị tới hạn — p-value bị ngoại suy). Vẫn ghi nhận
        # kết quả, chỉ tắt warning console để không nhiễu log.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")

            # Giới hạn nlags tối đa = T//3 để tránh cạn bậc tự do với mẫu nhỏ
            max_lags = max(1, len(clean) // 3)
            result = kpss(clean, regression="c", nlags=max_lags)

        kpss_stat, p_value, lags_used, crit_values = result

        reject_h0 = p_value < SIGNIFICANCE_LEVEL

        logger.info(
            f"[KPSS] {var_name} ({diff_label}): statistic={kpss_stat:.4f}, "
            f"p-value={p_value:.4f}, lags={lags_used} "
            f"→ {'BÁC BỎ' if reject_h0 else 'GIỮ'} H0 (dừng) "
            f"tại α={SIGNIFICANCE_LEVEL}"
        )

        return {
            "statistic": _safe_float(kpss_stat),
            "p_value": _safe_float(p_value),
            "lags_used": int(lags_used),
            "critical_values": _safe_dict(crit_values),
            "reject_h0": bool(reject_h0),
            "interpretation": "không dừng (non-stationary)" if reject_h0
                              else "dừng (stationary)"
        }

    except Exception as e:
        logger.warning(
            f"[KPSS] {var_name} ({diff_label}): kiểm định thất bại — {e}."
        )
        return None


# =====================================================================
# KẾT HỢP ADF + KPSS (DUAL CONFIRMATION)
# =====================================================================

def _dual_confirmation(adf_result, kpss_result, var_name, diff_label):
    """
    Kết hợp kết quả ADF + KPSS theo ma trận quyết định kép.

    TẠI SAO cần kết hợp 2 kiểm định thay vì chỉ dùng ADF:
        - ADF có power thấp (dễ giữ nhầm H0) khi mẫu nhỏ hoặc chuỗi gần
          ranh giới dừng/không dừng → hay kết luận "không dừng" dù chuỗi
          thực sự dừng (Type II error cao).
        - KPSS bổ sung bằng cách ĐẢO giả thuyết → nếu cả 2 đồng thuận,
          kết luận đáng tin cậy hơn nhiều so với dùng 1 kiểm định đơn lẻ.

    Trả về:
        str — "stationary", "non_stationary", "contradictory", hoặc
        "inconclusive" (với giải thích cụ thể trong log).
    """
    # Trường hợp một hoặc cả hai kiểm định thất bại (mẫu quá nhỏ)
    if adf_result is None and kpss_result is None:
        logger.warning(
            f"{var_name} ({diff_label}): CẢ HAI kiểm định ADF+KPSS đều "
            f"thất bại — không thể xác định tính dừng."
        )
        return "test_failed"

    if adf_result is None:
        # Chỉ có KPSS — dùng kết quả đơn lẻ với cảnh báo
        conclusion = "stationary" if not kpss_result["reject_h0"] else "non_stationary"
        logger.warning(
            f"{var_name} ({diff_label}): ADF thất bại, chỉ dùng KPSS → "
            f"kết luận tạm: {conclusion} (ĐỘ TIN CẬY THẤP)."
        )
        return conclusion

    if kpss_result is None:
        conclusion = "stationary" if adf_result["reject_h0"] else "non_stationary"
        logger.warning(
            f"{var_name} ({diff_label}): KPSS thất bại, chỉ dùng ADF → "
            f"kết luận tạm: {conclusion} (ĐỘ TIN CẬY THẤP)."
        )
        return conclusion

    # Cả hai kiểm định đều chạy thành công — áp dụng ma trận quyết định
    adf_rejects = adf_result["reject_h0"]     # ADF bác bỏ → chuỗi dừng
    kpss_rejects = kpss_result["reject_h0"]   # KPSS bác bỏ → chuỗi KHÔNG dừng

    if adf_rejects and not kpss_rejects:
        # Case 1: ADF nói "dừng" + KPSS nói "dừng" → XÁC NHẬN DỪNG
        logger.info(
            f"{var_name} ({diff_label}): ✓ Dual confirmation → DỪNG "
            f"(ADF bác bỏ unit root, KPSS giữ stationarity)."
        )
        return "stationary"

    elif not adf_rejects and kpss_rejects:
        # Case 2: ADF nói "không dừng" + KPSS nói "không dừng" → XÁC NHẬN KHÔNG DỪNG
        logger.info(
            f"{var_name} ({diff_label}): ✓ Dual confirmation → KHÔNG DỪNG "
            f"(ADF giữ unit root, KPSS bác bỏ stationarity)."
        )
        return "non_stationary"

    elif adf_rejects and kpss_rejects:
        # Case 3: Mâu thuẫn — ADF nói "dừng" nhưng KPSS cũng bác bỏ "dừng"
        # Thường xảy ra khi chuỗi dừng quanh một xu hướng (trend-stationary)
        # hoặc có structural break. Dùng Zivot-Andrews (1992) làm tiebreaker:
        # ZA cho phép 1 structural break nội sinh → nếu ZA bác bỏ H0 (unit
        # root), kết luận chuỗi dừng quanh break → "stationary".
        # Nếu ZA không bác bỏ → giữ "contradictory", tạm xử lý như dừng.
        logger.warning(
            f"{var_name} ({diff_label}): ⚠ KẾT QUẢ MÂU THUẪN — ADF bác bỏ "
            f"unit root nhưng KPSS cũng bác bỏ stationarity. Chạy Zivot-Andrews "
            f"làm tiebreaker (kiểm tra structural break)..."
        )
        try:
            za_result = zivot_andrews(
                adf_result["series_used"], maxlag=None, regression="c", autolag="AIC"
            )
            za_stat = float(za_result[0])
            za_pvalue = float(za_result[1])
            za_breakpoint = int(za_result[4])
            za_rejects = za_pvalue < SIGNIFICANCE_LEVEL

            logger.info(
                f"{var_name} ({diff_label}): Zivot-Andrews — "
                f"stat={za_stat:.4f}, p={za_pvalue:.4f}, "
                f"breakpoint tại index {za_breakpoint}. "
                f"{'Bác bỏ' if za_rejects else 'Giữ'} H0 (unit root)."
            )

            if za_rejects:
                logger.info(
                    f"{var_name} ({diff_label}): ZA xác nhận DỪNG (có "
                    f"structural break) → kết luận 'stationary'."
                )
                return "stationary"
            else:
                logger.warning(
                    f"{var_name} ({diff_label}): ZA không bác bỏ unit root → "
                    f"giữ 'contradictory', tạm xử lý như 'dừng' (bảo thủ — "
                    f"ưu tiên ADF vì Johansen yêu cầu I(1))."
                )
                return "contradictory"
        except Exception as e:
            # ZA thất bại (mẫu quá nhỏ, hoặc lỗi hội tụ) → fallback
            logger.warning(
                f"{var_name} ({diff_label}): Zivot-Andrews thất bại ({e}) — "
                f"fallback về 'contradictory', tạm xử lý như 'dừng'."
            )
            return "contradictory"

    else:
        # Case 4: Cả hai đều không bác bỏ — không đủ bằng chứng kết luận
        # Thường do power thấp (mẫu nhỏ).
        logger.warning(
            f"{var_name} ({diff_label}): ❓ KHÔNG KẾT LUẬN — ADF giữ H0 "
            f"(unit root) nhưng KPSS cũng giữ H0 (dừng). Thường xảy ra khi "
            f"mẫu quá nhỏ, power của cả 2 kiểm định đều thấp. Tạm xử lý "
            f"như 'không dừng' (bảo thủ — sẽ sai phân thêm)."
        )
        return "inconclusive"


# =====================================================================
# XÁC ĐỊNH BẬC TÍCH HỢP d(i)
# =====================================================================

def _find_integration_order(series, var_name):
    """
    Tìm bậc tích hợp d(i) cho một biến bằng sai phân tuần tự.

    Quy trình:
        1. Kiểm định chuỗi gốc (level) bằng ADF+KPSS.
        2. Nếu dừng → d = 0.
        3. Nếu không dừng → sai phân bậc 1, kiểm định lại.
        4. Nếu vẫn không dừng → sai phân bậc 2, kiểm định lại.
        5. Nếu d > 2 mà vẫn không dừng → ghi ERROR, gán d = 2 (giới hạn
           thực tiễn, vì I(3)+ rất hiếm trong dữ liệu kinh tế).

    TẠI SAO sai phân tuần tự thay vì chọn d trước:
        Sai phân (differencing) loại bỏ xu hướng ngẫu nhiên (stochastic
        trend) trong chuỗi, nhưng sai phân QUÁ nhiều tạo thêm nhiễu
        (overdifferencing). Quy trình tuần tự đảm bảo tìm d TỐI THIỂU
        cần thiết để chuỗi dừng.

    Trả về:
        dict {
            "integration_order": int,   # d(i) = 0, 1, hoặc 2
            "tests": {...},             # kết quả kiểm định từng bậc
            "determination_method": str
        }
    """
    result = {
        "integration_order": None,
        "tests": {},
        "determination_method": "ADF+KPSS dual confirmation (Pfaff, 2008)"
    }

    diff_labels = ["level", "first_diff", "second_diff"]
    current_series = series.copy()

    for d in range(MAX_INTEGRATION_ORDER + 1):
        diff_label = diff_labels[d]

        if d > 0:
            # Sai phân bậc d: Δ^d(x_t) = Δ^(d-1)(x_t) - Δ^(d-1)(x_{t-1})
            # Mỗi lần sai phân mất 1 quan sát → chuỗi ngắn dần
            current_series = current_series.diff().dropna()
            logger.info(
                f"{var_name}: sai phân bậc {d}, còn {len(current_series)} "
                f"quan sát."
            )

        if len(current_series.dropna()) < 3:
            logger.warning(
                f"{var_name} ({diff_label}): chỉ còn {len(current_series)} "
                f"quan sát sau sai phân bậc {d} — không đủ để kiểm định. "
                f"Gán d({var_name}) = {d} theo mặc định."
            )
            result["integration_order"] = d
            break

        # Chạy cả 2 kiểm định
        adf_res = _run_adf_test(current_series, var_name, diff_label)
        kpss_res = _run_kpss_test(current_series, var_name, diff_label)

        # Kết hợp theo ma trận quyết định kép
        conclusion = _dual_confirmation(adf_res, kpss_res, var_name, diff_label)

        result["tests"][diff_label] = {
            "adf": adf_res,
            "kpss": kpss_res,
            "conclusion": conclusion,
            "n_observations": len(current_series.dropna())
        }

        # Nếu dừng (hoặc mâu thuẫn — tạm coi như dừng) → d(i) = d hiện tại
        if conclusion in ("stationary", "contradictory"):
            result["integration_order"] = d
            logger.info(
                f"{var_name}: bậc tích hợp d({var_name}) = {d} "
                f"({'I(0) — dừng tại mức' if d == 0 else f'I({d}) — cần sai phân {d} lần'})."
            )
            break

        # Nếu hết bậc sai phân cho phép mà vẫn không dừng
        if d == MAX_INTEGRATION_ORDER:
            result["integration_order"] = d
            logger.warning(
                f"{var_name}: vẫn KHÔNG DỪNG sau sai phân bậc {d}. "
                f"Gán d({var_name}) = {d} (giới hạn thực tiễn). Cần kiểm tra "
                f"lại dữ liệu — có thể có structural break hoặc outlier."
            )

    return result


# =====================================================================
# PHÂN TÍCH ĐỘ NHẠY (SENSITIVITY ANALYSIS)
# =====================================================================

def _run_sensitivity_analysis(df, full_results):
    """
    Phân tích độ nhạy: loại bỏ tuần có giá trị nội suy, chạy lại kiểm định.

    TẠI SAO cần phân tích độ nhạy:
        Nội suy (interpolation) ở Phase 0 tạo ra dữ liệu "nhân tạo" — các
        giá trị này KHÔNG phải quan sát thực mà được suy ra từ các tuần lân
        cận. Nếu kết luận tính dừng thay đổi khi loại tuần nội suy, nghĩa
        là kết luận PHỤTHUỘC vào bước nội suy → cần thận trọng khi diễn giải.

    Quy trình:
        1. Xác định tuần có BẤT KỲ cột is_interpolated nào = True.
        2. Loại các tuần đó → tạo dataset "sạch".
        3. Chạy lại _find_integration_order trên dataset sạch.
        4. So sánh d(i) giữa 2 lần chạy → ghi WARNING nếu khác.
    """
    # Xác định tuần nội suy (bất kỳ biến nào bị nội suy)
    interp_cols = [c for c in df.columns if c.startswith("is_interpolated")]
    if not interp_cols:
        logger.info("Không tìm thấy cột is_interpolated — bỏ qua sensitivity analysis.")
        return None

    # Tạo mask: True nếu tuần đó có BẤT KỲ giá trị nào bị nội suy
    any_interpolated = df[interp_cols].any(axis=1)
    excluded_weeks = df.loc[any_interpolated, "week_start"].tolist()
    n_excluded = int(any_interpolated.sum())

    if n_excluded == 0:
        logger.info("Không có tuần nào bị nội suy — sensitivity analysis không cần thiết.")
        return {
            "description": "Không có tuần nội suy — kết quả giống hoàn toàn.",
            "excluded_weeks": [],
            "n_observations_clean": len(df),
            "discrepancies": []
        }

    df_clean = df.loc[~any_interpolated].copy()
    n_clean = len(df_clean)

    logger.info(
        f"Sensitivity analysis: loại {n_excluded} tuần nội suy "
        f"({', '.join(str(w) for w in excluded_weeks)}), "
        f"còn {n_clean} tuần 'sạch'."
    )

    if n_clean < MIN_OBS_STATIONARITY:
        logger.warning(
            f"Sensitivity analysis: chỉ còn {n_clean} tuần sau khi loại nội suy "
            f"(< {MIN_OBS_STATIONARITY} tối thiểu). Kết quả sensitivity có "
            f"ĐỘ TIN CẬY RẤT THẤP — chỉ mang tính tham khảo."
        )

    # Chạy lại kiểm định trên dataset sạch
    sensitivity_results = {}
    discrepancies = []

    for var in ANALYSIS_VARS:
        if var not in df_clean.columns:
            continue

        clean_series = df_clean[var].copy()
        clean_var_result = _find_integration_order(clean_series, f"{var}_clean")
        sensitivity_results[var] = clean_var_result

        # So sánh d(i) giữa full và clean
        full_d = full_results[var]["integration_order"]
        clean_d = clean_var_result["integration_order"]

        if full_d != clean_d:
            discrepancy = {
                "variable": var,
                "d_full_dataset": full_d,
                "d_clean_dataset": clean_d,
                "warning": (
                    f"Bậc tích hợp d({var}) thay đổi từ {full_d} (đầy đủ) "
                    f"sang {clean_d} (loại nội suy). Kết luận tính dừng CÓ "
                    f"THỂ PHỤ THUỘC vào bước nội suy ở Phase 0."
                )
            }
            discrepancies.append(discrepancy)
            logger.warning(
                f"⚠ SENSITIVITY: d({var}) thay đổi {full_d} → {clean_d} "
                f"khi loại tuần nội suy!"
            )

    if not discrepancies:
        logger.info(
            "Sensitivity analysis: d(i) KHÔNG thay đổi khi loại tuần nội "
            "suy — kết luận ổn định (robust)."
        )

    return {
        "description": "So sánh kiểm định tính dừng giữa dataset đầy đủ và dataset loại tuần nội suy.",
        "excluded_weeks": [str(w) for w in excluded_weeks],
        "n_excluded": n_excluded,
        "n_observations_clean": n_clean,
        "results_clean": sensitivity_results,
        "discrepancies": discrepancies
    }


# =====================================================================
# KIỂM TRA TÍNH LIÊN TỤC TRỤC THỜI GIAN
# =====================================================================

def _check_time_gaps(df):
    """
    Phát hiện khoảng trống (gap) trong chuỗi thời gian tuần.

    TẠI SAO cần kiểm tra:
        Kiểm định ADF/KPSS giả định các quan sát CÁCH ĐỀU nhau (equally
        spaced). Nếu có gap (thiếu tuần), phép sai phân Δx_t = x_t - x_{t-1}
        thực chất tính hiệu giữa 2 tuần KHÔNG liên tiếp (ví dụ: cách 3
        tuần thay vì 1 tuần) → sai lệch ý nghĩa thống kê của kiểm định.
        Ghi WARNING để Anh Béo biết và đánh giá tác động.
    """
    dates = pd.to_datetime(df["week_start"])
    expected_gap = pd.Timedelta(weeks=1)
    gaps = []

    for i in range(1, len(dates)):
        actual_gap = dates.iloc[i] - dates.iloc[i - 1]
        if actual_gap > expected_gap:
            n_missing = int(actual_gap / expected_gap) - 1
            gaps.append({
                "after": str(dates.iloc[i - 1].date()),
                "before": str(dates.iloc[i].date()),
                "actual_gap_weeks": int(actual_gap.days / 7),
                "missing_weeks": n_missing
            })

    if gaps:
        total_missing = sum(g["missing_weeks"] for g in gaps)
        logger.warning(
            f"Phát hiện {len(gaps)} khoảng trống trong trục thời gian "
            f"(tổng cộng thiếu {total_missing} tuần). Kiểm định ADF/KPSS "
            f"giả định chuỗi cách đều — kết quả có thể bị ảnh hưởng."
        )
        for g in gaps:
            logger.warning(
                f"  Gap: {g['after']} → {g['before']} "
                f"(cách {g['actual_gap_weeks']} tuần, thiếu {g['missing_weeks']} tuần)"
            )

    return gaps


# =====================================================================
# HÀM CHÍNH — ĐIỀU PHỐI PHASE 1
# =====================================================================

def run_phase1(input_path=None):
    """
    Hàm chính điều phối toàn bộ Phase 1: Kiểm định tính dừng.

    Tham số:
        input_path: str hoặc None — đường dẫn tới causal_weekly_dataset.csv.
                    Nếu None, tự tìm trong data/processed/.

    Trả về:
        str — đường dẫn tới file JSON kết quả (reports/phase1_stationarity.json).

    Raises:
        FileNotFoundError nếu không tìm thấy dataset — theo đúng hợp đồng
        skill.md: Phase X thiếu input Phase Y phải dừng và báo lỗi rõ ràng.
    """
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("PHASE 1 — KIỂM ĐỊNH TÍNH DỪNG (STATIONARITY TESTING)")
    logger.info("=" * 60)

    # -----------------------------------------------------------------
    # Bước 1: Tải dataset tuần từ output Phase 0
    # -----------------------------------------------------------------
    base_dir = get_base_dir()

    if input_path is None:
        input_path = os.path.join(
            base_dir, "data", "processed", "causal_weekly_dataset.csv"
        )

    if not os.path.exists(input_path):
        raise FileNotFoundError(
            f"Không tìm thấy dataset tại {input_path}. "
            f"Cần chạy Phase 0 (phase0_data_reengineering.py) trước để tạo "
            f"causal_weekly_dataset.csv."
        )

    # Đọc và tạo bản copy — tuân thủ nguyên tắc bất biến (CLAUDE.md mục 2)
    df = pd.read_csv(input_path).copy()
    df["week_start"] = pd.to_datetime(df["week_start"])

    n_obs = len(df)
    date_start = str(df["week_start"].min().date())
    date_end = str(df["week_start"].max().date())

    logger.info(
        f"Đã tải dataset: {n_obs} tuần, từ {date_start} đến {date_end}."
    )

    # Cảnh báo nếu mẫu nhỏ
    if n_obs < RECOMMENDED_MIN_OBS:
        logger.warning(
            f"Kích thước mẫu ({n_obs}) nhỏ hơn khuyến nghị ({RECOMMENDED_MIN_OBS}) "
            f"cho kiểm định ADF/KPSS. Kết quả có thể thiếu power — cần diễn "
            f"giải thận trọng."
        )

    # -----------------------------------------------------------------
    # Bước 2: Kiểm tra tính liên tục trục thời gian
    # -----------------------------------------------------------------
    time_gaps = _check_time_gaps(df)

    # -----------------------------------------------------------------
    # Bước 3: Kiểm định tính dừng cho từng biến
    # -----------------------------------------------------------------
    logger.info("-" * 40)
    logger.info("Bắt đầu kiểm định tính dừng cho 4 biến...")
    logger.info("-" * 40)

    var_results = {}
    all_warnings = []

    # Cảnh báo chung về mẫu nhỏ
    if n_obs < RECOMMENDED_MIN_OBS:
        all_warnings.append(
            f"Kích thước mẫu ({n_obs}) nhỏ hơn khuyến nghị ({RECOMMENDED_MIN_OBS}) "
            f"cho kiểm định ADF/KPSS. Kết quả cần được diễn giải thận trọng."
        )

    for var in ANALYSIS_VARS:
        if var not in df.columns:
            logger.warning(f"Biến '{var}' không tồn tại trong dataset — bỏ qua.")
            all_warnings.append(f"Biến '{var}' không tồn tại trong dataset.")
            continue

        logger.info(f"\n{'='*30} {var} {'='*30}")
        series = df[var].copy()

        # Thống kê mô tả nhanh trước khi kiểm định
        logger.info(
            f"{var}: mean={series.mean():.4f}, std={series.std():.4f}, "
            f"min={series.min():.4f}, max={series.max():.4f}, "
            f"NaN={series.isna().sum()}"
        )

        var_result = _find_integration_order(series, var)
        var_results[var] = var_result

    # -----------------------------------------------------------------
    # Bước 4: Tính d_max (bậc tích hợp lớn nhất) — dùng cho Toda-Yamamoto
    # -----------------------------------------------------------------
    d_values = {
        var: res["integration_order"]
        for var, res in var_results.items()
        if res["integration_order"] is not None
    }
    d_max = max(d_values.values()) if d_values else 0

    logger.info("-" * 40)
    logger.info("TÓM TẮT BẬC TÍCH HỢP:")
    for var, d in d_values.items():
        logger.info(f"  d({var}) = {d}  →  I({d})")
    logger.info(f"  d_max = {d_max} (dùng cho Toda-Yamamoto ở Phase 3b)")
    logger.info("-" * 40)

    # -----------------------------------------------------------------
    # Bước 5: Phân tích độ nhạy (loại tuần nội suy)
    # -----------------------------------------------------------------
    logger.info("\n--- PHÂN TÍCH ĐỘ NHẠY (Sensitivity Analysis) ---")
    sensitivity = _run_sensitivity_analysis(df, var_results)

    # -----------------------------------------------------------------
    # Bước 6: Ghi kết quả ra JSON (reports/phase1_stationarity.json)
    # -----------------------------------------------------------------
    # Loại bỏ trường series_used (pd.Series) khỏi kết quả trước khi
    # serialize — trường này chỉ dùng nội bộ cho Zivot-Andrews tiebreaker,
    # không cần lưu vào JSON.
    for _var, _vdata in var_results.items():
        if "tests" in _vdata:
            for _diff_label, _tdata in _vdata["tests"].items():
                if isinstance(_tdata, dict):
                    for _test_key in ("adf", "kpss"):
                        if isinstance(_tdata.get(_test_key), dict):
                            _tdata[_test_key].pop("series_used", None)

    output = {
        "metadata": {
            "script": "phase1_stationarity.py",
            "timestamp": datetime.now().isoformat(),
            "input_file": "data/processed/causal_weekly_dataset.csv",
            "n_observations": n_obs,
            "date_range": {"start": date_start, "end": date_end},
            "significance_level": SIGNIFICANCE_LEVEL,
            "method": "ADF+KPSS dual confirmation (Pfaff, 2008) + Zivot-Andrews tiebreaker",
            "adf_regression": "c (constant, no trend)",
            "kpss_regression": "c (level stationarity)",
            "adf_autolag": "AIC"
        },
        "results": var_results,
        "d_max": d_max,
        "d_values": d_values,
        "time_gaps": time_gaps,
        "sensitivity_analysis": sensitivity,
        "warnings": all_warnings
    }

    output_dir = os.path.join(base_dir, "reports")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "phase1_stationarity.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    logger.info(f"Kết quả Phase 1 đã lưu: {output_path}")

    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info(f"Phase 1 hoàn tất trong {elapsed:.1f}s.")

    return output_path


# =====================================================================
# ENTRY POINT — cho phép chạy script độc lập (CLAUDE.md mục 3.5)
# =====================================================================
if __name__ == "__main__":
    try:
        output = run_phase1()
        logger.info(f"Kết quả lưu tại: {output}")
    except Exception:
        logger.exception("Phase 1 thất bại — xem traceback ở trên.")
        sys.exit(1)
