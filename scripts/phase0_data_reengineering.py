"""
Tầng 2 — Phase 0: Tái cấu trúc & Đồng bộ hóa dữ liệu thô thành dataset tuần.

Mục đích:
    Đọc 3 file CSV nguyên trạng từ snapshot mới nhất trong `data/raw/`, thực hiện:
      (1) Đồng bộ trục thời gian — chống look-ahead bias bằng cách gán tuần theo
          `PostingDate` (Production), `ActualShipDate` (Delay), và `ShipmentDate`
          (OrderDemand) — tất cả đều là "ngày biết được" (point-in-time correct).
      (2) Gộp theo tuần: tổng sản lượng (ProductionVolume), tỷ lệ trễ (DelayRate),
          tổng khối lượng đặt hàng (OrderDemand).
      (3) Reindex lưới tuần đều đặn (W-MON) + forward-fill DelayRate (limit=4,
          CLAUDE.md mục 8), fillna(0) cho ProductionVolume/OrderDemand.
      (4) Giám sát bản ghi cận nửa đêm (22:00–02:00) — ghi WARNING.
    và ghi kết quả ra `data/processed/causal_weekly_dataset.csv`.

Phương án A (2026-08-12): 100% dữ liệu thật từ NAV:
    - ProductionVolume: [Value Entry] Source Type 3+4 → SUM(ValuedQty)/tuần
    - DelayRate: [Sales Order Header] → IsDelayed mean/tuần (giữ nguyên)
    - OrderDemand: [Sales Order Line] → SUM(Quantity)/tuần

Input:  `data/raw/snapshot_YYYYMMDD_HHMM/production_volume.csv`,
        `data/raw/snapshot_YYYYMMDD_HHMM/cmt_delay_results.csv`,
        `data/raw/snapshot_YYYYMMDD_HHMM/order_demand.csv`.

Output: `data/processed/causal_weekly_dataset.csv`
        Các cột: week_start, ProductionVolume, DelayRate, OrderDemand,
                 is_filled_delay.

Sở hữu: Role A — Data Engineering (skill.md).
Tuân thủ: CLAUDE.md mục 2 (bất biến raw), mục 3 (coding), mục 7 (logging),
          mục 8 (forward-fill Strategy A cho DelayRate).
"""

import os
import sys
import glob
from datetime import datetime

import numpy as np
import pandas as pd

from scripts.utils import get_logger, get_base_dir

logger = get_logger("phase0")


# =====================================================================
# HÀM TIỆN ÍCH NỘI BỘ
# =====================================================================

def _find_latest_snapshot() -> str:
    """
    Tìm thư mục snapshot mới nhất trong `data/raw/`.

    Quy ước đặt tên: `snapshot_YYYYMMDD_HHMM` — sắp xếp lexicographic
    trùng với thứ tự thời gian.

    Raises:
        FileNotFoundError nếu không tìm thấy snapshot nào.
    """
    raw_dir = os.path.join(get_base_dir(), "data", "raw")
    pattern = os.path.join(raw_dir, "snapshot_*")
    snapshot_dirs = sorted(glob.glob(pattern))

    if not snapshot_dirs:
        raise FileNotFoundError(
            "Không tìm thấy thư mục snapshot nào trong data/raw/. "
            "Cần chạy Tầng 1 (tang1_db_extractor.py) trước để trích xuất "
            "dữ liệu từ SQL Server."
        )

    latest = snapshot_dirs[-1]
    logger.info(f"Snapshot mới nhất: {os.path.basename(latest)}")
    return latest


def _load_raw_csv(snapshot_dir: str, filename: str) -> pd.DataFrame:
    """
    Đọc 1 file CSV từ thư mục snapshot — CHỈ ĐỌC, không sửa đổi.
    Tuân thủ nguyên tắc bất biến dữ liệu (CLAUDE.md mục 2).
    """
    filepath = os.path.join(snapshot_dir, filename)

    if not os.path.exists(filepath):
        raise FileNotFoundError(
            f"Không tìm thấy file '{filename}' trong {snapshot_dir}. "
            f"Cần chạy Tầng 1 (tang1_db_extractor.py) trước."
        )

    df = pd.read_csv(filepath, encoding="utf-8-sig")
    logger.info(f"Đã tải '{filename}': {len(df):,} dòng, {len(df.columns)} cột.")
    return df


