"""
Tầng 1 — DB Layer: Khai thác dữ liệu gốc từ SQL Server.

Mục đích:
    Kết nối trực tiếp vào database ERP (QTDN) trên SQL Server, trích xuất
    3 bảng phân tích (`production_volume`, `cmt_delay_results`, `order_demand`)
    từ các bảng Microsoft Dynamics NAV. Cả 3 truy vấn dùng chung mốc thời
    gian `snapshot_time` để đảm bảo tính nhất quán dữ liệu.

Thiết kế (theo ARCHITECTURE_4_tang.md, Tầng 1):
    1. Mở 1 kết nối SQL Server duy nhất, chốt `snapshot_time` MỘT LẦN.
    2. Chạy 3 truy vấn SQL — mỗi truy vấn lọc theo `WHERE ... <= @snapshot_time`.
    3. Ghi NGUYÊN TRẠNG kết quả ra `data/raw/snapshot_YYYYMMDD_HHMM/*.csv`
       — KHÔNG transform thêm (tuân thủ CLAUDE.md mục 2).
    4. Tự động cập nhật `data/raw/MANIFEST.md`: timestamp, checksum SHA-256,
       số dòng mỗi file, tỉ lệ khớp OrderNo giữa các file.

Input:  SQL Server (QTDN) — ĐÂY LÀ ĐIỂM TRUY CẬP SQL SERVER DUY NHẤT
        của toàn bộ Phương án 3 (CLAUDE.md mục 4).
Output: `data/raw/snapshot_YYYYMMDD_HHMM/{production_volume.csv,
        cmt_delay_results.csv, order_demand.csv}` + `data/raw/MANIFEST.md`.
Sở hữu: Role A — Data Engineering (skill.md).

Bảng NAV (Dynamics NAV / Business Central) sử dụng:
    - [Value Entry] (Table 5802): bảng chủ lực — 363K+ dòng (2019–2026).
      Source Type 3 (Work Center) và 4 (Machine Center) chứa sản lượng sản
      xuất thực tế. Cột [Sales Order No_] liên kết về Sales Order (mã BDH).
    - [Sales Order Header] (Table 36): đơn hàng bán — 8,580 dòng (2017–2027).
      Cột [Shipment Date]/[Requested Delivery Date] cho phân tích delay.
    - [Sales Order Line] (Table 37): chi tiết đơn hàng — cột [Quantity] chứa
      khối lượng đặt hàng, dùng để tính biến OrderDemand.

Lịch sử thay đổi:
    - v1–v3: Truy vấn từ các bảng không đủ dữ liệu (xem git history).
    - v4: Revenue từ [Cust_ Ledger Entry], OEE từ [Production Order Header].
    - v5 (bản này, Phương án A): Chẩn đoán CSDL (2026-08-12) phát hiện:
        * [Production Order Header]: chỉ 2 bản ghi (2010)
        * [Cust_ Ledger Entry]: 3 bản ghi Revenue ≠ 0 (2010)
        * [Sales Invoice Header]: rỗng hoàn toàn
      → Chuyển sang Phương án A (100% dữ liệu thật):
        * ProductionVolume từ [Value Entry] (Source Type 3+4)
        * DelayRate từ [Sales Order Header] (giữ nguyên)
        * OrderDemand từ [Sales Order Line] × [Sales Order Header]
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
    "server": os.environ.get("DB_SERVER", r"(local)\SQLEXPRESS"),
    "database": os.environ.get("DB_DATABASE", "QTDN"),
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
    Tính tỉ lệ khớp OrderNo giữa các file cùng loại document number.

    Phương án A: production_volume dùng Production Order No (từ Value Entry),
    trong khi cmt_delay_results và order_demand dùng Sales Order No — hai
    numbering series khác nhau nên KHÔNG THỂ so sánh chéo. Jaccard chỉ tính
    giữa các file cùng dùng Sales Order No (cmt_delay_results + order_demand).

    Mục đích: phát hiện sớm lệch dữ liệu do snapshot không đồng thời.
    Nếu tỉ lệ khớp < 50%, Tầng 1 ghi WARNING (CLAUDE.md mục 7.3).
    Ngưỡng 50% (thay vì 95%) vì order_demand chứa cả đơn hàng chưa giao
    (chưa có shipment) nên giao tập hợp tự nhiên < 100%.
    """
    # Chỉ so sánh giữa các file dùng Sales Order No
    sales_order_tables = ["cmt_delay_results", "order_demand"]
    sets = {}
    for name in sales_order_tables:
        if name in dataframes and "OrderNo" in dataframes[name].columns:
            sets[name] = set(dataframes[name]["OrderNo"].dropna().unique())

    # Ghi log riêng cho production_volume (khác numbering series)
    if "production_volume" in dataframes:
        pv_df = dataframes["production_volume"]
        if "OrderNo" in pv_df.columns:
            pv_count = pv_df["OrderNo"].dropna().nunique()
            logger.info(
                f"production_volume có {pv_count:,} Production Order No riêng biệt "
                f"(numbering series khác Sales Order — không so sánh Jaccard)."
            )

    if len(sets) < 2:
        return {"overlap_ratio": None, "detail": "Không đủ file Sales Order để so sánh Jaccard."}

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
        f"- **Nguồn:** Truy vấn trực tiếp từ bảng NAV (Value Entry, Sales Order Header/Line)",
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
# CÁC TRUY VẤN SQL — PHƯƠNG ÁN A (100% DỮ LIỆU THẬT)
# =====================================================================
# Xác nhận nguồn dữ liệu qua chẩn đoán CSDL ngày 2026-08-12:
#   1. [Value Entry]: 363,509 dòng (2019–2026), Source Type 3+4 = sản xuất
#   2. [Sales Order Header]: 8,580 dòng (2017–2027), 4,092 có cả 2 ngày
#   3. [Sales Order Line]: có Quantity > 0, liên kết với Header qua Document No_
#
# Bảng NAV có dấu cách trong tên → bọc bằng [dấu ngoặc vuông].
# Cột NAV có hậu tố _ (vd: No_, Prod_ Order No_) → giữ nguyên.
#
# Nếu Anh Béo thấy lỗi "Invalid column name" khi chạy, kiểm tra tên
# cột bằng: SELECT TOP 1 * FROM [tên bảng]; rồi sửa lại ở đây.
# =====================================================================

