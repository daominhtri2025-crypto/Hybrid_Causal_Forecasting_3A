"""
Tầng 2 — Phase 0 (Hybrid Synthetic): Xây dựng dataset tuần với dữ liệu
mô phỏng thông minh (Smart Synthetic Data) cho pipeline VECM.

Mục đích:
    Tạo dataset tuần 3 biến (OEE_Score, DelayRate, Revenue) khi CSDL QTDN
    không đủ dữ liệu Production Order (2 dòng) và Revenue (3 dòng hóa đơn)
    để chạy các kiểm định chuỗi thời gian.

    Chiến lược "Hướng 4" — Hybrid:
      - Biến Delay: Dữ liệu THẬT từ 4,127 Sales Orders (2017–2025), hoặc
        mô phỏng sát phân phối thực khi chưa export được từ NAV.
      - Biến OEE: Mô phỏng có quan hệ nhân quả Granger với Delay (lag 1-2).
      - Biến Revenue: Mô phỏng có mùa vụ + phản hồi nhân quả từ Delay.

    Khi có dữ liệu OEE/Revenue thật từ hệ thống khác, chỉ cần đổi nguồn
    input — logic pipeline Phase 1→4 KHÔNG cần sửa.

Công thức toán học:
    (1) OEE_t = μ + ρ·(OEE_{t-1} − μ)
                − λ₁·z(Delay_{t+1}) − λ₂·z(Delay_{t+2})
                + σ·ε_t
        Ý nghĩa: OEE sụt giảm TRƯỚC KHI Delay tăng (nhân quả Granger,
        OEE → Delay với lag 1-2 tuần). Dấu trừ đảm bảo OEE↓ → Delay↑.

    (2) log(Rev_t) = log(Rev_{t-1}) + g + Δseasonal_t
                     − δ₁·z(Delay_{t-1}) − δ₂·z(Delay_{t-2})
                     + σ·ε_t
        Ý nghĩa: Random walk trong log-space (I(1) thực sự). Revenue
        giảm SAU KHI Delay tăng (phản hồi nhân quả, Delay → Revenue
        với lag 1-2 tuần). Log-space đảm bảo Revenue > 0.

    trong đó z(x) = (x − mean) / std (standardization).

Input:  CSV xuất từ tang1_db_extractor.py hoặc SSMS (Sales Order Header),
        HOẶC không có input (tự sinh dữ liệu mô phỏng sát QTDN).
Output: data/processed/causal_weekly_dataset.csv (cùng format phase0 gốc).
        reports/phase0_synthetic_metadata.json (ghi rõ biến nào thật/giả).

Tham chiếu khoa học:
    - Granger, C.W.J. (1969). "Investigating Causal Relations by
      Econometric Models and Cross-spectral Methods." Econometrica, 37(3).
    - Johansen, S. (1991). "Estimation and Hypothesis Testing of
      Cointegration Vectors in Gaussian VAR Models." Econometrica, 59(6).
    - Lütkepohl, H. (2005). "New Introduction to Multiple Time Series
      Analysis." Springer. [Cấu trúc DGP cho mô phỏng VECM]

Tuân thủ: CLAUDE.md mục 2 (bất biến raw), mục 3 (coding), mục 7 (logging).
"""

import os
import sys
import json
from datetime import datetime
from typing import Optional, Dict, Tuple

import numpy as np
import pandas as pd

from scripts.utils import get_logger, get_base_dir

logger = get_logger("phase0_synthetic")

# Seed mặc định — đảm bảo tái lập kết quả (CLAUDE.md mục 3.5)
DEFAULT_SEED = 42

# =====================================================================
# PHÂN PHỐI SALES ORDER THỰC TẾ TỪ CSDL QTDN
# (Kết quả chẩn đoán ngày 2026-08-10 — 4,127 đơn hàng tổng cộng)
# Dùng 2018–2025 cho mô phỏng (2017 chỉ có 1 đơn — quá thưa)
# =====================================================================
QTDN_YEARLY_DISTRIBUTION: Dict[int, int] = {
    2018: 11,
    2019: 826,
    2020: 541,
    2021: 694,
    2022: 384,
    2023: 357,
    2024: 481,
    2025: 480,
}


# =====================================================================
# LỚP CHÍNH: CausalDatasetBuilder
# =====================================================================

