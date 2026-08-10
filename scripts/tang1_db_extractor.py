"""
Tầng 1 — DB Layer: Khai thác dữ liệu gốc từ SQL Server.

Mục đích:
    Kết nối trực tiếp vào database ERP (`qtdn_datamining`) trên SQL Server,
    trích xuất và TÍNH TOÁN 3 bảng phân tích (`cmt_oee_results`,
    `cmt_delay_results`, `fob_revenue`) từ 3 bảng ERP gốc (`WorkOrders`,
    `SalesOrders`, `Invoices`). Cả 3 truy vấn dùng chung một mốc thời gian
    `snapshot_time` để đảm bảo tính nhất quán dữ liệu.

Thiết kế (theo ARCHITECTURE_4_tang.md, Tầng 1):
    1. Mở 1 kết nối SQL Server duy nhất, chốt `snapshot_time` MỘT LẦN.
    2. Chạy 3 truy vấn SQL tính toán OEE_Score, IsDelayed, Revenue — mỗi
       truy vấn lọc theo `WHERE <cột thời gian> <= @snapshot_time`.
    3. Ghi NGUYÊN TRẠNG kết quả ra `data/raw/snapshot_YYYYMMDD_HHMM/*.csv`
       — KHÔNG transform thêm sau khi đã truy vấn (tuân thủ nguyên tắc bất
       biến, CLAUDE.md mục 2).
    4. Tự động cập nhật `data/raw/MANIFEST.md`: timestamp, checksum SHA-256,
       số dòng mỗi file, tỉ lệ khớp OrderNo giữa 3 file.

Input:  SQL Server (`qtdn_datamining`) — ĐÂY LÀ ĐIỂM TRUY CẬP SQL SERVER
        DUY NHẤT của toàn bộ Phương án 3 (CLAUDE.md mục 4).
Output: `data/raw/snapshot_YYYYMMDD_HHMM/{cmt_oee_results.csv,
        cmt_delay_results.csv, fob_revenue.csv}` + `data/raw/MANIFEST.md`.
Sở hữu: Role A — Data Engineering (skill.md).

Bảng ERP gốc sử dụng:
    - WorkOrders: dữ liệu lệnh sản xuất (OrderNo, PlanQty, ActualEndDate...)
    - ProductionLogs: dữ liệu vận hành máy (PlannedOperatingMinutes,
      ActualWorkingMinutes, TotalQty, GoodQty, StandardCycleTime) — JOIN
      với WorkOrders qua OrderNo để tính OEE = A × P × Q
    - SalesOrders: dữ liệu đơn hàng bán (PlannedShipmentDate, ActualShipDate...)
    - Invoices: dữ liệu hóa đơn/doanh thu (FOBValue, ShipmentDate...)

Thay đổi so với bản trước:
    - Bản cũ: SELECT * FROM cmt_oee_results (giả định bảng đã tồn tại sẵn)
    - Bản mới: Truy vấn trực tiếp từ bảng ERP gốc, TÍNH TOÁN OEE/Delay/Revenue
      bằng SQL — không phụ thuộc pipeline Phương án A chạy trước.
"""

import os
import sys
import hashlib
from datetime import datetime
from typing import Optional

import pandas as pd
import pyodbc

# Import logger dùng chung — tuân thủ CLAUDE.md mục 7: không dùng print()
# cho bất kỳ thông điệp nào liên quan đến tiến trình xử lý dữ liệu.
from scripts.utils import get_logger, get_base_dir

logger = get_logger("tang1")

# =====================================================================
# CẤU HÌNH KẾT NỐI SQL SERVER
# =====================================================================
# Anh Béo điền thông tin kết nối thực tế tại đây trước khi chạy trên
# máy local. Nếu muốn dùng biến môi trường, đặt:
#   set DB_SERVER=192.168.1.100\SQLEXPRESS   (Windows)
#   export DB_SERVER=192.168.1.100\\SQLEXPRESS (Linux/macOS)
# Script ưu tiên đọc từ biến môi trường; nếu không có, dùng giá trị
# mặc định (placeholder) bên dưới.
# =====================================================================
DB_CONFIG = {
    "server": os.environ.get("DB_SERVER", "localhost"),
    "database": os.environ.get("DB_DATABASE", "qtdn_datamining"),
    "driver": os.environ.get("DB_DRIVER", "{ODBC Driver 17 for SQL Server}"),
    "username": os.environ.get("DB_USERNAME", ""),
    "password": os.environ.get("DB_PASSWORD", ""),
    # True = Windows Authentication (không cần username/password)
    # False = SQL Server Authentication (phải điền username/password)
    "trusted_connection": os.environ.get("DB_TRUSTED", "true").lower() == "true",
}

