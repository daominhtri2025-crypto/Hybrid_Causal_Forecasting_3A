"""
Tầng 2 — Phase 0: Tái cấu trúc & Đồng bộ hóa dữ liệu thô thành dataset tuần.

Mục đích:
    Đọc 3 file CSV nguyên trạng từ snapshot mới nhất trong `data/raw/`, thực hiện:
      (1) Đồng bộ trục thời gian — chống look-ahead bias bằng cách gán tuần theo
          `ActualEndDate` (OEE), `ActualShipDate` (Delay), và `PostingDate`
          (Revenue) thay vì dùng ngày kế hoạch (ARCHITECTURE_4_tang.md, mục 2.1).
      (2) Tính trung bình tuần có trọng số — `np.average(OEE_Score, weights=RealQty)`
          phản ánh khối lượng sản xuất thực tế (ARCHITECTURE, mục 2.3).
      (3) Nội suy NaN có giới hạn — `interpolate(limit=2)` cho tỷ lệ (OEE,
          DelayRate), `fillna(0)` cho tổng/đếm (Revenue, OrderVolume). Thêm cột
          `is_interpolated_*` để Tầng 3 biết dòng nào bị can thiệp
          (ARCHITECTURE, mục 2.4).
      (4) Giám sát bản ghi cận nửa đêm (22:00–02:00) — ghi WARNING kèm OrderNo
          cụ thể (ARCHITECTURE, mục 2.2).
    và ghi kết quả ra `data/processed/causal_weekly_dataset.csv`.

Input:  `data/raw/snapshot_YYYYMMDD_HHMM/cmt_oee_results.csv`,
        `data/raw/snapshot_YYYYMMDD_HHMM/cmt_delay_results.csv`,
        `data/raw/snapshot_YYYYMMDD_HHMM/fob_revenue.csv`.
        (Đọc từ snapshot MỚI NHẤT nếu không chỉ định cụ thể.)

Output: `data/processed/causal_weekly_dataset.csv`
        Các cột: week_start, OEE_Score, DelayRate, Revenue, OrderVolume,
                 is_interpolated_oee, is_interpolated_delay.

Sở hữu: Role A — Data Engineering (skill.md).
Tuân thủ: CLAUDE.md mục 2 (bất biến raw), mục 3 (coding), mục 7 (logging).

Thay đổi so với bản trước: Rebuild hoàn toàn (Phương án 3-A). Bản cũ dùng
    `PlannedShipmentDate` gây look-ahead bias nghiêm trọng, dùng `mean()` đơn
    giản thay vì trọng số, và gán 0 vô điều kiện cho NaN.
"""