def _warn_midnight_boundary(
    df: pd.DataFrame,
    date_col: str,
    source_name: str,
) -> int:
    """
    Giám sát bản ghi có timestamp trong khung ±2 giờ quanh nửa đêm.
    Ghi WARNING kèm OrderNo mẫu — KHÔNG tự sửa (ARCHITECTURE, mục 2.2).
    """
    if date_col not in df.columns:
        return 0

    dt_series = pd.to_datetime(df[date_col], errors="coerce")
    hours = dt_series.dt.hour

    # NAV lưu date-only dưới dạng datetime 00:00:00 — đây là timestamp chuẩn,
    # không phải bản ghi "cận nửa đêm". Loại bỏ các bản ghi có time = 00:00:00.
    is_exact_midnight = (
        (hours == 0)
        & (dt_series.dt.minute == 0)
        & (dt_series.dt.second == 0)
    )
    mask = ((hours >= 22) | (hours < 2)) & ~is_exact_midnight
    boundary_df = df[mask]
    count = len(boundary_df)

    if count > 0:
        sample_orders = ""
        if "OrderNo" in boundary_df.columns:
            sample_list = boundary_df["OrderNo"].head(10).tolist()
            sample_orders = f" — OrderNo mẫu: {sample_list}"
            if count > 10:
                sample_orders += f" (và {count - 10} đơn hàng khác)"

        logger.warning(
            f"[{source_name}] Phát hiện {count:,} bản ghi có {date_col} "
            f"trong khung cận nửa đêm (22:00–02:00).{sample_orders}"
        )

    return count


def _to_week_start(dt_series: pd.Series) -> pd.Series:
    """
    Chuyển đổi cột datetime thành ngày đầu tuần (thứ Hai - Monday).
    Công thức: lùi về thứ Hai gần nhất bằng cách trừ đi weekday().
    """
    dt = pd.to_datetime(dt_series, errors="coerce")
    return dt.dt.normalize() - pd.to_timedelta(dt.dt.weekday, unit="D")


# =====================================================================
# XỬ LÝ TỪNG NGUỒN DỮ LIỆU → GỘP THEO TUẦN
# =====================================================================