# Số lần thử kết nối lại khi SQL Server không phản hồi — sau MAX_RETRY
# lần đều thất bại, ghi CRITICAL và dừng pipeline (fail-fast).
MAX_RETRY = 3


def _build_connection_string() -> str:
    """
    Xây dựng connection string cho pyodbc từ DB_CONFIG.

    Tách riêng hàm này để dễ bảo trì khi cấu hình kết nối thay đổi
    (vd: chuyển từ Windows Auth sang SQL Auth), không phải sửa logic
    chính trong hàm extract.
    """
    parts = [
        f"DRIVER={DB_CONFIG['driver']}",
        f"SERVER={DB_CONFIG['server']}",
        f"DATABASE={DB_CONFIG['database']}",
    ]

    if DB_CONFIG.get("trusted_connection"):
        parts.append("Trusted_Connection=yes")
    else:
        parts.append(f"UID={DB_CONFIG['username']}")
        parts.append(f"PWD={DB_CONFIG['password']}")

    return ";".join(parts)


def _connect_sql_server() -> pyodbc.Connection:
    """
    Mở kết nối SQL Server với cơ chế retry.

    Thử tối đa MAX_RETRY lần — nếu tất cả đều thất bại, ghi CRITICAL
    vào log (CLAUDE.md mục 7.3) và raise exception để main.py dừng
    pipeline (fail-fast).
    """
    conn_str = _build_connection_string()
    last_error: Optional[Exception] = None

    for attempt in range(1, MAX_RETRY + 1):
        try:
            logger.info(f"Đang kết nối SQL Server (lần thử {attempt}/{MAX_RETRY})...")
            logger.info(
                f"  Server: {DB_CONFIG['server']} | Database: {DB_CONFIG['database']} | "
                f"Auth: {'Windows' if DB_CONFIG['trusted_connection'] else 'SQL Server'}"
            )
            conn = pyodbc.connect(conn_str, timeout=30)
            logger.info("Kết nối SQL Server thành công.")
            return conn
        except pyodbc.Error as e:
            last_error = e
            logger.warning(
                f"Kết nối SQL Server thất bại lần {attempt}/{MAX_RETRY}: {e}"
            )

    # Sau MAX_RETRY lần đều thất bại — CRITICAL vì đây là lỗi hạ tầng
    # nghiêm trọng, không thể tiếp tục pipeline.
    logger.critical(
        f"Kết nối SQL Server thất bại sau {MAX_RETRY} lần thử. "
        f"Kiểm tra lại cấu hình DB_CONFIG trong tang1_db_extractor.py "
        f"hoặc biến môi trường DB_SERVER, DB_DATABASE, DB_DRIVER."
    )
    raise ConnectionError(
        f"Không thể kết nối SQL Server sau {MAX_RETRY} lần thử."
    ) from last_error