class CausalDatasetBuilder:
    """
    Xây dựng dataset tuần 3 biến (OEE, Delay, Revenue) cho pipeline VECM.

    Hai chế độ hoạt động:
      - "hybrid": Delay THẬT (từ CSV) + OEE/Revenue MÔ PHỎNG.
      - "full_synthetic": Tất cả 3 biến đều mô phỏng (testing pipeline).

    Khi có dữ liệu OEE/Revenue thật từ hệ thống khác, chỉ cần truyền
    oee_series / revenue_series vào build_dataset() — toàn bộ pipeline
    Phase 1→4 (ADF → Granger → Johansen → VECM) KHÔNG cần sửa gì.

    Ví dụ sử dụng:
        # Chế độ full synthetic (testing):
        builder = CausalDatasetBuilder(seed=42)
        orders = builder.simulate_sales_orders()
        delay  = builder.orders_to_weekly_delay(orders)
        ds     = builder.build_dataset(delay)
        builder.save_dataset(ds)

        # Chế độ hybrid (Delay thật + OEE/Revenue mô phỏng):
        builder = CausalDatasetBuilder(seed=42)
        delay  = builder.load_real_delay("path/to/sales_orders.csv")
        ds     = builder.build_dataset(delay)
        builder.save_dataset(ds)

        # Khi có thêm OEE thật:
        oee_df = pd.read_csv("oee_weekly.csv")
        oee_s  = oee_df.set_index("week_start")["OEE_Score"]
        ds     = builder.build_dataset(delay, oee_series=oee_s)
    """

    def __init__(self, seed: int = DEFAULT_SEED):
        """
        Khởi tạo builder với random seed cố định.

        Seed ảnh hưởng đến TẤT CẢ yếu tố ngẫu nhiên: mô phỏng Sales
        Order, nhiễu OEE, nhiễu Revenue. Cùng seed → cùng kết quả
        (CLAUDE.md mục 3.5).
        """
        self.rng = np.random.default_rng(seed)
        self.seed = seed
        self._metadata: Dict = {
            "seed": seed,
            "created_at": datetime.now().isoformat(),
            "script": "phase0_synthetic_pipeline.py",
            "strategy": "Hướng 4 — Hybrid (Delay thật/mô phỏng + OEE/Revenue mô phỏng)",
            "variables": {},
        }

    # =================================================================
    # PHẦN 1A: MÔ PHỎNG SALES ORDER CẤP ĐƠN HÀNG (4,127 dòng)
    # =================================================================

    def simulate_sales_orders(
        self,
        start: str = "2018-01-01",
        end: str = "2025-12-31",
        yearly_counts: Optional[Dict[int, int]] = None,
    ) -> pd.DataFrame:
        """
        Tạo bảng Sales Order mô phỏng sát phân phối thực của CSDL QTDN.

        Mỗi đơn hàng có:
          - OrderNo: mã đơn hàng (BDHxxxxx, theo quy ước NAV)
          - ShipmentDate: ngày giao hàng thực tế
          - RequestedDeliveryDate: ngày khách hàng yêu cầu giao
          - IsDelayed: 1 nếu ShipmentDate > RequestedDeliveryDate
          - DelayDays: số ngày trễ (0 nếu đúng hạn)

        Xác suất trễ biến đổi theo thời gian (mô phỏng thực tế ngành):
          - 2018–2019: ~40% (tăng trưởng nhanh, áp lực giao hàng)
          - 2020:      ~55% (COVID-19 gây gián đoạn chuỗi cung ứng)
          - 2021–2022: ~35% (phục hồi dần)
          - 2023–2025: ~25% (ổn định, cải thiện quy trình)

        Tham số:
            start, end: khoảng thời gian mô phỏng.
            yearly_counts: số đơn hàng mỗi năm (mặc định: QTDN thực tế).

        Trả về:
            DataFrame cấp đơn hàng (~3,774 dòng nếu dùng QTDN mặc định).
        """
        if yearly_counts is None:
            yearly_counts = QTDN_YEARLY_DISTRIBUTION

        logger.info("Mô phỏng Sales Order cấp đơn hàng từ phân phối QTDN...")

        all_orders = []
        order_counter = 0

        for year, count in sorted(yearly_counts.items()):
            if year < int(start[:4]) or year > int(end[:4]):
                continue

            # Xác suất trễ cơ sở theo giai đoạn (mô phỏng thực tế ngành)
            year_frac = year + 0.5
            if year_frac < 2019.5:
                base_delay_prob = 0.40
            elif year_frac < 2020.5:
                base_delay_prob = 0.55
            elif year_frac < 2022.0:
                base_delay_prob = 0.38
            elif year_frac < 2023.5:
                base_delay_prob = 0.33
            else:
                base_delay_prob = 0.25

            # Phân bổ đơn hàng trong năm (rải đều + nhiễu)
            year_start = pd.Timestamp(f"{year}-01-01")
            year_end = pd.Timestamp(f"{year}-12-31")
            days_in_year = (year_end - year_start).days + 1

            for _ in range(count):
                order_counter += 1
                order_no = f"BDH{order_counter:05d}"

                # Ngày yêu cầu giao hàng — rải ngẫu nhiên trong năm
                random_day = int(self.rng.integers(0, days_in_year))
                requested_date = year_start + pd.Timedelta(days=random_day)

                # Xác suất trễ cho từng đơn (± nhiễu quanh base)
                delay_prob = np.clip(
                    base_delay_prob + self.rng.normal(0, 0.05),
                    0.05, 0.80,
                )
                is_delayed = int(self.rng.random() < delay_prob)

                if is_delayed:
                    # Số ngày trễ: phân phối Exponential truncated (1–30 ngày)
                    delay_days = int(np.clip(
                        self.rng.exponential(scale=7.0) + 1,
                        1, 30,
                    ))
                    shipment_date = requested_date + pd.Timedelta(days=delay_days)
                else:
                    # Giao sớm hoặc đúng hạn (0–3 ngày trước deadline)
                    early_days = int(self.rng.integers(0, 4))
                    delay_days = 0
                    shipment_date = requested_date - pd.Timedelta(days=early_days)

                all_orders.append({
                    "OrderNo": order_no,
                    "ShipmentDate": shipment_date,
                    "RequestedDeliveryDate": requested_date,
                    "IsDelayed": is_delayed,
                    "DelayDays": delay_days,
                })

        orders_df = pd.DataFrame(all_orders)
        orders_df = orders_df.sort_values("ShipmentDate").reset_index(drop=True)

        total = len(orders_df)
        delayed = orders_df["IsDelayed"].sum()
        logger.info(
            f"  Sinh xong: {total:,} đơn hàng, "
            f"{delayed:,} bị trễ ({delayed/total:.1%}), "
            f"từ {orders_df['ShipmentDate'].min().date()} "
            f"đến {orders_df['ShipmentDate'].max().date()}."
        )

        return orders_df

    # =================================================================
    # PHẦN 1B: CHUYỂN ĐỔI ĐƠN HÀNG → CHUỖI TUẦN
    # =================================================================

    def orders_to_weekly_delay(
        self,
        orders_df: pd.DataFrame,
        min_orders_per_week: int = 1,
    ) -> pd.DataFrame:
        """
        Gộp dữ liệu đơn hàng theo tuần → chuỗi DelayRate.

        Mốc thời gian: dùng ShipmentDate (ngày giao thực tế) — nhất quán
        với phase0_data_reengineering.py (chống look-ahead bias).

        Tuần được xác định theo ISO week (bắt đầu thứ Hai).

        Tham số:
            orders_df: DataFrame đơn hàng (từ simulate hoặc CSV thật).
            min_orders_per_week: lọc bỏ tuần có quá ít đơn hàng (nhiễu
                                 thống kê — tuần 1 đơn cho DelayRate 0/100%).

        Trả về:
            DataFrame tuần: week_start, DelayRate, order_count.
        """
        df = orders_df.copy()

        # --- Xác định cột ngày giao hàng ---
        date_col = None
        for candidate in ["ShipmentDate", "ActualEndDate", "Shipment Date"]:
            if candidate in df.columns:
                date_col = candidate
                break
        if date_col is None:
            raise ValueError(
                f"Không tìm thấy cột ngày giao hàng. "
                f"Cột hiện có: {list(df.columns)}"
            )

        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.dropna(subset=[date_col])

        # --- Gán tuần (Monday-based) ---
        dt = df[date_col]
        df["week_start"] = dt.dt.normalize() - pd.to_timedelta(dt.dt.weekday, unit="D")

        # --- Đảm bảo cột IsDelayed là số ---
        df["IsDelayed"] = pd.to_numeric(df["IsDelayed"], errors="coerce")
        df = df.dropna(subset=["IsDelayed"])

        # --- Gộp theo tuần ---
        weekly = (
            df.groupby("week_start")
            .agg(
                DelayRate=("IsDelayed", "mean"),
                order_count=("IsDelayed", "count"),
            )
            .reset_index()
            .sort_values("week_start")
            .reset_index(drop=True)
        )

        # --- Lọc tuần quá thưa ---
        before_filter = len(weekly)
        weekly = weekly[weekly["order_count"] >= min_orders_per_week].reset_index(drop=True)
        filtered_out = before_filter - len(weekly)
        if filtered_out > 0:
            logger.warning(
                f"[Delay] Loại {filtered_out:,} tuần có < {min_orders_per_week} "
                f"đơn hàng (DelayRate không đáng tin cậy)."
            )

        logger.info(
            f"[Delay] Gộp tuần xong: {len(weekly):,} tuần, "
            f"trung bình {weekly['order_count'].mean():.1f} đơn/tuần, "
            f"DelayRate trung bình = {weekly['DelayRate'].mean():.1%}."
        )

        return weekly

    # =================================================================
    # PHẦN 1C: ĐỌC DỮ LIỆU DELAY THẬT TỪ CSV
    # =================================================================

    def load_real_delay(
        self,
        csv_path: str,
        date_col: Optional[str] = None,
        planned_col: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Đọc Sales Order thật từ CSV → tính DelayRate theo tuần.

        Tự động nhận diện 2 định dạng:
          (A) Output từ tang1_db_extractor.py:
              OrderNo, IsDelayed, DelayDays, ShipmentDate, RequestedDeliveryDate
          (B) Export SSMS (NAV Sales Order Header):
              No_, Sell-to Customer No_, Shipment Date, Requested Delivery Date

        Tham số:
            csv_path: đường dẫn đến file CSV.
            date_col: tên cột ngày giao hàng thực tế (auto-detect nếu None).
            planned_col: tên cột ngày giao hàng kế hoạch (auto-detect nếu None).

        Trả về:
            DataFrame tuần: week_start, DelayRate, order_count.
        """
        logger.info(f"Đọc dữ liệu Delay thật từ: {csv_path}")
        df = pd.read_csv(csv_path, encoding="utf-8-sig")
        logger.info(f"  Đã tải: {len(df):,} dòng, {len(df.columns)} cột.")

        # --- Tự nhận diện cột ngày ---
        actual_col = date_col
        planned_col_name = planned_col

        actual_candidates = [
            "ActualShipDate", "ShipmentDate", "Shipment Date",
            "Shipment_Date", "ActualEndDate", "Actual End Date",
        ]
        planned_candidates = [
            "RequestedDeliveryDate", "Requested Delivery Date",
            "Requested_Delivery_Date", "PlannedShipmentDate",
            "Planned Shipment Date",
        ]

        if actual_col is None:
            for c in actual_candidates:
                if c in df.columns:
                    actual_col = c
                    break
        if planned_col_name is None:
            for c in planned_candidates:
                if c in df.columns:
                    planned_col_name = c
                    break

        if actual_col is None or planned_col_name is None:
            raise ValueError(
                f"Không tìm thấy cột ngày giao hàng. "
                f"Cột hiện có: {list(df.columns)}. "
                f"Chỉ định date_col và planned_col thủ công."
            )

        logger.info(f"  Cột nhận diện: actual='{actual_col}', planned='{planned_col_name}'.")

        # --- Ép kiểu datetime ---
        df[actual_col] = pd.to_datetime(df[actual_col], errors="coerce")
        df[planned_col_name] = pd.to_datetime(df[planned_col_name], errors="coerce")

        nat_before = len(df)
        df = df.dropna(subset=[actual_col, planned_col_name])
        nat_dropped = nat_before - len(df)
        if nat_dropped > 0:
            logger.warning(f"  Loại {nat_dropped:,} dòng có ngày tháng không hợp lệ.")

        # --- Tính IsDelayed nếu chưa có ---
        if "IsDelayed" not in df.columns:
            df["IsDelayed"] = (df[actual_col] > df[planned_col_name]).astype(int)
            logger.info(
                f"  Tự tính IsDelayed: {df['IsDelayed'].sum():,}/{len(df):,} "
                f"đơn bị trễ ({df['IsDelayed'].mean():.1%})."
            )

        # --- Chuẩn hóa tên cột để orders_to_weekly_delay() nhận diện ---
        df = df.rename(columns={actual_col: "ShipmentDate"})

        # --- Ghi metadata ---
        self._metadata["variables"]["DelayRate"] = {
            "source": "real",
            "source_file": os.path.basename(csv_path),
            "n_orders": len(df),
        }

        return self.orders_to_weekly_delay(df)

    # =================================================================
    # PHẦN 2: SINH DỮ LIỆU OEE MÔ PHỎNG (OEE → Delay, Granger-causal)
    # =================================================================

    def generate_oee(
        self,
        delay_weekly: pd.DataFrame,
        mu: float = 0.80,
        ar1: float = 0.98,
        lambda1: float = 0.008,
        lambda2: float = 0.004,
        noise_std: float = 0.008,
        oee_min: float = 0.65,
        oee_max: float = 0.95,
    ) -> pd.Series:
        """
        Sinh chuỗi OEE mô phỏng có quan hệ nhân quả Granger với Delay.

        ╔═══════════════════════════════════════════════════════════════╗
        ║  MÔ HÌNH TOÁN HỌC (reverse-engineering từ Delay):          ║
        ║                                                             ║
        ║  OEE_t = μ + ρ·(OEE_{t-1} − μ)                            ║
        ║          − λ₁·z(Delay_{t+1})                               ║
        ║          − λ₂·z(Delay_{t+2})                               ║
        ║          + σ·ε_t                                            ║
        ║                                                             ║
        ║  z(x) = (x − mean(x)) / std(x)                            ║
        ║  ε_t ~ N(0, 1)                                             ║
        ╚═══════════════════════════════════════════════════════════════╝

        Giải thích cơ chế nhân quả:
            Trong thực tế sản xuất, OEE thấp (năng suất kém, chất lượng
            giảm) sẽ dẫn đến giao hàng trễ sau 1-2 tuần. Để mô phỏng
            chiều nhân quả này, ta "nhìn vào Delay tương lai" khi sinh OEE:

            - z(Delay_{t+1}) CAO (delay sẽ tăng) → OEE_t THẤP (dấu trừ)
            - z(Delay_{t+1}) THẤP (delay sẽ giảm) → OEE_t CAO

            Khi Phase 2 chạy Granger Causality test, nó sẽ phát hiện:
            "OEE quá khứ (lag 1-2) giúp dự báo Delay hiện tại" → bác bỏ
            H0 → kết luận OEE Granger-cause Delay.

        Tham số:
            delay_weekly: DataFrame tuần chứa cột DelayRate.
            mu:          OEE trung bình mục tiêu (0.80 = 80%, typical ngành may).
            ar1:         hệ số AR(1) gần nghiệm đơn vị (near unit root).
                         0.98 → ADF test với n≈375 không bác bỏ H0 unit root
                         → Phase 1 phân loại OEE là I(1) → Johansen test có
                         đủ biến I(1) để tìm cointegration → route VECM.
                         Unconditional std ≈ noise_std/sqrt(1−ρ²) ≈ 0.050.
            lambda1:     coupling OEE → Delay tại lag 1 (mạnh hơn).
                         Cân bằng: đủ lớn để Granger test trên sai phân
                         vẫn phát hiện, nhưng đủ nhỏ để OEE không dồn
                         về biên clip khi AR khuếch đại.
            lambda2:     coupling OEE → Delay tại lag 2 (yếu hơn).
            noise_std:   độ lệch chuẩn nhiễu innovation (~0.8% OEE).
                         Unconditional std ≈ 0.06 (phần lớn do causal +
                         AR persistence, không phải noise thuần).
            oee_min/max: giới hạn OEE thực tế [0.65, 0.95].

        Trả về:
            pd.Series cùng length với delay_weekly, giá trị OEE_Score.
        """
        n = len(delay_weekly)
        delay = delay_weekly["DelayRate"].values

        # --- Standardize Delay (z-score) ---
        d_mean = np.nanmean(delay)
        d_std = np.nanstd(delay)
        if d_std < 1e-10:
            logger.warning(
                "[OEE] DelayRate có phương sai ≈ 0 — tạo OEE không coupling."
            )
            z_delay = np.zeros(n)
        else:
            z_delay = (delay - d_mean) / d_std

        z_delay = np.nan_to_num(z_delay, nan=0.0)

        # --- Làm mượt z_delay bằng rolling mean (cửa sổ 4 tuần) ---
        # Lý do: các tuần có rất ít đơn hàng (1-3 đơn, đặc biệt 2018)
        # cho DelayRate cực trị (0% hoặc 100%), gây z-score ±2σ và đẩy
        # OEE về clip boundary. Smoothing giữ xu hướng nhân quả nhưng
        # loại bỏ nhiễu thống kê do mẫu nhỏ.
        z_delay_smooth = pd.Series(z_delay).rolling(
            window=4, min_periods=1, center=True
        ).mean().values

        # --- Sinh chuỗi OEE (vòng lặp vì cần OEE_{t-1} cho AR) ---
        oee = np.full(n, mu)
        noise = self.rng.normal(0, noise_std, n)

        for t in range(n):
            # Thành phần AR(1): quán tính từ tuần trước
            ar_component = ar1 * (oee[t - 1] - mu) if t > 0 else 0.0

            # Thành phần nhân quả: "nhìn vào Delay TƯƠNG LAI"
            # Nếu Delay sẽ tăng ở t+1 → OEE tại t phải thấp (dấu trừ)
            causal = 0.0
            if t + 1 < n:
                causal -= lambda1 * z_delay_smooth[t + 1]
            if t + 2 < n:
                causal -= lambda2 * z_delay_smooth[t + 2]

            oee[t] = mu + ar_component + causal + noise[t]

        # --- Clip giới hạn thực tế ---
        oee = np.clip(oee, oee_min, oee_max)

        logger.info(
            f"[OEE] Sinh mô phỏng: {n} tuần, "
            f"mean={np.mean(oee):.3f}, std={np.std(oee):.3f}, "
            f"range=[{np.min(oee):.3f}, {np.max(oee):.3f}]."
        )

        self._metadata["variables"]["OEE_Score"] = {
            "source": "synthetic",
            "method": "AR(1) + Granger-causal reverse-engineering from Delay",
            "formula": "OEE_t = μ + ρ·(OEE_{t-1}−μ) − λ₁·z(D_{t+1}) − λ₂·z(D_{t+2}) + σ·ε_t",
            "params": {
                "mu": mu, "ar1": ar1,
                "lambda1": lambda1, "lambda2": lambda2,
                "noise_std": noise_std,
                "clip": [oee_min, oee_max],
            },
            "stats": {
                "mean": round(float(np.mean(oee)), 4),
                "std": round(float(np.std(oee)), 4),
                "min": round(float(np.min(oee)), 4),
                "max": round(float(np.max(oee)), 4),
            },
        }

        return pd.Series(oee, index=delay_weekly.index, name="OEE_Score")

    # =================================================================
    # PHẦN 3: SINH DỮ LIỆU REVENUE MÔ PHỎNG (Delay → Revenue)
    # =================================================================

    def generate_revenue(
        self,
        delay_weekly: pd.DataFrame,
        base_revenue: float = 500_000_000,
        seasonal_amp: float = 0.15,
        delta1: float = 0.012,
        delta2: float = 0.006,
        noise_std: float = 0.012,
        growth_rate: float = 0.001,
    ) -> pd.Series:
        """
        Sinh chuỗi Revenue mô phỏng có mùa vụ + phản hồi từ Delay.

        ╔═══════════════════════════════════════════════════════════════╗
        ║  MÔ HÌNH TOÁN HỌC (random walk log-space, I(1)):           ║
        ║                                                             ║
        ║  log(Rev_t) = log(Rev_{t-1}) + g                           ║
        ║               + Δseasonal_t                                 ║
        ║               − δ₁·z(Delay_{t-1})                          ║
        ║               − δ₂·z(Delay_{t-2})                          ║
        ║               + σ·ε_t                                       ║
        ║                                                             ║
        ║  Δseasonal_t = A·sin(2π(woy_t−13)/52) − A·sin(...)_{t-1}  ║
        ╚═══════════════════════════════════════════════════════════════╝

        Giải thích:
            Random walk với drift trong log-space → Revenue là I(1) thực
            sự (không phải "gần" unit root). ADF sẽ không bác bỏ H0 unit
            root → Phase 1 phân loại Revenue là I(1) → Johansen test có
            đủ biến I(1) để tìm cointegration → route VECM.

        Giải thích cơ chế nhân quả:
            Trong thực tế kinh doanh FOB may mặc:
            - Giao hàng trễ (Delay↑) → khách hàng phạt/hủy đơn → doanh
              thu giảm sau 1-2 tuần.
            - Dấu trừ (−δ) trước z(Delay_{t-1}): khi Delay quá khứ cao,
              Revenue hiện tại giảm.
            - Phase 2 sẽ phát hiện: "Delay quá khứ (lag 1-2) giúp dự báo
              Revenue" → Delay Granger-cause Revenue.

        Thành phần mùa vụ:
            Ngành may mặc FOB: đỉnh đơn hàng ~Q1-Q2 (chuẩn bị xuân-hè),
            đáy ~Q3-Q4. Sử dụng Δseasonal (thay đổi mùa vụ tuần-sang-
            tuần) thay vì level — đảm bảo seasonal oscillate quanh random
            walk mà không tích lũy drift.

        Tham số:
            delay_weekly: DataFrame tuần chứa cột DelayRate + week_start.
            base_revenue: doanh thu cơ sở khởi điểm (VND/tuần). 500M =
                          trung bình công ty may vừa (~26 tỷ/năm).
            seasonal_amp: biên độ mùa vụ (0.15 = ±15%).
            delta1, delta2: coupling Delay → Revenue (lag 1, 2).
            noise_std:    nhiễu innovation trong log-space (~1.2%).
                          Cumulative std ≈ σ·√T ≈ 0.23 sau 375 tuần.
            growth_rate:  drift/tuần (0.001 ≈ 5.3%/năm).

        Trả về:
            pd.Series cùng length, giá trị Revenue (VND).
        """
        n = len(delay_weekly)
        delay = delay_weekly["DelayRate"].values
        weeks = pd.to_datetime(delay_weekly["week_start"])

        # --- Standardize Delay ---
        d_mean = np.nanmean(delay)
        d_std = np.nanstd(delay)
        z_delay = np.zeros(n) if d_std < 1e-10 else (delay - d_mean) / d_std
        z_delay = np.nan_to_num(z_delay, nan=0.0)

        # --- Smoothing z_delay (giống OEE — loại nhiễu mẫu nhỏ) ---
        z_delay_smooth = pd.Series(z_delay).rolling(
            window=4, min_periods=1, center=True
        ).mean().values

        # --- Thành phần mùa vụ (level) ---
        # Peak ≈ tuần 13 (đầu Q2), trough ≈ tuần 39 (đầu Q4)
        week_of_year = weeks.dt.isocalendar().week.values.astype(float)
        seasonal = seasonal_amp * np.sin(2 * np.pi * (week_of_year - 13) / 52)

        # --- Sinh chuỗi trong log-space: RANDOM WALK với drift ---
        # Random walk (I(1) thực sự) thay vì AR(1) mean-reverting.
        # Tránh dùng AR(1) detrended vì ADF vẫn bác bỏ unit root khi
        # residual AR < 1 (xem lịch sử commit — AR(0.98) detrended
        # vẫn bị ADF phát hiện là stationary).
        log_base = np.log(base_revenue)
        log_rev = np.full(n, log_base)
        noise = self.rng.normal(0, noise_std, n)

        for t in range(n):
            if t == 0:
                # Khởi tạo: baseline + seasonal tuần đầu + nhiễu
                log_rev[0] = log_base + seasonal[0] + noise[0]
                continue

            # Thay đổi mùa vụ tuần-sang-tuần (oscillate, không tích lũy)
            seasonal_change = seasonal[t] - seasonal[t - 1]

            # Nhân quả: Delay QUÁ KHỨ ảnh hưởng Revenue hiện tại
            causal = 0.0
            if t >= 1:
                causal -= delta1 * z_delay_smooth[t - 1]
            if t >= 2:
                causal -= delta2 * z_delay_smooth[t - 2]

            # Random walk: log(Rev_t) = log(Rev_{t-1}) + drift + ...
            log_rev[t] = log_rev[t - 1] + growth_rate + seasonal_change + causal + noise[t]

        # --- Chuyển về scale thật (exp) ---
        revenue = np.exp(log_rev)

        logger.info(
            f"[Revenue] Sinh mô phỏng: {n} tuần, "
            f"mean={np.mean(revenue):,.0f} VND, "
            f"range=[{np.min(revenue):,.0f}, {np.max(revenue):,.0f}]."
        )

        self._metadata["variables"]["Revenue"] = {
            "source": "synthetic",
            "method": "Random walk (I(1)) in log-space + seasonal + Delay-lagged coupling",
            "formula": (
                "log(Rev_t) = log(Rev_{t-1}) + g + Δseasonal_t "
                "− δ₁·z(D_{t-1}) − δ₂·z(D_{t-2}) + σ·ε_t"
            ),
            "params": {
                "base_revenue_vnd": base_revenue,
                "seasonal_amp": seasonal_amp,
                "delta1": delta1, "delta2": delta2,
                "noise_std": noise_std,
                "growth_rate_per_week": growth_rate,
            },
            "stats": {
                "mean": round(float(np.mean(revenue)), 0),
                "std": round(float(np.std(revenue)), 0),
                "min": round(float(np.min(revenue)), 0),
                "max": round(float(np.max(revenue)), 0),
            },
        }

        return pd.Series(revenue, index=delay_weekly.index, name="Revenue")

    # =================================================================
    # PHẦN 4: GỘP DATASET HOÀN CHỈNH
    # =================================================================

    def build_dataset(
        self,
        delay_weekly: pd.DataFrame,
        oee_series: Optional[pd.Series] = None,
        revenue_series: Optional[pd.Series] = None,
    ) -> pd.DataFrame:
        """
        Gộp 3 biến thành dataset tuần hoàn chỉnh.

        Format output ĐỒNG NHẤT với phase0_data_reengineering.py:
            week_start, OEE_Score, DelayRate, Revenue, OrderVolume,
            is_interpolated_oee, is_interpolated_delay

        Tham số:
            delay_weekly: DataFrame tuần (bắt buộc) — từ load_real_delay
                          hoặc orders_to_weekly_delay.
            oee_series: Series OEE thật. None → tự sinh mô phỏng.
            revenue_series: Series Revenue thật. None → tự sinh mô phỏng.

        Trả về:
            DataFrame tuần hoàn chỉnh, sẵn sàng cho Phase 1→4.
        """
        logger.info("Gộp 3 biến thành dataset tuần...")

        # --- OEE: thật hoặc mô phỏng ---
        if oee_series is None:
            logger.info("  OEE: không có dữ liệu thật → sinh mô phỏng.")
            oee_series = self.generate_oee(delay_weekly)
        else:
            logger.info("  OEE: sử dụng dữ liệu thật được cung cấp.")
            self._metadata["variables"]["OEE_Score"] = {"source": "real"}

        # --- Revenue: thật hoặc mô phỏng ---
        if revenue_series is None:
            logger.info("  Revenue: không có dữ liệu thật → sinh mô phỏng.")
            revenue_series = self.generate_revenue(delay_weekly)
        else:
            logger.info("  Revenue: sử dụng dữ liệu thật được cung cấp.")
            self._metadata["variables"]["Revenue"] = {"source": "real"}

        # --- Xây dựng DataFrame output ---
        dataset = pd.DataFrame({
            "week_start": delay_weekly["week_start"].values,
            "OEE_Score": oee_series.values,
            "DelayRate": delay_weekly["DelayRate"].values,
            "Revenue": revenue_series.values,
            "OrderVolume": delay_weekly["order_count"].values,
            # Dữ liệu mô phỏng hoàn chỉnh — không cần nội suy
            "is_interpolated_oee": 0,
            "is_interpolated_delay": 0,
        })

        dataset = dataset.sort_values("week_start").reset_index(drop=True)

        logger.info(
            f"  Dataset hoàn chỉnh: {len(dataset):,} tuần × "
            f"{len(dataset.columns)} cột."
        )

        return dataset

    # =================================================================
    # PHẦN 5: LƯU FILE + METADATA
    # =================================================================

    def save_dataset(
        self,
        dataset: pd.DataFrame,
        output_dir: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Lưu dataset + metadata ra file.

        Output:
            - data/processed/causal_weekly_dataset.csv
            - reports/phase0_synthetic_metadata.json

        Trả về: (csv_path, json_path).
        """
        if output_dir is None:
            output_dir = get_base_dir()

        # --- CSV (cùng format với phase0 gốc) ---
        csv_path = os.path.join(
            output_dir, "data", "processed", "causal_weekly_dataset.csv"
        )
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        dataset.to_csv(csv_path, index=False, encoding="utf-8-sig")
        logger.info(f"  Đã lưu dataset: {csv_path}")

        # --- Metadata JSON (ghi rõ biến nào thật/giả) ---
        json_path = os.path.join(output_dir, "reports", "phase0_synthetic_metadata.json")
        os.makedirs(os.path.dirname(json_path), exist_ok=True)

        self._metadata["output"] = {
            "csv_path": csv_path,
            "n_weeks": len(dataset),
            "date_range": {
                "start": str(dataset["week_start"].min()),
                "end": str(dataset["week_start"].max()),
            },
            "columns": list(dataset.columns),
        }

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self._metadata, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"  Đã lưu metadata: {json_path}")

        return csv_path, json_path

    # =================================================================
    # PHẦN 6: PREVIEW (IN BẢNG MARKDOWN)
    # =================================================================

    def preview(self, dataset: pd.DataFrame, n_rows: int = 5) -> str:
        """
        In bảng Markdown 5 dòng đầu tiên của dataset.

        Dùng để kiểm tra nhanh trước khi chạy Phase 1→4.

        Trả về: chuỗi Markdown table.
        """
        df = dataset.head(n_rows).copy()

        # Làm tròn cho dễ đọc
        df["OEE_Score"] = df["OEE_Score"].map("{:.4f}".format)
        df["DelayRate"] = df["DelayRate"].map("{:.4f}".format)
        df["Revenue"] = df["Revenue"].map("{:,.0f}".format)

        # Chuyển week_start sang chuỗi ngày
        df["week_start"] = pd.to_datetime(df["week_start"]).dt.strftime("%Y-%m-%d")

        header = "| " + " | ".join(df.columns) + " |"
        separator = "| " + " | ".join(["---"] * len(df.columns)) + " |"
        rows = []
        for _, row in df.iterrows():
            rows.append("| " + " | ".join(str(v) for v in row.values) + " |")

        table = "\n".join([header, separator] + rows)
        return table