import os
import sys
import glob
from datetime import datetime, timedelta

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
    trùng với thứ tự thời gian, nên thư mục cuối cùng sau khi sort chính
    là snapshot mới nhất. Không cần parse timestamp phức tạp.

    Raises:
        FileNotFoundError nếu không tìm thấy snapshot nào — đúng theo
        hợp đồng skill.md: Phase X thiếu input của Phase Y phải báo lỗi
        rõ ràng, không tự tính lại.
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

    Tuân thủ nguyên tắc bất biến dữ liệu (CLAUDE.md mục 2): hàm này chỉ
    đọc và trả về DataFrame nguyên trạng. Mọi transform sẽ thực hiện trên
    bản copy ở các hàm xử lý phía sau.

    Raises:
        FileNotFoundError nếu file không tồn tại — kèm hướng dẫn chạy
        Tầng 1 trước (skill.md, quy tắc cứng).
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
    Giám sát bản ghi có timestamp nằm trong khung ±2 giờ quanh nửa đêm.

    Lý do (ARCHITECTURE_4_tang.md, mục 2.2): dự án tạm dùng quy tắc ngày
    dương lịch chuẩn (00:00–23:59) để xác định ngày/tuần. Những bản ghi có
    timestamp trong khoảng 22:00–02:00 có rủi ro cao bị gán sai ngày/tuần
    nếu ca làm việc thực tế không trùng ranh giới dương lịch.

    Script KHÔNG tự sửa — chỉ ghi WARNING kèm OrderNo cụ thể để Anh Béo
    review định kỳ và quyết định có cần bổ sung quy tắc ca làm việc chính
    thức hay không.

    Trả về: số lượng bản ghi nằm trong khung cận nửa đêm.
    """
    if date_col not in df.columns:
        return 0

    dt_series = pd.to_datetime(df[date_col], errors="coerce")
    hours = dt_series.dt.hour

    # Khung cận nửa đêm: 22:00–23:59 (giờ >= 22) hoặc 00:00–01:59 (giờ < 2)
    mask = (hours >= 22) | (hours < 2)
    boundary_df = df[mask]
    count = len(boundary_df)

    if count > 0:
        # Liệt kê tối đa 10 OrderNo đầu tiên để log không quá dài,
        # nhưng vẫn ghi rõ TỔNG SỐ bản ghi bị ảnh hưởng (CLAUDE.md mục 7.3:
        # bắt buộc ghi rõ số lượng dòng).
        sample_orders = ""
        if "OrderNo" in boundary_df.columns:
            sample_list = boundary_df["OrderNo"].head(10).tolist()
            sample_orders = f" — OrderNo mẫu: {sample_list}"
            if count > 10:
                sample_orders += f" (và {count - 10} đơn hàng khác)"

        logger.warning(
            f"[{source_name}] Phát hiện {count:,} bản ghi có {date_col} "
            f"trong khung cận nửa đêm (22:00–02:00) — có rủi ro gán sai "
            f"ngày/tuần nếu ca làm việc không trùng ranh giới dương lịch."
            f"{sample_orders}"
        )

    return count


def _to_week_start(dt_series: pd.Series) -> pd.Series:
    """
    Chuyển đổi cột datetime thành ngày đầu tuần (thứ Hai - Monday).

    Công thức: lùi về thứ Hai gần nhất bằng cách trừ đi `weekday()`
    (Monday=0, Sunday=6). Kết quả là ngày bắt đầu tuần ISO, dùng làm
    trục thời gian chung khi merge 3 nguồn dữ liệu.
    """
    dt = pd.to_datetime(dt_series, errors="coerce")
    return dt.dt.normalize() - pd.to_timedelta(dt.dt.weekday, unit="D")


# =====================================================================
# XỬ LÝ TỪNG NGUỒN DỮ LIỆU → GỘP THEO TUẦN
# =====================================================================

def _aggregate_oee_weekly(oee_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Gộp dữ liệu OEE theo tuần — trung bình có trọng số theo RealQty.

    Logic nghiệp vụ quan trọng (ARCHITECTURE_4_tang.md, mục 2.1 + 2.3):

    1. CHỐNG LOOK-AHEAD BIAS: Gán `OEE_Score` vào tuần theo `ActualEndDate`
       (ngày hoàn thành thực tế), KHÔNG dùng `PlannedShipmentDate`. Lý do:
       `OEE_Score` được tính từ `RealQty` — giá trị này chỉ BIẾT ĐƯỢC sau
       khi đơn hàng hoàn thành. Gán vào tuần theo ngày kế hoạch
       (`PlannedShipmentDate`, thường sớm hơn) sẽ tạo look-ahead bias —
       gán giá trị "biết sau" vào tuần "trước khi biết".

    2. LOẠI ĐƠN HÀNG CHƯA HOÀN THÀNH: Đơn hàng có `ActualEndDate` là NaT
       (chưa hoàn thành tại thời điểm snapshot) bị loại khỏi tính toán —
       KHÔNG gán 0 hay NaN giả cho một chỉ số chưa tồn tại.

    3. TRỌNG SỐ THEO RealQty: Dùng `np.average(OEE_Score, weights=RealQty)`
       thay vì `mean()` đơn giản — phản ánh đúng khối lượng công việc thực
       tế trong tuần. Đơn hàng sản xuất 10,000 sản phẩm phải có ảnh hưởng
       lớn hơn đơn hàng 100 sản phẩm khi tính OEE trung bình tuần.

    4. KHÔNG TỰ TÍNH LẠI OEE_Score: Dùng đúng giá trị `OEE_Score` đã có sẵn
       trong `cmt_oee_results.csv` — tuân thủ CLAUDE.md mục 2 điểm 4.
    """
    df = oee_raw.copy()

    # --- Ép kiểu cột thời gian ---
    df["ActualEndDate"] = pd.to_datetime(df["ActualEndDate"], errors="coerce")

    # --- Loại đơn hàng chưa hoàn thành (ActualEndDate là NaT) ---
    # Đây là đơn hàng đang sản xuất tại thời điểm snapshot — OEE_Score
    # của chúng chưa tồn tại, không được phép gán giá trị giả.
    nat_count = df["ActualEndDate"].isna().sum()
    if nat_count > 0:
        logger.warning(
            f"[OEE] Loại {nat_count:,} đơn hàng chưa hoàn thành "
            f"(ActualEndDate = NaT) — OEE_Score chưa tồn tại, không gán giả."
        )
    df = df.dropna(subset=["ActualEndDate"])

    # --- Giám sát bản ghi cận nửa đêm ---
    _warn_midnight_boundary(df, "ActualEndDate", "OEE")

    # --- Gán tuần theo ActualEndDate (KHÔNG phải PlannedShipmentDate) ---
    df["week_start"] = _to_week_start(df["ActualEndDate"])

    # --- Ép kiểu cột số liệu ---
    df["OEE_Score"] = pd.to_numeric(df["OEE_Score"], errors="coerce")
    df["RealQty"] = pd.to_numeric(df["RealQty"], errors="coerce")

    # Loại dòng có OEE_Score hoặc RealQty không hợp lệ (NaN sau ép kiểu)
    invalid_count = df[["OEE_Score", "RealQty"]].isna().any(axis=1).sum()
    if invalid_count > 0:
        logger.warning(
            f"[OEE] Loại {invalid_count:,} dòng có OEE_Score hoặc RealQty "
            f"không ép được sang số (NaN sau pd.to_numeric)."
        )
    df = df.dropna(subset=["OEE_Score", "RealQty"])

    # --- Loại dòng trùng OrderNo trong cùng 1 tuần ---
    # Nếu cùng 1 OrderNo xuất hiện nhiều lần (do lỗi trích xuất hoặc
    # cập nhật bản ghi), giữ bản ghi cuối cùng (theo thời gian) để tránh
    # đếm trùng trọng số.
    before_dedup = len(df)
    df = df.sort_values("ActualEndDate").drop_duplicates(
        subset=["OrderNo", "week_start"], keep="last"
    )
    dedup_dropped = before_dedup - len(df)
    if dedup_dropped > 0:
        logger.warning(
            f"[OEE] Đã drop {dedup_dropped:,} dòng trùng lặp "
            f"(cùng OrderNo + cùng tuần)."
        )

    logger.info(
        f"[OEE] Sau tiền xử lý: {len(df):,} dòng hợp lệ, "
        f"sẵn sàng gộp theo tuần."
    )

    # --- Gộp theo tuần: trung bình có trọng số ---
    def _weighted_oee(group: pd.DataFrame) -> pd.Series:
        """
        Tính OEE trung bình tuần có trọng số theo RealQty.

        Trường hợp đặc biệt: nếu tổng RealQty = 0 trong tuần (tất cả đơn
        hàng đều có sản lượng = 0), không thể chia cho 0 → fallback về
        mean() đơn giản và ghi WARNING.
        """
        total_qty = group["RealQty"].sum()
        if total_qty > 0:
            weighted_avg = np.average(
                group["OEE_Score"], weights=group["RealQty"]
            )
        else:
            weighted_avg = group["OEE_Score"].mean()
            # group.name chứa giá trị key của groupby (week_start) vì
            # include_groups=False loại cột groupby khỏi DataFrame con.
            week_label = group.name.date() if hasattr(group.name, "date") else group.name
            logger.warning(
                f"[OEE] Tuần {week_label}: "
                f"tổng RealQty = 0, fallback về mean() đơn giản."
            )

        return pd.Series({
            "OEE_Score": weighted_avg,
            "oee_order_count": len(group),
        })

    weekly_oee = (
        df.groupby("week_start")
        .apply(_weighted_oee, include_groups=False)
        .reset_index()
    )

    logger.info(f"[OEE] Gộp xong: {len(weekly_oee):,} tuần.")
    return weekly_oee