def _compute_sha256(file_path: str) -> str:
    """
    Tính checksum SHA-256 cho file — dùng để ghi vào MANIFEST.md.

    Đọc file theo chunk 8KB để xử lý được cả file lớn mà không
    tiêu tốn RAM. Trả về chuỗi hex 64 ký tự.
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _compute_orderno_overlap(dataframes: dict[str, pd.DataFrame]) -> dict:
    """
    Tính tỉ lệ khớp OrderNo giữa 3 file bằng Jaccard Index.

    Mục đích: phát hiện sớm lệch dữ liệu do snapshot không đồng thời
    (ARCHITECTURE_4_tang.md, Tầng 1, mục 4). Nếu tỉ lệ khớp < 95%,
    Tầng 1 ghi WARNING (CLAUDE.md mục 7.3).

    Công thức Jaccard: J(A,B,C) = |A ∩ B ∩ C| / |A ∪ B ∪ C|
    (xem MATH_AND_ALGORITHMS.md, Tầng 1, mục 1.1)
    """
    sets = {}
    for name, df in dataframes.items():
        if "OrderNo" in df.columns:
            sets[name] = set(df["OrderNo"].dropna().unique())
        else:
            # Nếu file không có cột OrderNo (vd: fob_revenue chỉ có dữ liệu
            # tổng hợp theo tháng), bỏ qua file đó khi tính overlap.
            logger.warning(
                f"File {name} không có cột 'OrderNo' — bỏ qua khi tính "
                f"tỉ lệ khớp OrderNo."
            )

    if len(sets) < 2:
        return {"overlap_ratio": None, "detail": "Không đủ file có cột OrderNo để so sánh."}

    # Tính Jaccard index: |giao| / |hợp| của tất cả các tập có OrderNo
    all_sets = list(sets.values())
    intersection = all_sets[0]
    union = all_sets[0]
    for s in all_sets[1:]:
        intersection = intersection & s
        union = union | s

    ratio = len(intersection) / len(union) if len(union) > 0 else 0.0

    return {
        "overlap_ratio": round(ratio, 4),
        "intersection_count": len(intersection),
        "union_count": len(union),
        "per_file_count": {name: len(s) for name, s in sets.items()},
    }


def _write_manifest(
    snapshot_dir: str,
    snapshot_time: datetime,
    file_info: list[dict],
    overlap_info: dict,
) -> None:
    """
    Ghi/cập nhật file MANIFEST.md trong data/raw/.

    Mỗi lần chạy Tầng 1 thêm một mục mới vào MANIFEST.md (append),
    không ghi đè nội dung cũ — giữ lịch sử tất cả snapshot đã trích xuất
    (audit trail, CLAUDE.md mục 7.2).
    """
    base_dir = get_base_dir()
    manifest_path = os.path.join(base_dir, "data", "raw", "MANIFEST.md")

    # Xây dựng nội dung mục mới cho snapshot hiện tại
    lines = [
        f"\n## Snapshot: {os.path.basename(snapshot_dir)}",
        f"",
        f"- **Thời điểm trích xuất (snapshot_time):** {snapshot_time.isoformat()}",
        f"- **Thời điểm ghi file:** {datetime.now().isoformat()}",
        f"- **Nguồn:** Truy vấn trực tiếp từ bảng ERP gốc (WorkOrders, ProductionLogs, SalesOrders, Invoices)",
        f"",
        f"### Danh sách file",
        f"",
        f"| File | Số dòng | SHA-256 |",
        f"|------|---------|---------|",
    ]

    for info in file_info:
        lines.append(f"| `{info['filename']}` | {info['row_count']:,} | `{info['sha256']}` |")

    lines.append("")
    lines.append("### Tỉ lệ khớp OrderNo giữa các file")
    lines.append("")

    if overlap_info.get("overlap_ratio") is not None:
        ratio_pct = overlap_info["overlap_ratio"] * 100
        lines.append(f"- **Jaccard index:** {ratio_pct:.2f}%")
        lines.append(f"- Giao (intersection): {overlap_info['intersection_count']:,} OrderNo")
        lines.append(f"- Hợp (union): {overlap_info['union_count']:,} OrderNo")
        for fname, cnt in overlap_info.get("per_file_count", {}).items():
            lines.append(f"- `{fname}`: {cnt:,} OrderNo riêng biệt")
    else:
        lines.append(f"- {overlap_info.get('detail', 'Không có thông tin.')}")

    lines.append("")
    lines.append("---")
    lines.append("")

    content = "\n".join(lines)

    # Nếu MANIFEST.md chưa tồn tại, tạo header ban đầu
    if not os.path.exists(manifest_path):
        header = (
            "# MANIFEST.md — Lịch sử snapshot dữ liệu thô\n\n"
            "> File này được tự động cập nhật bởi `tang1_db_extractor.py`.\n"
            "> Mỗi mục tương ứng với một lần trích xuất dữ liệu từ SQL Server.\n"
            "> KHÔNG chỉnh sửa thủ công.\n\n"
            "---\n"
        )
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write(header)

    with open(manifest_path, "a", encoding="utf-8") as f:
        f.write(content)

    logger.info(f"Đã cập nhật MANIFEST.md: {manifest_path}")


# =====================================================================
# CÁC TRUY VẤN SQL — TÍNH TOÁN TỪ BẢNG ERP GỐC
# =====================================================================
# Mỗi truy vấn:
#   1. Đọc dữ liệu từ bảng ERP gốc (WorkOrders, SalesOrders, Invoices)
#   2. TÍNH TOÁN chỉ số phân tích (OEE_Score, IsDelayed, Revenue)
#   3. Lọc theo `<cột thời gian> <= ?` (snapshot_time) để đảm bảo
#      cả 3 file phản ánh cùng một lát cắt thời gian.
#
# Anh Béo cần xác nhận/điều chỉnh tên cột nếu schema thực tế khác
# tên placeholder bên dưới (vd: PlanQty → PlannedQuantity).
# =====================================================================

# --- Truy vấn 1: OEE (Overall Equipment Effectiveness) ---
# Tính từ bảng WorkOrders JOIN ProductionLogs — phân rã OEE theo tiêu chuẩn
# quốc tế (Nakajima, 1988): OEE = Availability × Performance × Quality.
#
# Công thức phân rã (xem MATH_AND_ALGORITHMS.md mục 1.3):
#   A (Availability)  = ActualWorkingMinutes / PlannedOperatingMinutes
#   P (Performance)   = (TotalQty × StandardCycleTime) / ActualWorkingMinutes
#   Q (Quality)       = GoodQty / TotalQty
#   OEE_Score         = A × P × Q
#
# Nguồn dữ liệu:
#   - WorkOrders: thông tin lệnh sản xuất (OrderNo, PlanQty, ActualEndDate...)
#   - ProductionLogs: dữ liệu vận hành máy thực tế (thời gian chạy, sản lượng,
#     chu kỳ chuẩn, sản phẩm đạt chất lượng)
#
# NULLIF(..., 0) tại mỗi phép chia — tránh division by zero; nếu mẫu số = 0
# thì thành phần đó trả về NULL → OEE_Score tổng cũng NULL (ghi WARNING ở
# hàm extract_snapshot).
#
# Chỉ lấy lệnh sản xuất đã hoàn thành (ActualEndDate IS NOT NULL) và nằm
# trong khung thời gian snapshot (zero look-ahead bias).
SQL_OEE = """
    SELECT
        wo.OrderNo,
        wo.ProductCode,
        wo.PlanQty,
        wo.ActualStartDate,
        wo.ActualEndDate,
        wo.MachineLine,

        -- Dữ liệu vận hành từ ProductionLogs
        pl.PlannedOperatingMinutes,
        pl.ActualWorkingMinutes,
        pl.TotalQty,
        pl.GoodQty,
        pl.StandardCycleTime,

        -- Availability: tỉ lệ thời gian máy chạy thực tế / kế hoạch
        ROUND(
            CAST(pl.ActualWorkingMinutes AS FLOAT)
            / NULLIF(pl.PlannedOperatingMinutes, 0),
            4
        ) AS Availability,

        -- Performance: tỉ lệ năng suất thực tế so với năng suất lý thuyết
        ROUND(
            (CAST(pl.TotalQty AS FLOAT) * pl.StandardCycleTime)
            / NULLIF(pl.ActualWorkingMinutes, 0),
            4
        ) AS Performance,

        -- Quality: tỉ lệ sản phẩm đạt chất lượng
        ROUND(
            CAST(pl.GoodQty AS FLOAT)
            / NULLIF(pl.TotalQty, 0),
            4
        ) AS Quality,

        -- OEE_Score = A × P × Q (tính đầy đủ 3 thành phần)
        CASE
            WHEN ISNULL(pl.PlannedOperatingMinutes, 0) = 0
              OR ISNULL(pl.ActualWorkingMinutes, 0) = 0
              OR ISNULL(pl.TotalQty, 0) = 0
            THEN NULL
            ELSE ROUND(
                (CAST(pl.ActualWorkingMinutes AS FLOAT)
                    / NULLIF(pl.PlannedOperatingMinutes, 0))
              * ((CAST(pl.TotalQty AS FLOAT) * pl.StandardCycleTime)
                    / NULLIF(pl.ActualWorkingMinutes, 0))
              * (CAST(pl.GoodQty AS FLOAT)
                    / NULLIF(pl.TotalQty, 0)),
                4
            )
        END AS OEE_Score

    FROM WorkOrders wo
    INNER JOIN ProductionLogs pl
        ON wo.OrderNo = pl.OrderNo
    WHERE wo.ActualEndDate IS NOT NULL
      AND wo.ActualEndDate <= ?
    ORDER BY wo.ActualEndDate, wo.OrderNo
