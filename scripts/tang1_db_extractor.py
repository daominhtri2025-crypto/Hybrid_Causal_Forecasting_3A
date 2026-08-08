"""
Tầng 1 — DB Layer: Khai thác dữ liệu gốc từ SQL Server.

Mục đích:
    Trích xuất 3 bảng dữ liệu (`cmt_oee_results`, `cmt_delay_results`,
    `fob_revenue`) từ database `qtdn_datamining` trên SQL Server, đảm bảo cả
    3 truy vấn phản ánh CÙNG MỘT lát cắt thời gian (snapshot) — tránh lệch
    OrderNo giữa các file do đơn hàng phát sinh giữa các lần truy vấn.

Thiết kế (theo ARCHITECTURE_4_tang.md, Tầng 1):
    1. Mở 1 kết nối SQL Server duy nhất, chốt `snapshot_time` MỘT LẦN.
    2. Chạy 3 truy vấn trong cùng session, mỗi truy vấn lọc theo
       `WHERE <cột thời gian> <= @snapshot_time`.
    3. Ghi NGUYÊN TRẠNG ra `data/raw/snapshot_YYYYMMDD_HHMM/*.csv` — KHÔNG
       transform, KHÔNG đổi tên cột (tuân thủ nguyên tắc bất biến, CLAUDE.md
       mục 2).
    4. Tự động cập nhật `data/raw/MANIFEST.md`: timestamp, checksum SHA-256,
       số dòng mỗi file, tỉ lệ khớp OrderNo giữa 3 file.

Input:  SQL Server (`qtdn_datamining`) — ĐÂY LÀ ĐIỂM TRUY CẬP SQL SERVER
        DUY NHẤT của toàn bộ Phương án 3 (CLAUDE.md mục 4).
Output: `data/raw/snapshot_YYYYMMDD_HHMM/{cmt_oee_results.csv,
        cmt_delay_results.csv, fob_revenue.csv}` + `data/raw/MANIFEST.md`.
Sở hữu: Role A — Data Engineering (skill.md).

Thay đổi so với bản trước: Đây là bản rebuild hoàn toàn (Phương án 3-A),
    không kế thừa code cũ.
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
# máy local. Script này KHÔNG đọc từ biến môi trường ẩn — đảm bảo tái
# lập được (reproducibility, CLAUDE.md mục 3.5).
# =====================================================================
DB_CONFIG = {
    "server": "localhost",          # Thay bằng tên/IP SQL Server thực tế
    "database": "qtdn_datamining",
    "driver": "{ODBC Driver 17 for SQL Server}",
    # Nếu dùng Windows Authentication, để trống username/password
    # và thêm "Trusted_Connection=yes" vào connection string.
    "username": "",
    "password": "",
    "trusted_connection": True,     # True = Windows Auth, False = SQL Auth
}

# Số lần thử kết nối lại khi SQL Server không phản hồi
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
        f"Kiểm tra lại cấu hình DB_CONFIG trong tang1_db_extractor.py."
    )
    raise ConnectionError(
        f"Không thể kết nối SQL Server sau {MAX_RETRY} lần thử."
    ) from last_error


def _compute_sha256(file_path: str) -> str:
    """Tính checksum SHA-256 cho file — dùng để ghi vào MANIFEST.md."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _compute_orderno_overlap(dataframes: dict[str, pd.DataFrame]) -> dict:
    """
    Tính tỉ lệ khớp OrderNo giữa 3 file.

    Mục đích: phát hiện sớm lệch dữ liệu do snapshot không đồng thời
    (ARCHITECTURE_4_tang.md, Tầng 1, mục 4). Nếu tỉ lệ khớp < 95%,
    Tầng 1 ghi WARNING (CLAUDE.md mục 7.3).

    Trả về dict chứa:
        - sets: tập OrderNo của từng file (để debug nếu cần)
        - overlap_ratio: tỉ lệ giao/hợp (Jaccard index) giữa 3 tập
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
# CÁC TRUY VẤN SQL — GIỮ NGUYÊN TÊN CỘT GỐC TỪ DATABASE
# =====================================================================
# Mỗi truy vấn lọc theo `<cột thời gian> <= @snapshot_time` để đảm bảo
# cả 3 file phản ánh cùng một lát cắt thời gian (ARCHITECTURE, Tầng 1,
# mục 2). Cột thời gian cụ thể phụ thuộc vào cấu trúc bảng trong
# database qtdn_datamining — Anh Béo xác nhận/điều chỉnh tên cột nếu
# cần trước khi chạy chính thức.
# =====================================================================

QUERIES = {
    "cmt_oee_results": """
        SELECT *
        FROM cmt_oee_results
        WHERE ActualEndDate <= ?
    """,
    "cmt_delay_results": """
        SELECT *
        FROM cmt_delay_results
        WHERE ActualEndDate <= ?
    """,
    "fob_revenue": """
        SELECT *
        FROM fob_revenue
        WHERE ShipmentDate <= ?
    """,
}


def extract_snapshot() -> str:
    """
    Hàm chính của Tầng 1: trích xuất snapshot đồng thời từ SQL Server.

    Quy trình:
        1. Chốt snapshot_time — MỘT LẦN duy nhất cho cả 3 truy vấn.
        2. Kết nối SQL Server (có retry).
        3. Chạy tuần tự 3 truy vấn, mỗi truy vấn lọc <= snapshot_time.
        4. Ghi nguyên trạng ra CSV (KHÔNG transform — CLAUDE.md mục 2).
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
    # Bước 2: Kết nối SQL Server
    # -----------------------------------------------------------------
    conn = _connect_sql_server()

    try:
        dataframes: dict[str, pd.DataFrame] = {}
        file_info_list: list[dict] = []

        # -----------------------------------------------------------------
        # Bước 3: Chạy tuần tự 3 truy vấn — mỗi truy vấn dùng chung
        # snapshot_time làm tham số lọc. Chạy tuần tự (không parallel) vì
        # dùng chung 1 kết nối — đủ nhanh cho dataset quy mô này, và đơn
        # giản hơn khi debug nếu có lỗi.
        # -----------------------------------------------------------------
        for table_name, query in QUERIES.items():
            logger.info(f"Đang truy vấn bảng '{table_name}'...")

            df = pd.read_sql(query, conn, params=[snapshot_time])
            row_count = len(df)

            # Ghi INFO số dòng — bắt buộc theo CLAUDE.md mục 7.3
            logger.info(
                f"Đã tải '{table_name}': {row_count:,} dòng, "
                f"{len(df.columns)} cột."
            )

            # Ghi WARNING nếu bảng rỗng — bất thường nhưng chưa crash
            if row_count == 0:
                logger.warning(
                    f"Bảng '{table_name}' trả về 0 dòng — kiểm tra lại "
                    f"snapshot_time ({snapshot_time.isoformat()}) hoặc dữ "
                    f"liệu trong database."
                )

            # ---------------------------------------------------------------
            # Bước 4: Ghi nguyên trạng ra CSV — TUYỆT ĐỐI KHÔNG transform.
            # Giữ nguyên tên cột gốc từ SQL Server, không đổi encoding,
            # không lọc/sửa giá trị. Tuân thủ nguyên tắc bất biến dữ liệu
            # (CLAUDE.md mục 2, điểm 1 và 3).
            # ---------------------------------------------------------------
            csv_filename = f"{table_name}.csv"
            csv_path = os.path.join(snapshot_dir, csv_filename)
            df.to_csv(csv_path, index=False, encoding="utf-8-sig")

            logger.info(f"Đã ghi '{csv_filename}' ({row_count:,} dòng).")

            # Tính checksum SHA-256 cho file vừa ghi — dùng cho MANIFEST.md
            sha256 = _compute_sha256(csv_path)

            dataframes[table_name] = df
            file_info_list.append({
                "filename": csv_filename,
                "row_count": row_count,
                "sha256": sha256,
            })

        # -----------------------------------------------------------------
        # Bước 5: Tính tỉ lệ khớp OrderNo và cập nhật MANIFEST.md
        # -----------------------------------------------------------------
        overlap_info = _compute_orderno_overlap(dataframes)

        if overlap_info.get("overlap_ratio") is not None:
            ratio_pct = overlap_info["overlap_ratio"] * 100
            logger.info(f"Tỉ lệ khớp OrderNo (Jaccard): {ratio_pct:.2f}%")

            # WARNING nếu tỉ lệ khớp < 95% — dấu hiệu snapshot không đồng
            # thời hoặc dữ liệu bất thường (ARCHITECTURE, Tầng 1, mục 5).
            if overlap_info["overlap_ratio"] < 0.95:
                logger.warning(
                    f"Tỉ lệ khớp OrderNo giữa các file = {ratio_pct:.2f}% "
                    f"(< 95%) — kiểm tra lại xem snapshot có đồng thời không, "
                    f"hoặc có bảng nào thiếu dữ liệu OrderNo. "
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
        conn.close()
        logger.info("Đã đóng kết nối SQL Server.")

    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info(f"Tầng 1 hoàn tất trong {elapsed:.1f}s. Snapshot: {snapshot_dir}")

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
    except Exception:
        logger.exception("Tầng 1 thất bại — xem traceback ở trên.")
        sys.exit(1)