# --- Truy vấn 1: Production Volume (Sản lượng sản xuất) ---
# Nguồn: [Value Entry] (NAV Table 5802)
#
# Lý do chuyển từ [Production Order Header]:
#   Chẩn đoán CSDL (2026-08-12) cho thấy [Production Order Header] chỉ có
#   2 bản ghi (2010), [Production Order Header Posted] rỗng hoàn toàn.
#   Trong khi [Value Entry] có 363,509 dòng từ 2019-02-11 đến 2026-07-03,
#   với Source Type 3 (Work Center, 162K) và 4 (Machine Center, 200K) chứa
#   toàn bộ dữ liệu sản xuất thực tế.
#
# Cột chính:
#   - [Posting Date]: ngày hạch toán — mốc thời gian gán vào tuần
#   - [Source Type]: 3 = Work Center, 4 = Machine Center (hoạt động SX)
#   - [Valued Quantity]: sản lượng thực tế (đơn vị sản phẩm)
#   - [Invoiced Quantity]: sản lượng đã xuất hóa đơn
#   - [Item No_]: mã sản phẩm
#   - [Document No_]: mã chứng từ sản xuất
#   - [Sales Order No_]: liên kết về Sales Order (mã BDH) — cho phép
#     merge sản xuất ↔ đơn hàng bán nếu cần
#
# Filter: Source Type IN (3, 4) — chỉ lấy hoạt động sản xuất tại Work
# Center và Machine Center. Loại trừ Source Type 0 (139 dòng, không rõ
# nguồn gốc).
SQL_PRODUCTION = """
    SELECT
        ve.[Document No_]               AS OrderNo,
        ve.[Item No_]                   AS ProductCode,
        ve.[Posting Date]               AS PostingDate,
        ve.[Source Type]                AS SourceType,
        ve.[Valued Quantity]            AS ValuedQty,
        ve.[Invoiced Quantity]          AS InvoicedQty,
        ve.[Cost per Unit]              AS CostPerUnit,
        ve.[Cost per Unit (LCY)]        AS CostPerUnitLCY,
        ve.[Cost Actual]                AS CostActual,
        ve.[Cost Actual (LCY)]          AS CostActualLCY,
        ve.[Sales Order No_]            AS SalesOrderNo,
        ve.[Document Type]              AS DocumentType

    FROM [Value Entry] ve
    WHERE ve.[Source Type] IN (3, 4)
      AND ve.[Posting Date] IS NOT NULL
      AND ve.[Posting Date] <= ?
    ORDER BY ve.[Posting Date], ve.[Document No_]
"""