"""

# --- Truy vấn 2: Delay (Trễ đơn hàng) ---
# Tính từ bảng SalesOrders — mỗi dòng là 1 đơn hàng bán.
# IsDelayed = 1 nếu ngày giao thực tế (ActualShipDate) muộn hơn
#             ngày kế hoạch (PlannedShipmentDate).
# DelayDays = số ngày trễ (0 nếu giao đúng hoặc sớm hơn kế hoạch).
# Dùng ActualShipDate (ngày giao thực tế) làm mốc thời gian snapshot
# — KHÔNG dùng PlannedShipmentDate vì ngày kế hoạch có thể bị điều
# chỉnh ngược (zero look-ahead bias, xem INNOVATIONS.md mục 4.3).
SQL_DELAY = """
    SELECT
        so.OrderNo,
        so.CustomerCode,
        so.PlannedShipmentDate,
        so.ActualShipDate,
        CASE
            WHEN so.ActualShipDate > so.PlannedShipmentDate THEN 1
            ELSE 0
        END AS IsDelayed,
        CASE
            WHEN so.ActualShipDate > so.PlannedShipmentDate
                THEN DATEDIFF(DAY, so.PlannedShipmentDate, so.ActualShipDate)
            ELSE 0
        END AS DelayDays
    FROM SalesOrders so
    WHERE so.ActualShipDate IS NOT NULL
      AND so.ActualShipDate <= ?
    ORDER BY so.ActualShipDate, so.OrderNo