def _aggregate_delay_weekly(delay_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Gộp dữ liệu Delay theo tuần — tính tỷ lệ đơn hàng bị trễ.

    Logic nghiệp vụ:

    1. CHỐNG LOOK-AHEAD BIAS: Gán vào tuần theo `ActualShipDate` (ngày giao
       hàng thực tế từ Sales Order Header) — vì `IsDelayed` chỉ xác định
       được SAU khi đơn hàng đã giao (so sánh `ActualShipDate` vs
       `PlannedShipmentDate`).

    2. LOẠI ĐƠN HÀNG CHƯA GIAO: Đơn hàng có `ActualShipDate` là NaT
       → chưa thể xác định trễ hay không → loại khỏi tính toán.

    3. DelayRate = số đơn trễ / tổng số đơn trong tuần (tỷ lệ đơn giản).
       Không áp dụng trọng số RealQty ở đây vì kiến trúc chỉ quy định
       weighting cho OEE_Score (ARCHITECTURE, mục 2.3). DelayRate phản ánh
       "bao nhiêu phần trăm đơn hàng bị trễ" — mỗi đơn hàng đều quan trọng
       như nhau về mặt cam kết giao hàng, bất kể quy mô sản xuất.
    """
    df = delay_raw.copy()

    # --- Ép kiểu cột thời gian ---
    df["ActualShipDate"] = pd.to_datetime(df["ActualShipDate"], errors="coerce")

    # --- Loại đơn hàng chưa giao ---
    nat_count = df["ActualShipDate"].isna().sum()
    if nat_count > 0:
        logger.warning(
            f"[Delay] Loại {nat_count:,} đơn hàng chưa giao "
            f"(ActualShipDate = NaT) — chưa thể xác định trễ hay không."
        )
    df = df.dropna(subset=["ActualShipDate"])

    # --- Giám sát bản ghi cận nửa đêm ---
    _warn_midnight_boundary(df, "ActualShipDate", "Delay")

    # --- Gán tuần theo ActualShipDate ---
    df["week_start"] = _to_week_start(df["ActualShipDate"])

    # --- Xử lý cột IsDelayed ---
    # Ép sang số: 1 = trễ, 0 = đúng hạn. Nếu cột chứa True/False hoặc
    # chuỗi "Yes"/"No", pd.to_numeric sẽ thất bại → xử lý riêng.
    if "IsDelayed" in df.columns:
        # Thử ép trực tiếp trước
        df["IsDelayed"] = pd.to_numeric(df["IsDelayed"], errors="coerce")

        invalid_delay = df["IsDelayed"].isna().sum()
        if invalid_delay > 0:
            logger.warning(
                f"[Delay] {invalid_delay:,} dòng có IsDelayed không ép được "
                f"sang số (NaN) — loại khỏi tính toán DelayRate."
            )
        df = df.dropna(subset=["IsDelayed"])
    else:
        # Nếu không có cột IsDelayed, thử tính từ PlannedShipmentDate vs
        # ActualEndDate — trễ nếu hoàn thành SAU ngày kế hoạch.
        # Đây KHÔNG vi phạm CLAUDE.md mục 2 điểm 4 vì cmt_delay_results
        # chưa có sẵn trường IsDelayed dạng số.
        logger.info(
            "[Delay] Không tìm thấy cột 'IsDelayed' — tính tự động: "
            "IsDelayed = 1 nếu ActualShipDate > PlannedShipmentDate."
        )
        df["PlannedShipmentDate"] = pd.to_datetime(
            df["PlannedShipmentDate"], errors="coerce"
        )
        df["IsDelayed"] = (df["ActualShipDate"] > df["PlannedShipmentDate"]).astype(int)

    # --- Loại dòng trùng OrderNo trong cùng 1 tuần ---
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

    # --- Gộp theo tuần: DelayRate = trung bình IsDelayed (tỷ lệ 0–1) ---
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


def _aggregate_revenue_weekly(revenue_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Gộp dữ liệu Revenue theo tuần — tổng doanh thu và số đơn hàng.

    Logic nghiệp vụ:

    1. MỐC THỜI GIAN: Dùng `PostingDate` (ngày hạch toán) — đây là thời
       điểm doanh thu được ghi nhận trong sổ cái. Khác với OEE dùng
       `ActualEndDate`, Delay dùng `ActualShipDate`. Cả ba đều là "ngày
       biết được" — nhất quán về triết lý point-in-time correctness
       (ARCHITECTURE, mục 2.1).

    2. Revenue và OrderVolume là tổng/đếm — giá trị 0 có ý nghĩa thật
       ("không có giao dịch trong tuần đó"). Vì vậy khi nội suy sau này
       sẽ dùng `fillna(0)` thay vì `interpolate()` (ARCHITECTURE, mục 2.4).
    """
    df = revenue_raw.copy()

    # --- Ép kiểu cột thời gian ---
    df["PostingDate"] = pd.to_datetime(df["PostingDate"], errors="coerce")

    # Loại dòng không parse được PostingDate
    nat_count = df["PostingDate"].isna().sum()
    if nat_count > 0:
        logger.warning(
            f"[Revenue] Loại {nat_count:,} dòng có PostingDate không hợp lệ "
            f"(NaT sau ép kiểu datetime)."
        )
    df = df.dropna(subset=["PostingDate"])

    # --- Giám sát bản ghi cận nửa đêm ---
    _warn_midnight_boundary(df, "PostingDate", "Revenue")

    # --- Gán tuần theo PostingDate ---
    df["week_start"] = _to_week_start(df["PostingDate"])

    # --- Ép kiểu cột Revenue ---
    # Tên cột Revenue có thể khác tùy database — Anh Béo xác nhận tên
    # chính xác trước khi chạy chính thức. Thử một số tên phổ biến.
    revenue_col = None
    for candidate in ["Revenue", "FOB_Revenue", "TotalRevenue", "Amount"]:
        if candidate in df.columns:
            revenue_col = candidate
            break

    if revenue_col is None:
        logger.warning(
            "[Revenue] Không tìm thấy cột Revenue — thử dùng cột số "
            "đầu tiên sau ShipmentDate. Anh Béo cần xác nhận tên cột đúng."
        )
        # Fallback: tìm cột số đầu tiên (ngoài week_start)
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if numeric_cols:
            revenue_col = numeric_cols[0]
            logger.info(f"[Revenue] Sử dụng cột '{revenue_col}' làm Revenue.")
        else:
            raise ValueError(
                "Không tìm thấy cột số nào trong fob_revenue.csv để dùng "
                "làm Revenue. Kiểm tra lại cấu trúc file."
            )

    df["Revenue"] = pd.to_numeric(df[revenue_col], errors="coerce").fillna(0)

    logger.info(
        f"[Revenue] Sau tiền xử lý: {len(df):,} dòng hợp lệ, "
        f"sẵn sàng gộp theo tuần."
    )

    # --- Gộp theo tuần: tổng Revenue + đếm số đơn (OrderVolume) ---
    weekly_revenue = (
        df.groupby("week_start")
        .agg(
            Revenue=("Revenue", "sum"),
            OrderVolume=("Revenue", "count"),
        )
        .reset_index()
    )

    logger.info(f"[Revenue] Gộp xong: {len(weekly_revenue):,} tuần.")
    return weekly_revenue


# =====================================================================
# MERGE + NỘI SUY + CỜ is_interpolated
# =====================================================================

def _merge_weekly_datasets(
    weekly_oee: pd.DataFrame,
    weekly_delay: pd.DataFrame,
    weekly_revenue: pd.DataFrame,
) -> pd.DataFrame:
    """
    Merge 3 dataset tuần vào 1 bảng chung theo `week_start`.

    Dùng outer join để giữ TẤT CẢ các tuần từ mọi nguồn — nếu một tuần
    chỉ có Revenue mà không có OEE (vd: không đơn hàng sản xuất nào hoàn
    thành trong tuần đó), tuần đó vẫn tồn tại với OEE_Score = NaN (sẽ
    được xử lý bởi bước nội suy phía sau).
    """
    # Merge OEE + Delay trước (cùng dùng ActualEndDate làm mốc)
    merged = pd.merge(
        weekly_oee[["week_start", "OEE_Score"]],
        weekly_delay[["week_start", "DelayRate"]],
        on="week_start",
        how="outer",
    )

    # Merge tiếp Revenue (dùng ShipmentDate làm mốc — có thể lệch tuần
    # so với OEE/Delay, outer join đảm bảo không mất tuần nào)
    merged = pd.merge(
        merged,
        weekly_revenue[["week_start", "Revenue", "OrderVolume"]],
        on="week_start",
        how="outer",
    )

    # Sắp xếp theo thời gian — bắt buộc cho chronological split sau này
    # (CLAUDE.md mục 3.4) và cho interpolate() hoạt động đúng
    merged = merged.sort_values("week_start").reset_index(drop=True)

    logger.info(
        f"Sau merge 3 nguồn: {len(merged):,} tuần, "
        f"từ {merged['week_start'].min().date()} "
        f"đến {merged['week_start'].max().date()}."
    )

    return merged


def _interpolate_with_flags(df: pd.DataFrame) -> pd.DataFrame:
    """
    Nội suy NaN có giới hạn và thêm cột cờ `is_interpolated_*`.

    Chiến lược nội suy (ARCHITECTURE_4_tang.md, mục 2.4):

    1. OEE_Score, DelayRate (là TỶ LỆ — cần có mẫu mới có ý nghĩa):
       - Dùng `interpolate(method='linear', limit=2)` — nội suy tuyến
         tính tối đa 2 tuần liên tiếp.
       - Vượt quá 2 tuần liên tiếp → giữ NaN và ghi WARNING.
       - Lý do giới hạn: nội suy không giới hạn trên chuỗi thời gian
         ngắn (vài chục tuần) có thể tạo ra các giá trị vô nghĩa, đặc
         biệt khi khoảng trống dài nằm ở đầu/cuối chuỗi.

    2. Revenue, OrderVolume (là TỔNG/ĐẾM — giá trị 0 có ý nghĩa thật):
       - Dùng `fillna(0)` — "không có giao dịch" là thông tin hợp lệ.
       - KHÔNG dùng interpolate vì nội suy tổng doanh thu giữa 2 tuần
         không có ý nghĩa kinh tế (Revenue không liên tục như tỷ lệ).

    3. Cột cờ `is_interpolated_*` (boolean 0/1):
       - Đánh dấu chính xác dòng nào bị can thiệp nội suy, để Tầng 3
         chạy kiểm định độ nhạy — so sánh kết quả trên dữ liệu đầy đủ
         vs. dữ liệu chỉ gồm các tuần "sạch" (ARCHITECTURE, mục Tầng 3).
    """
    result = df.copy()

    # --- Bước 1: Tạo cờ is_interpolated TRƯỚC KHI nội suy ---
    # Một dòng được đánh dấu `is_interpolated = 1` nếu giá trị GỐC là NaN
    # VÀ sau khi interpolate nó được lấp đầy (không còn NaN nữa).
    # Nếu NaN vẫn giữ nguyên sau interpolate (vượt limit=2), cờ = 0 vì
    # giá trị không bị can thiệp — nó vẫn là NaN gốc.

    # Ghi nhận vị trí NaN gốc trước khi nội suy
    oee_was_nan = result["OEE_Score"].isna()
    delay_was_nan = result["DelayRate"].isna()

    nan_oee_count = oee_was_nan.sum()
    nan_delay_count = delay_was_nan.sum()

    if nan_oee_count > 0:
        logger.info(
            f"[Nội suy] OEE_Score: {nan_oee_count:,} tuần có giá trị NaN "
            f"trước khi nội suy."
        )
    if nan_delay_count > 0:
        logger.info(
            f"[Nội suy] DelayRate: {nan_delay_count:,} tuần có giá trị NaN "
            f"trước khi nội suy."
        )

    # --- Bước 2: Nội suy OEE_Score (tỷ lệ) — limit=2 tuần liên tiếp ---
    result["OEE_Score"] = result["OEE_Score"].interpolate(
        method="linear", limit=2, limit_direction="both"
    )

    # --- Bước 3: Nội suy DelayRate (tỷ lệ) — limit=2 tuần liên tiếp ---
    result["DelayRate"] = result["DelayRate"].interpolate(
        method="linear", limit=2, limit_direction="both"
    )

    # --- Bước 4: Đánh dấu is_interpolated ---
    # Cờ = 1 nếu: (a) giá trị gốc là NaN, VÀ (b) sau interpolate không
    # còn NaN (tức đã được nội suy thành công).
    result["is_interpolated_oee"] = (
        oee_was_nan & result["OEE_Score"].notna()
    ).astype(int)

    result["is_interpolated_delay"] = (
        delay_was_nan & result["DelayRate"].notna()
    ).astype(int)

    # Ghi log số tuần đã nội suy vs. số tuần vẫn còn NaN (vượt limit)
    interpolated_oee = result["is_interpolated_oee"].sum()
    remaining_nan_oee = result["OEE_Score"].isna().sum()
    interpolated_delay = result["is_interpolated_delay"].sum()
    remaining_nan_delay = result["DelayRate"].isna().sum()

    logger.info(
        f"[Nội suy] OEE_Score: đã nội suy {interpolated_oee:,} tuần, "
        f"còn {remaining_nan_oee:,} tuần NaN (vượt limit=2)."
    )
    logger.info(
        f"[Nội suy] DelayRate: đã nội suy {interpolated_delay:,} tuần, "
        f"còn {remaining_nan_delay:,} tuần NaN (vượt limit=2)."
    )

    # WARNING nếu còn NaN sau nội suy — Anh Béo cần biết để quyết định
    # có chấp nhận dataset hay yêu cầu kiểm tra lại dữ liệu gốc.
    if remaining_nan_oee > 0:
        logger.warning(
            f"[Nội suy] OEE_Score vẫn còn {remaining_nan_oee:,} tuần NaN "
            f"sau khi nội suy (khoảng trống > 2 tuần liên tiếp). "
            f"Các tuần này sẽ giữ NaN trong dataset — Tầng 3 cần xử lý."
        )
    if remaining_nan_delay > 0:
        logger.warning(
            f"[Nội suy] DelayRate vẫn còn {remaining_nan_delay:,} tuần NaN "
            f"sau khi nội suy (khoảng trống > 2 tuần liên tiếp). "
            f"Các tuần này sẽ giữ NaN trong dataset — Tầng 3 cần xử lý."
        )

    # --- Bước 5: Revenue & OrderVolume — fillna(0) ---
    # Giá trị 0 có ý nghĩa thật: "không có giao dịch trong tuần đó"
    result["Revenue"] = result["Revenue"].fillna(0)
    result["OrderVolume"] = result["OrderVolume"].fillna(0).astype(int)

    return result


# =====================================================================
# HÀM CHÍNH — ĐIỀU PHỐI TOÀN BỘ TẦNG 2
# =====================================================================

def run_phase0(snapshot_dir: str = None) -> str:
    """
    Hàm chính của Tầng 2 (Phase 0): tái cấu trúc dữ liệu thô → dataset tuần.

    Quy trình:
        1. Tìm/xác nhận thư mục snapshot.
        2. Đọc 3 file CSV nguyên trạng (CHỈ ĐỌC — bất biến raw).
        3. Gộp OEE, Delay, Revenue theo tuần (chống look-ahead bias).
        4. Merge 3 nguồn vào 1 bảng chung.
        5. Nội suy NaN có giới hạn + gắn cờ is_interpolated.
        6. Ghi kết quả ra `data/processed/causal_weekly_dataset.csv`.

    Tham số:
        snapshot_dir: đường dẫn tuyệt đối đến thư mục snapshot cụ thể.
                      Nếu None, tự động dùng snapshot mới nhất.

    Trả về:
        Đường dẫn tuyệt đối đến file output.
    """
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("Phase 0 (Tái cấu trúc dữ liệu) bắt đầu.")
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
    # Tuân thủ bất biến: CHỈ ĐỌC, mọi transform trên bản copy.
    # -----------------------------------------------------------------
    oee_raw = _load_raw_csv(snapshot_dir, "cmt_oee_results.csv")
    delay_raw = _load_raw_csv(snapshot_dir, "cmt_delay_results.csv")
    revenue_raw = _load_raw_csv(snapshot_dir, "fob_revenue.csv")

    # -----------------------------------------------------------------
    # Bước 3: Gộp từng nguồn theo tuần
    # -----------------------------------------------------------------
    logger.info("-" * 40)
    logger.info("Bắt đầu gộp dữ liệu OEE theo tuần...")
    weekly_oee = _aggregate_oee_weekly(oee_raw)

    logger.info("-" * 40)
    logger.info("Bắt đầu gộp dữ liệu Delay theo tuần...")
    weekly_delay = _aggregate_delay_weekly(delay_raw)

    logger.info("-" * 40)
    logger.info("Bắt đầu gộp dữ liệu Revenue theo tuần...")
    weekly_revenue = _aggregate_revenue_weekly(revenue_raw)

    # -----------------------------------------------------------------
    # Bước 4: Merge 3 nguồn vào 1 bảng chung
    # -----------------------------------------------------------------
    logger.info("-" * 40)
    logger.info("Merge 3 dataset tuần...")
    merged = _merge_weekly_datasets(weekly_oee, weekly_delay, weekly_revenue)

    # -----------------------------------------------------------------
    # Bước 5: Nội suy NaN có giới hạn + cờ is_interpolated
    # -----------------------------------------------------------------
    logger.info("-" * 40)
    logger.info("Nội suy NaN và gắn cờ is_interpolated...")
    final_dataset = _interpolate_with_flags(merged)

    # -----------------------------------------------------------------
    # Bước 6: Ghi kết quả ra data/processed/
    # -----------------------------------------------------------------
    output_path = os.path.join(
        get_base_dir(), "data", "processed", "causal_weekly_dataset.csv"
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Chọn và sắp xếp cột output theo đúng thứ tự quy ước
    output_columns = [
        "week_start",
        "OEE_Score",
        "DelayRate",
        "Revenue",
        "OrderVolume",
        "is_interpolated_oee",
        "is_interpolated_delay",
    ]

    final_dataset = final_dataset[output_columns]
    final_dataset.to_csv(output_path, index=False, encoding="utf-8-sig")

    # -----------------------------------------------------------------
    # Tóm tắt dataset — thông tin này sẽ hiển thị tại ĐIỂM DỪNG XÁC NHẬN 1
    # (skill.md mục 3, điểm 1): main.py dừng và in tóm tắt để Anh Béo
    # duyệt trước khi chạy Tầng 3.
    # -----------------------------------------------------------------
    total_weeks = len(final_dataset)
    date_range_start = final_dataset["week_start"].min()
    date_range_end = final_dataset["week_start"].max()
    interpolated_oee_count = final_dataset["is_interpolated_oee"].sum()
    interpolated_delay_count = final_dataset["is_interpolated_delay"].sum()
    remaining_nan = final_dataset[["OEE_Score", "DelayRate"]].isna().any(axis=1).sum()

    logger.info("=" * 60)
    logger.info("TÓM TẮT DATASET TUẦN (cho điểm dừng xác nhận):")
    logger.info(f"  - Tổng số tuần       : {total_weeks:,}")
    logger.info(f"  - Khoảng thời gian   : {date_range_start} → {date_range_end}")
    logger.info(f"  - Tuần nội suy OEE   : {interpolated_oee_count:,}")
    logger.info(f"  - Tuần nội suy Delay : {interpolated_delay_count:,}")
    logger.info(f"  - Tuần còn NaN       : {remaining_nan:,}")
    logger.info(f"  - File output        : {output_path}")
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