# --- Truy vấn 2: Delay (Trễ đơn hàng) ---
# Nguồn: [Sales Order Header]
#   - No_: mã đơn hàng (vd: BDH00003)
#   - [Sell-to Customer No_]: mã khách hàng
#   - [Shipment Date]: ngày giao dự kiến (NAV cập nhật khi thay đổi)
#   - [Requested Delivery Date]: ngày khách yêu cầu giao
#
# Ghi chú đối chiếu QTDN.sql:
#   KPI giao hàng (KPI_1_11) dùng View_SO_Value_Entry (một VIEW) và
#   các hàm CompareQty dùng [Sales Order Line] — không truy vấn trực tiếp
#   [Sales Order Header]. Tuy nhiên, [Sales Order Header] là bảng NAV chuẩn
#   (Table ID 36), tồn tại trong CSDL (xác nhận qua Object Explorer), và
#   chứa cột [Shipment Date]/[Requested Delivery Date] cần thiết cho
#   phân tích delay mà View không cung cấp trực tiếp.
#
# IsDelayed = 1 nếu Shipment Date > Requested Delivery Date
# DelayDays = số ngày trễ (0 nếu đúng hạn hoặc sớm)
#
# Dùng [Shipment Date] làm mốc thời gian snapshot — đây là ngày NAV
# ghi nhận cho lô hàng, phản ánh kế hoạch giao hàng thực tế.
SQL_DELAY = """
    SELECT
        soh.[No_]                        AS OrderNo,
        soh.[Sell-to Customer No_]       AS CustomerCode,
        soh.[Requested Delivery Date]    AS PlannedShipmentDate,
        soh.[Shipment Date]              AS ActualShipDate,
        soh.[External Document No_]      AS ExternalDocNo,
        CASE
            WHEN soh.[Shipment Date] > soh.[Requested Delivery Date] THEN 1
            ELSE 0
        END AS IsDelayed,
        CASE
            WHEN soh.[Shipment Date] > soh.[Requested Delivery Date]
                THEN DATEDIFF(DAY,
                     soh.[Requested Delivery Date],
                     soh.[Shipment Date])
            ELSE 0
        END AS DelayDays
    FROM [Sales Order Header] soh
    WHERE soh.[Shipment Date] IS NOT NULL
      AND soh.[Requested Delivery Date] IS NOT NULL
      AND soh.[Shipment Date] <= ?
    ORDER BY soh.[Shipment Date], soh.[No_]
"""

# --- Truy vấn 3: Order Demand (Khối lượng đặt hàng) ---
# Nguồn: [Sales Order Line] JOIN [Sales Order Header]
#
# Lý do chuyển từ [Cust_ Ledger Entry]:
#   Chẩn đoán CSDL (2026-08-12) cho thấy [Cust_ Ledger Entry] chỉ có 3
#   bản ghi có Sales (LCY) ≠ 0 (toàn bộ từ 06/2010), [Sales Invoice Header]
#   rỗng hoàn toàn (0 hóa đơn). Công ty không posting hóa đơn vào NAV.
#
#   Thay vào đó, [Sales Order Line] có dữ liệu phong phú (join từ 8,580
#   Sales Order Header, phạm vi 2017–2027) với cột [Quantity] chứa khối
#   lượng đặt hàng thực tế.
#
# Biến OrderDemand (tổng Quantity/tuần) phản ánh ÁP LỰC ĐƠN HÀNG — động
# lực nhân quả đầu vào trong chuỗi: OrderDemand → ProductionVolume → DelayRate.
# Khi áp lực đơn hàng tăng → sản xuất phải tăng công suất → rủi ro trễ
# hạn tăng theo.
#
# Cột chính:
#   - sol.[Document No_]: mã đơn hàng (BDH) — khớp với Sales Order Header
#   - sol.[Quantity]: khối lượng đặt hàng (đơn vị: PCS hoặc theo sản phẩm)
#   - sol.[Shipment Date]: ngày giao dự kiến — mốc thời gian gán vào tuần
#   - sol.[No_]: mã sản phẩm (item code)
#   - soh.[Sell-to Customer No_]: mã khách hàng
#
# Dùng [Shipment Date] từ Sales Order Line (mỗi line có thể có ngày giao
# riêng, chính xác hơn dùng ngày từ Header).
SQL_ORDER_DEMAND = """
    SELECT
        sol.[Document No_]              AS OrderNo,
        sol.[Line No_]                  AS LineNo,
        soh.[Sell-to Customer No_]      AS CustomerCode,
        sol.[No_]                       AS ProductCode,
        sol.[Description],
        sol.[Quantity]                   AS Quantity,
        sol.[Outstanding Quantity]       AS OutstandingQty,
        sol.[Shipment Date]             AS ShipmentDate,
        sol.[Unit of Measure]           AS UnitOfMeasure

    FROM [Sales Order Line] sol
    INNER JOIN [Sales Order Header] soh
        ON sol.[Document No_] = soh.[No_]
        AND sol.[Document Type] = soh.[Document Type]
    WHERE sol.[Shipment Date] IS NOT NULL
      AND sol.[Quantity] > 0
      AND sol.[Shipment Date] <= ?
    ORDER BY sol.[Shipment Date], sol.[Document No_]
"""

# Ánh xạ tên bảng đầu ra → truy vấn SQL tương ứng
# Phương án A (2026-08-12): chuyển từ OEE/Revenue sang Production/OrderDemand
# vì CSDL NAV không có đủ dữ liệu Production Order (2 dòng) và Revenue (0 hóa đơn).
QUERIES = {
    "production_volume": SQL_PRODUCTION,
    "cmt_delay_results": SQL_DELAY,
    "order_demand": SQL_ORDER_DEMAND,
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
                "production_volume": "ValuedQty",
                "cmt_delay_results": "IsDelayed",
                "order_demand": "Quantity",
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

            if overlap_info["overlap_ratio"] < 0.50:
                logger.warning(
                    f"Tỉ lệ khớp OrderNo (Sales Order) giữa cmt_delay_results "
                    f"và order_demand = {ratio_pct:.2f}% (< 50%) — kiểm tra "
                    f"lại snapshot hoặc bảng ERP gốc. "
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