def _aggregate_production_weekly(prod_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Gộp dữ liệu sản xuất từ Value Entry theo tuần — tổng sản lượng.

    Nguồn: production_volume.csv (từ [Value Entry], Source Type 3+4).
    Biến: ProductionVolume = SUM(ValuedQty) mỗi tuần.

    Logic nghiệp vụ:
    1. Dùng PostingDate (ngày hạch toán trong Value Entry) làm mốc thời gian
       — đây là ngày NAV ghi nhận giao dịch sản xuất, point-in-time correct.
    2. Loại bản ghi có PostingDate là NaT (không xác định được tuần).
    3. ValuedQty có thể âm (điều chỉnh, trả hàng) — giữ nguyên dấu âm
       trong tổng tuần để phản ánh đúng sản lượng ròng.
    """
    df = prod_raw.copy()

    df["PostingDate"] = pd.to_datetime(df["PostingDate"], errors="coerce")

    nat_count = df["PostingDate"].isna().sum()
    if nat_count > 0:
        logger.warning(
            f"[Production] Loại {nat_count:,} dòng có PostingDate = NaT."
        )
    df = df.dropna(subset=["PostingDate"])

    _warn_midnight_boundary(df, "PostingDate", "Production")

    df["week_start"] = _to_week_start(df["PostingDate"])

    df["ValuedQty"] = pd.to_numeric(df["ValuedQty"], errors="coerce").fillna(0)

    logger.info(
        f"[Production] Sau tiền xử lý: {len(df):,} dòng hợp lệ, "
        f"sẵn sàng gộp theo tuần."
    )

    # Tổng sản lượng mỗi tuần + đếm số bản ghi (transaction count)
    weekly_prod = (
        df.groupby("week_start")
        .agg(
            ProductionVolume=("ValuedQty", "sum"),
            production_txn_count=("ValuedQty", "count"),
        )
        .reset_index()
    )

    logger.info(f"[Production] Gộp xong: {len(weekly_prod):,} tuần.")
    return weekly_prod


def _aggregate_delay_weekly(delay_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Gộp dữ liệu Delay theo tuần — tỷ lệ đơn hàng bị trễ.

    Nguồn: cmt_delay_results.csv (từ [Sales Order Header]).
    Biến: DelayRate = mean(IsDelayed) mỗi tuần (tỷ lệ 0–1).

    Logic nghiệp vụ:
    1. Gán vào tuần theo ActualShipDate (ngày giao thực tế) — IsDelayed chỉ
       xác định được SAU khi đã giao (chống look-ahead bias).
    2. Loại đơn hàng chưa giao (ActualShipDate = NaT).
    3. DelayRate không áp dụng trọng số — mỗi đơn hàng đều quan trọng
       như nhau về cam kết giao hàng, bất kể quy mô.
    """
    df = delay_raw.copy()

    df["ActualShipDate"] = pd.to_datetime(df["ActualShipDate"], errors="coerce")

    nat_count = df["ActualShipDate"].isna().sum()
    if nat_count > 0:
        logger.warning(
            f"[Delay] Loại {nat_count:,} đơn hàng chưa giao "
            f"(ActualShipDate = NaT)."
        )
    df = df.dropna(subset=["ActualShipDate"])

    _warn_midnight_boundary(df, "ActualShipDate", "Delay")

    df["week_start"] = _to_week_start(df["ActualShipDate"])

    if "IsDelayed" in df.columns:
        df["IsDelayed"] = pd.to_numeric(df["IsDelayed"], errors="coerce")
        invalid_delay = df["IsDelayed"].isna().sum()
        if invalid_delay > 0:
            logger.warning(
                f"[Delay] {invalid_delay:,} dòng có IsDelayed không ép được "
                f"sang số — loại khỏi tính toán."
            )
        df = df.dropna(subset=["IsDelayed"])
    else:
        logger.info(
            "[Delay] Không tìm thấy cột 'IsDelayed' — tính tự động: "
            "IsDelayed = 1 nếu ActualShipDate > PlannedShipmentDate."
        )
        df["PlannedShipmentDate"] = pd.to_datetime(
            df["PlannedShipmentDate"], errors="coerce"
        )
        df["IsDelayed"] = (df["ActualShipDate"] > df["PlannedShipmentDate"]).astype(int)

    before_dedup = len(df)
    df = df.sort_values("ActualShipDate").drop_duplicates(
        subset=["OrderNo", "week_start"], keep="last"
    )
    dedup_dropped = before_dedup - len(df)
    if dedup_dropped > 0:
        logger.warning(
            f"[Delay] Đã drop {dedup_dropped:,} dòng trùng lặp "
            f"(cùng OrderNo + cùng tuần)."
        )

    logger.info(
        f"[Delay] Sau tiền xử lý: {len(df):,} dòng hợp lệ, "
        f"sẵn sàng gộp theo tuần."
    )

    weekly_delay = (
        df.groupby("week_start")
        .agg(
            DelayRate=("IsDelayed", "mean"),
            delay_order_count=("IsDelayed", "count"),
        )
        .reset_index()
    )

    logger.info(f"[Delay] Gộp xong: {len(weekly_delay):,} tuần.")
    return weekly_delay


def _aggregate_demand_weekly(demand_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Gộp dữ liệu OrderDemand theo tuần — tổng khối lượng đặt hàng.

    Nguồn: order_demand.csv (từ [Sales Order Line] JOIN [Sales Order Header]).
    Biến: OrderDemand = SUM(Quantity) mỗi tuần.

    Logic nghiệp vụ:
    1. Dùng ShipmentDate (ngày giao dự kiến từ Sales Order Line) làm mốc —
       phản ánh thời điểm áp lực đơn hàng tác động lên sản xuất.
    2. Quantity > 0 đã được lọc ở Tầng 1 (SQL WHERE).
    3. OrderDemand phản ánh ÁP LỰC ĐƠN HÀNG — biến động lực đầu vào trong
       chuỗi nhân quả: OrderDemand → ProductionVolume → DelayRate.
    """
    df = demand_raw.copy()

    df["ShipmentDate"] = pd.to_datetime(df["ShipmentDate"], errors="coerce")

    nat_count = df["ShipmentDate"].isna().sum()
    if nat_count > 0:
        logger.warning(
            f"[Demand] Loại {nat_count:,} dòng có ShipmentDate = NaT."
        )
    df = df.dropna(subset=["ShipmentDate"])

    _warn_midnight_boundary(df, "ShipmentDate", "Demand")

    df["week_start"] = _to_week_start(df["ShipmentDate"])

    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce").fillna(0)

    logger.info(
        f"[Demand] Sau tiền xử lý: {len(df):,} dòng hợp lệ, "
        f"sẵn sàng gộp theo tuần."
    )

    # Tổng khối lượng đặt hàng + đếm số dòng đơn hàng (line count)
    weekly_demand = (
        df.groupby("week_start")
        .agg(
            OrderDemand=("Quantity", "sum"),
            demand_line_count=("Quantity", "count"),
        )
        .reset_index()
    )

    logger.info(f"[Demand] Gộp xong: {len(weekly_demand):,} tuần.")
    return weekly_demand


# =====================================================================
# MERGE + REINDEX + FORWARD-FILL + CỜ is_filled
# =====================================================================

def _merge_weekly_datasets(
    weekly_prod: pd.DataFrame,
    weekly_delay: pd.DataFrame,
    weekly_demand: pd.DataFrame,
) -> pd.DataFrame:
    """
    Merge 3 dataset tuần vào 1 bảng chung theo `week_start`.

    Dùng outer join để giữ TẤT CẢ các tuần từ mọi nguồn — nếu một tuần
    chỉ có Production mà không có Delay (vd: không đơn hàng nào hoàn thành
    giao trong tuần đó), tuần đó vẫn tồn tại.
    """
    # Merge Production + Delay
    merged = pd.merge(
        weekly_prod[["week_start", "ProductionVolume"]],
        weekly_delay[["week_start", "DelayRate"]],
        on="week_start",
        how="outer",
    )

    # Merge tiếp OrderDemand
    merged = pd.merge(
        merged,
        weekly_demand[["week_start", "OrderDemand"]],
        on="week_start",
        how="outer",
    )

    merged = merged.sort_values("week_start").reset_index(drop=True)

    logger.info(
        f"Sau merge 3 nguồn: {len(merged):,} tuần, "
        f"từ {merged['week_start'].min().date()} "
        f"đến {merged['week_start'].max().date()}."
    )

    return merged


def _reindex_and_fill(df: pd.DataFrame) -> pd.DataFrame:
    """
    Reindex lưới tuần đều đặn + forward-fill + đánh dấu is_filled.

    Chiến lược xử lý khoảng trống (CLAUDE.md mục 8):
    1. Reindex về lưới đều W-MON (mỗi tuần 1 dòng) từ tuần đầu đến tuần cuối.
    2. ProductionVolume, OrderDemand (TỔNG): fillna(0) — tuần không có hoạt
       động là thông tin thật ("nhà máy nghỉ", "không có đơn hàng").
    3. DelayRate (TỶ LỆ): forward-fill limit=4 tuần liên tiếp (CLAUDE.md
       mục 8.1) — giả định trạng thái delay không đổi trong ngắn hạn.
       Khoảng trống > 4 tuần giữ NaN (structural gap, CLAUDE.md mục 8.2).
    4. Đánh dấu cột is_filled (True = tuần được forward-fill hoặc fillna).
    """
    result = df.copy()

    # --- Bước 1: Reindex lưới tuần đều đặn ---
    min_week = result["week_start"].min()
    max_week = result["week_start"].max()
    full_weeks = pd.date_range(start=min_week, end=max_week, freq="W-MON")

    result = result.set_index("week_start").reindex(full_weeks)
    result.index.name = "week_start"
    result = result.reset_index()

    weeks_added = len(full_weeks) - len(df)
    if weeks_added > 0:
        logger.info(
            f"[Reindex] Đã thêm {weeks_added} tuần trống vào lưới "
            f"(tổng: {len(full_weeks)} tuần từ {min_week.date()} → {max_week.date()})."
        )

    # --- Bước 2: Ghi nhận vị trí NaN gốc TRƯỚC khi fill ---
    delay_was_nan = result["DelayRate"].isna()
    prod_was_nan = result["ProductionVolume"].isna()
    demand_was_nan = result["OrderDemand"].isna()

    nan_delay_count = delay_was_nan.sum()
    nan_prod_count = prod_was_nan.sum()
    nan_demand_count = demand_was_nan.sum()

    if nan_delay_count > 0:
        logger.info(f"[Fill] DelayRate: {nan_delay_count:,} tuần NaN trước fill.")
    if nan_prod_count > 0:
        logger.info(f"[Fill] ProductionVolume: {nan_prod_count:,} tuần NaN trước fill.")
    if nan_demand_count > 0:
        logger.info(f"[Fill] OrderDemand: {nan_demand_count:,} tuần NaN trước fill.")

    # --- Bước 3: Fill theo chiến lược phù hợp từng biến ---
    # DelayRate (tỷ lệ): forward-fill limit=4 (CLAUDE.md mục 8.1)
    result["DelayRate"] = result["DelayRate"].ffill(limit=4)

    # ProductionVolume, OrderDemand (tổng): fillna(0) — tuần rỗng = không
    # có hoạt động, giá trị 0 có ý nghĩa kinh tế thật
    result["ProductionVolume"] = result["ProductionVolume"].fillna(0)
    result["OrderDemand"] = result["OrderDemand"].fillna(0)

    # --- Bước 4: Đánh dấu is_filled ---
    # is_filled = True nếu giá trị GỐC là NaN VÀ sau fill không còn NaN
    result["is_filled_delay"] = (
        delay_was_nan & result["DelayRate"].notna()
    ).astype(int)

    # Log kết quả fill
    filled_delay = result["is_filled_delay"].sum()
    remaining_nan_delay = result["DelayRate"].isna().sum()

    logger.info(
        f"[Fill] DelayRate: đã forward-fill {filled_delay:,} tuần, "
        f"còn {remaining_nan_delay:,} tuần NaN (gap > 4 tuần)."
    )

    if remaining_nan_delay > 0:
        logger.warning(
            f"[Fill] DelayRate vẫn còn {remaining_nan_delay:,} tuần NaN "
            f"(khoảng trống > 4 tuần liên tiếp, structural gap). "
            f"Các tuần này sẽ bị drop trước khi phân tích (Tầng 3)."
        )

    return result


# =====================================================================
# HÀM CHÍNH — ĐIỀU PHỐI TOÀN BỘ TẦNG 2
# =====================================================================

def run_phase0(snapshot_dir: str = None) -> str:
    """
    Hàm chính của Tầng 2 (Phase 0): tái cấu trúc dữ liệu thô → dataset tuần.

    Quy trình:
        1. Tìm/xác nhận thư mục snapshot.
        2. Đọc 3 file CSV nguyên trạng (production_volume, cmt_delay_results,
           order_demand).
        3. Gộp Production, Delay, OrderDemand theo tuần.
        4. Merge 3 nguồn vào 1 bảng chung.
        5. Reindex lưới tuần đều + forward-fill + gắn cờ is_filled.
        6. Ghi kết quả ra `data/processed/causal_weekly_dataset.csv`.

    Trả về:
        Đường dẫn tuyệt đối đến file output.
    """
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("Phase 0 (Tái cấu trúc dữ liệu — Phương án A) bắt đầu.")
    logger.info("=" * 60)

    # -----------------------------------------------------------------
    # Bước 1: Xác định thư mục snapshot
    # -----------------------------------------------------------------
    if snapshot_dir is None:
        snapshot_dir = _find_latest_snapshot()
    else:
        if not os.path.isdir(snapshot_dir):
            raise FileNotFoundError(
                f"Thư mục snapshot không tồn tại: {snapshot_dir}"
            )
        logger.info(f"Sử dụng snapshot được chỉ định: {snapshot_dir}")

    # -----------------------------------------------------------------
    # Bước 2: Đọc 3 file CSV nguyên trạng từ snapshot
    # -----------------------------------------------------------------
    prod_raw = _load_raw_csv(snapshot_dir, "production_volume.csv")
    delay_raw = _load_raw_csv(snapshot_dir, "cmt_delay_results.csv")
    demand_raw = _load_raw_csv(snapshot_dir, "order_demand.csv")

    # -----------------------------------------------------------------
    # Bước 3: Gộp từng nguồn theo tuần
    # -----------------------------------------------------------------
    logger.info("-" * 40)
    logger.info("Bắt đầu gộp dữ liệu Production theo tuần...")
    weekly_prod = _aggregate_production_weekly(prod_raw)

    logger.info("-" * 40)
    logger.info("Bắt đầu gộp dữ liệu Delay theo tuần...")
    weekly_delay = _aggregate_delay_weekly(delay_raw)

    logger.info("-" * 40)
    logger.info("Bắt đầu gộp dữ liệu OrderDemand theo tuần...")
    weekly_demand = _aggregate_demand_weekly(demand_raw)

    # -----------------------------------------------------------------
    # Bước 4: Merge 3 nguồn vào 1 bảng chung
    # -----------------------------------------------------------------
    logger.info("-" * 40)
    logger.info("Merge 3 dataset tuần...")
    merged = _merge_weekly_datasets(weekly_prod, weekly_delay, weekly_demand)

    # -----------------------------------------------------------------
    # Bước 5: Reindex + forward-fill + cờ is_filled
    # -----------------------------------------------------------------
    logger.info("-" * 40)
    logger.info("Reindex lưới tuần + forward-fill DelayRate...")
    final_dataset = _reindex_and_fill(merged)

    # -----------------------------------------------------------------
    # Bước 6: Ghi kết quả ra data/processed/
    # -----------------------------------------------------------------
    output_path = os.path.join(
        get_base_dir(), "data", "processed", "causal_weekly_dataset.csv"
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    output_columns = [
        "week_start",
        "ProductionVolume",
        "DelayRate",
        "OrderDemand",
        "is_filled_delay",
    ]

    final_dataset = final_dataset[output_columns]
    final_dataset.to_csv(output_path, index=False, encoding="utf-8-sig")

    # -----------------------------------------------------------------
    # Tóm tắt dataset — ĐIỂM DỪNG XÁC NHẬN 1 (skill.md)
    # -----------------------------------------------------------------
    total_weeks = len(final_dataset)
    date_range_start = final_dataset["week_start"].min()
    date_range_end = final_dataset["week_start"].max()
    filled_delay_count = final_dataset["is_filled_delay"].sum()
    remaining_nan = final_dataset["DelayRate"].isna().sum()

    # Drop tuần có NaN trước khi báo cáo số tuần phân tích được
    usable_weeks = total_weeks - remaining_nan

    logger.info("=" * 60)
    logger.info("TÓM TẮT DATASET TUẦN (cho điểm dừng xác nhận):")
    logger.info(f"  - Tổng số tuần          : {total_weeks:,}")
    logger.info(f"  - Tuần phân tích được   : {usable_weeks:,}")
    logger.info(f"  - Khoảng thời gian      : {date_range_start} → {date_range_end}")
    logger.info(f"  - Tuần forward-fill Delay: {filled_delay_count:,}")
    logger.info(f"  - Tuần còn NaN (drop)   : {remaining_nan:,}")
    logger.info(f"  - File output           : {output_path}")
    logger.info("=" * 60)

    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info(f"Phase 0 hoàn tất trong {elapsed:.1f}s.")

    return output_path


# =====================================================================
# ENTRY POINT — cho phép chạy script độc lập (CLAUDE.md mục 3.5)
# =====================================================================
if __name__ == "__main__":
    try:
        output = run_phase0()
        logger.info(f"Kết quả lưu tại: {output}")
    except Exception:
        logger.exception("Phase 0 thất bại — xem traceback ở trên.")
        sys.exit(1)