"""

# --- Truy vấn 3: FOB Revenue (Doanh thu xuất khẩu) ---
# Tính từ bảng Invoices — mỗi dòng là 1 hóa đơn xuất khẩu.
# Revenue = Quantity * UnitPrice (tổng giá trị FOB cho từng dòng).
# TotalFOBValue là tổng giá trị đã có sẵn trong hóa đơn (nếu có),
# nếu không thì tính từ Quantity * UnitPrice.
# Dùng ShipmentDate làm mốc thời gian snapshot.
SQL_REVENUE = """
    SELECT
        inv.OrderNo,
        inv.InvoiceNo,
        inv.CustomerCode,
        inv.ShipmentDate,
        inv.Quantity,
        inv.UnitPrice,
        ISNULL(
            inv.TotalFOBValue,
            ROUND(CAST(inv.Quantity AS FLOAT) * CAST(inv.UnitPrice AS FLOAT), 2)
        ) AS Revenue
    FROM Invoices inv
    WHERE inv.ShipmentDate IS NOT NULL
      AND inv.ShipmentDate <= ?
    ORDER BY inv.ShipmentDate, inv.OrderNo
"""

# Ánh xạ tên bảng đầu ra → truy vấn SQL tương ứng
QUERIES = {
    "cmt_oee_results": SQL_OEE,
    "cmt_delay_results": SQL_DELAY,
    "fob_revenue": SQL_REVENUE,
}


def extract_snapshot() -> str:
    """
    Hàm chính của Tầng 1: trích xuất snapshot đồng thời từ SQL Server.

    Quy trình:
        1. Chốt snapshot_time — MỘT LẦN duy nhất cho cả 3 truy vấn.
        2. Kết nối SQL Server (có retry, tối đa MAX_RETRY lần).
        3. Chạy tuần tự 3 truy vấn SQL tính toán OEE/Delay/Revenue từ bảng
           ERP gốc, mỗi truy vấn lọc <= snapshot_time.
        4. Ghi kết quả ra CSV (KHÔNG transform thêm — CLAUDE.md mục 2).
        5. Tính checksum SHA-256, tỉ lệ khớp OrderNo, cập nhật MANIFEST.md.
        6. Ghi log INFO/WARNING theo đúng quy ước (CLAUDE.md mục 7.3).

    Trả về:
        Đường dẫn tuyệt đối đến thư mục snapshot vừa tạo.

    Raises:
        ConnectionError: nếu không kết nối được SQL Server sau MAX_RETRY lần.
        Exception: mọi lỗi khác — kèm traceback đầy đủ qua logger.exception().
    """
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("Tầng 1 (DB Extractor) bắt đầu.")
    logger.info("=" * 60)

    # -----------------------------------------------------------------
    # Bước 1: Chốt snapshot_time — đây là mốc thời gian duy nhất mà cả
    # 3 truy vấn sẽ dùng để lọc dữ liệu. Chốt TRƯỚC khi mở kết nối,
    # vì thời gian kết nối có thể dao động — ta muốn mốc chính xác nhất
    # có thể tại thời điểm QUYẾT ĐỊNH trích xuất.
    # -----------------------------------------------------------------
    snapshot_time = datetime.now()
    snapshot_label = snapshot_time.strftime("%Y%m%d_%H%M")
    logger.info(f"Snapshot time đã chốt: {snapshot_time.isoformat()}")

    # Tạo thư mục snapshot trong data/raw/ — nơi lưu file CSV nguyên trạng
    base_dir = get_base_dir()
    snapshot_dir = os.path.join(base_dir, "data", "raw", f"snapshot_{snapshot_label}")
    os.makedirs(snapshot_dir, exist_ok=True)
    logger.info(f"Thư mục snapshot: {snapshot_dir}")

    # -----------------------------------------------------------------
    # Bước 2: Kết nối SQL Server — có cơ chế retry (MAX_RETRY lần).
    # Nếu kết nối thất bại, hàm _connect_sql_server() tự raise
    # ConnectionError kèm log CRITICAL — pipeline dừng ngay (fail-fast).
    # -----------------------------------------------------------------
    conn = _connect_sql_server()

    try:
        dataframes: dict[str, pd.DataFrame] = {}
        file_info_list: list[dict] = []

        # -----------------------------------------------------------------
        # Bước 3: Chạy tuần tự 3 truy vấn — mỗi truy vấn tính toán chỉ số
        # phân tích từ bảng ERP gốc, dùng chung snapshot_time làm tham số
        # lọc. Chạy tuần tự (không parallel) vì dùng chung 1 kết nối —
        # đủ nhanh cho dataset quy mô này, và đơn giản hơn khi debug.
        # -----------------------------------------------------------------
        for table_name, query in QUERIES.items():
            logger.info(f"Đang truy vấn và tính toán '{table_name}'...")

            try:
                df = pd.read_sql(query, conn, params=[snapshot_time])
            except Exception:
                # Bắt riêng lỗi từng truy vấn — ghi rõ TÊN BẢNG bị lỗi
                # để dễ debug (vd: bảng gốc chưa tồn tại, sai tên cột...)
                logger.exception(
                    f"Truy vấn '{table_name}' thất bại — kiểm tra lại tên "
                    f"bảng/cột trong SQL Server. Xem traceback bên dưới."
                )
                raise

            row_count = len(df)
            col_count = len(df.columns)

            # Ghi INFO số dòng — bắt buộc theo CLAUDE.md mục 7.3
            logger.info(
                f"Đã tải '{table_name}': {row_count:,} dòng, "
                f"{col_count} cột ({', '.join(df.columns.tolist())})."
            )

            # Ghi WARNING nếu bảng rỗng — bất thường nhưng chưa crash
            if row_count == 0:
                logger.warning(
                    f"Truy vấn '{table_name}' trả về 0 dòng — kiểm tra lại "
                    f"snapshot_time ({snapshot_time.isoformat()}) hoặc dữ "
                    f"liệu trong bảng ERP gốc tương ứng."
                )

            # Kiểm tra giá trị NULL ở các cột tính toán — ghi WARNING nếu
            # có, vì NULL có thể do PlanQty = 0 (chia cho 0) hoặc dữ liệu
            # thiếu ở bảng gốc.
            computed_cols = {
                "cmt_oee_results": "OEE_Score",
                "cmt_delay_results": "IsDelayed",
                "fob_revenue": "Revenue",
            }
            check_col = computed_cols.get(table_name)
            if check_col and check_col in df.columns:
                null_count = df[check_col].isna().sum()
                if null_count > 0:
                    logger.warning(
                        f"Cột '{check_col}' trong '{table_name}': "
                        f"{null_count:,} giá trị NULL (có thể do chia cho 0 "
                        f"hoặc dữ liệu thiếu ở bảng ERP gốc)."
                    )

            # ---------------------------------------------------------------
            # Bước 4: Ghi nguyên trạng kết quả truy vấn ra CSV.
            # Sau khi SQL đã tính toán xong OEE/Delay/Revenue, kết quả
            # được ghi ra file KHÔNG qua bất kỳ transform nào thêm.
            # Tuân thủ nguyên tắc bất biến dữ liệu (CLAUDE.md mục 2).
            # ---------------------------------------------------------------
            csv_filename = f"{table_name}.csv"
            csv_path = os.path.join(snapshot_dir, csv_filename)
            df.to_csv(csv_path, index=False, encoding="utf-8-sig")

            logger.info(f"Đã ghi '{csv_filename}' ({row_count:,} dòng) vào {snapshot_dir}")

            # Tính checksum SHA-256 cho file vừa ghi — dùng cho MANIFEST.md
            # và để kiểm tra tính toàn vẹn dữ liệu sau này.
            sha256 = _compute_sha256(csv_path)
            logger.info(f"SHA-256 ({csv_filename}): {sha256[:16]}...")

            dataframes[table_name] = df
            file_info_list.append({
                "filename": csv_filename,
                "row_count": row_count,
                "sha256": sha256,
            })

        # -----------------------------------------------------------------
        # Bước 5: Tính tỉ lệ khớp OrderNo (Jaccard Index) và cập nhật
        # MANIFEST.md. Jaccard < 95% → WARNING (dấu hiệu dữ liệu lệch).
        # -----------------------------------------------------------------
        overlap_info = _compute_orderno_overlap(dataframes)

        if overlap_info.get("overlap_ratio") is not None:
            ratio_pct = overlap_info["overlap_ratio"] * 100
            logger.info(f"Tỉ lệ khớp OrderNo (Jaccard): {ratio_pct:.2f}%")

            if overlap_info["overlap_ratio"] < 0.95:
                logger.warning(
                    f"Tỉ lệ khớp OrderNo giữa các file = {ratio_pct:.2f}% "
                    f"(< 95%) — kiểm tra lại xem snapshot có đồng thời không, "
                    f"hoặc có bảng ERP gốc nào thiếu dữ liệu OrderNo. "
                    f"Chi tiết: giao={overlap_info['intersection_count']:,}, "
                    f"hợp={overlap_info['union_count']:,}."
                )

        _write_manifest(snapshot_dir, snapshot_time, file_info_list, overlap_info)

    except Exception:
        # Ghi ERROR kèm traceback đầy đủ — bắt buộc dùng logger.exception()
        # thay vì logger.error(str(e)) (CLAUDE.md mục 7.3).
        logger.exception("Tầng 1 gặp lỗi trong quá trình trích xuất dữ liệu.")
        raise
    finally:
        # Luôn đóng kết nối khi xong — dù thành công hay thất bại.
        conn.close()
        logger.info("Đã đóng kết nối SQL Server.")

    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info(f"Tầng 1 hoàn tất trong {elapsed:.1f}s. Snapshot: {snapshot_dir}")
    logger.info(
        f"Tóm tắt: {len(file_info_list)} file CSV đã ghi | "
        f"Tổng {sum(f['row_count'] for f in file_info_list):,} dòng | "
        f"Jaccard: {overlap_info.get('overlap_ratio', 'N/A')}"
    )

    return snapshot_dir


# =====================================================================
# ENTRY POINT — cho phép chạy script độc lập (CLAUDE.md mục 3.5:
# mọi script chạy độc lập được, đọc input cố định, không phụ thuộc
# biến môi trường ẩn).
# =====================================================================
if __name__ == "__main__":
    try:
        result_dir = extract_snapshot()
        logger.info(f"Kết quả snapshot lưu tại: {result_dir}")
    except ConnectionError:
        logger.critical(
            "Không kết nối được SQL Server — kiểm tra lại:\n"
            "  1. SQL Server đã bật và đang chạy?\n"
            "  2. Tên server/IP trong DB_CONFIG (hoặc biến môi trường DB_SERVER) đúng chưa?\n"
            "  3. ODBC Driver 17 đã cài chưa? (Xem SETUP_GUIDE.md mục 1)\n"
            "  4. Firewall có chặn cổng 1433 không?"
        )
        sys.exit(1)
    except Exception:
        logger.exception("Tầng 1 thất bại — xem traceback ở trên.")
        sys.exit(1)