# =====================================================================
# HÀM ĐIỀU PHỐI CHÍNH
# =====================================================================

def run_phase0_synthetic(
    delay_csv: Optional[str] = None,
    seed: int = DEFAULT_SEED,
) -> str:
    """
    Entry point cho Phase 0 (Hybrid Synthetic).

    Tham số:
        delay_csv: đường dẫn CSV chứa Sales Order thật. Nếu None →
                   tự sinh dữ liệu mô phỏng sát phân phối QTDN.
        seed: random seed (mặc định: 42).

    Trả về: đường dẫn causal_weekly_dataset.csv.
    """
    start_time = datetime.now()
    logger.info("=" * 65)
    logger.info("Phase 0 (Hybrid Synthetic Pipeline) bắt đầu.")
    logger.info(f"  Seed: {seed}")
    logger.info("=" * 65)

    builder = CausalDatasetBuilder(seed=seed)

    # -----------------------------------------------------------------
    # Bước 1: Xử lý Delay (thật hoặc mô phỏng)
    # -----------------------------------------------------------------
    if delay_csv and os.path.exists(delay_csv):
        logger.info(f"Chế độ: HYBRID — Delay thật từ {delay_csv}")
        delay_weekly = builder.load_real_delay(delay_csv)
    else:
        if delay_csv:
            logger.warning(
                f"File không tồn tại: {delay_csv} — chuyển sang mô phỏng."
            )
        logger.info("Chế độ: FULL SYNTHETIC — mô phỏng tất cả 3 biến.")
        orders = builder.simulate_sales_orders()
        delay_weekly = builder.orders_to_weekly_delay(orders)

        # Ghi metadata cho delay mô phỏng
        builder._metadata["variables"]["DelayRate"] = {
            "source": "simulated",
            "method": "Binomial sampling, time-varying probability, QTDN distribution",
            "n_orders": len(orders),
            "n_weeks": len(delay_weekly),
            "mean_delay_rate": round(float(delay_weekly["DelayRate"].mean()), 4),
        }

    # -----------------------------------------------------------------
    # Bước 2-3: OEE + Revenue (mô phỏng — tự động trong build_dataset)
    # -----------------------------------------------------------------
    dataset = builder.build_dataset(delay_weekly)

    # -----------------------------------------------------------------
    # Bước 4: Lưu file
    # -----------------------------------------------------------------
    csv_path, json_path = builder.save_dataset(dataset)

    # -----------------------------------------------------------------
    # Bước 5: Preview + Tóm tắt
    # -----------------------------------------------------------------
    logger.info("=" * 65)
    logger.info("PREVIEW — 5 dòng đầu tiên:")
    preview_table = builder.preview(dataset)
    for line in preview_table.split("\n"):
        logger.info(f"  {line}")

    logger.info("=" * 65)
    logger.info("TÓM TẮT DATASET (điểm dừng xác nhận Phase 0):")
    logger.info(f"  Tổng số tuần        : {len(dataset):,}")
    logger.info(
        f"  Khoảng thời gian    : "
        f"{dataset['week_start'].min()} → {dataset['week_start'].max()}"
    )
    logger.info(
        f"  OEE_Score           : "
        f"mean={dataset['OEE_Score'].mean():.4f}, "
        f"std={dataset['OEE_Score'].std():.4f}"
    )
    logger.info(
        f"  DelayRate           : "
        f"mean={dataset['DelayRate'].mean():.4f}, "
        f"std={dataset['DelayRate'].std():.4f}"
    )
    logger.info(
        f"  Revenue (VND)       : "
        f"mean={dataset['Revenue'].mean():,.0f}, "
        f"std={dataset['Revenue'].std():,.0f}"
    )

    # Nguồn dữ liệu từng biến
    logger.info("  Nguồn dữ liệu:")
    for var, info in builder._metadata.get("variables", {}).items():
        source = info.get("source", "unknown")
        logger.info(f"    {var}: [{source.upper()}]")

    logger.info(f"  File output         : {csv_path}")
    logger.info(f"  File metadata       : {json_path}")
    logger.info("=" * 65)

    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info(f"Phase 0 (Hybrid Synthetic) hoàn tất trong {elapsed:.1f}s.")

    return csv_path


# =====================================================================
# ENTRY POINT (CLAUDE.md mục 3.5 — chạy script độc lập)
# =====================================================================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Phase 0 Hybrid Synthetic: tạo dataset tuần cho pipeline VECM "
            "với OEE/Revenue mô phỏng thông minh (Hướng 4)."
        )
    )
    parser.add_argument(
        "--delay-csv",
        type=str,
        default=None,
        help=(
            "Đường dẫn CSV chứa Sales Order thật (output tang1 hoặc SSMS). "
            "Nếu không chỉ định → tự sinh mô phỏng sát QTDN."
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"Random seed cho tái lập kết quả (mặc định: {DEFAULT_SEED}).",
    )

    args = parser.parse_args()

    try:
        output = run_phase0_synthetic(
            delay_csv=args.delay_csv,
            seed=args.seed,
        )
        logger.info(f"Kết quả lưu tại: {output}")
    except Exception:
        logger.exception("Phase 0 (Hybrid Synthetic) thất bại — xem traceback.")
        sys.exit(1)
