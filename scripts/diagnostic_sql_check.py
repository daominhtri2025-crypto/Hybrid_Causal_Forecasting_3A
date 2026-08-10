"""
diagnostic_sql_check.py — Chẩn đoán CSDL QTDN trước khi chạy pipeline.

Mục đích:
    Kiểm tra toàn diện số lượng dòng và cấu trúc cột của TẤT CẢ bảng NAV
    liên quan đến 3 truy vấn chính (OEE, Delay, Revenue) trong Tầng 1.
    Giúp xác định bảng nào có dữ liệu, bảng nào rỗng, và nên dùng bảng
    nào cho từng KPI.

Cách dùng:
    python -m scripts.diagnostic_sql_check

Output:
    In ra console bảng tổng hợp số dòng từng bảng và tên cột thực tế.
    KHÔNG ghi file — chỉ dùng để chẩn đoán nhanh.

Lưu ý:
    Script này là công cụ hỗ trợ, không thuộc pipeline chính (Phase 0–5).
    Dùng pyodbc trực tiếp (giống tang1_db_extractor.py).
"""

import pyodbc
import sys

# =====================================================================
# Cấu hình kết nối — giống tang1_db_extractor.py
# =====================================================================
CONN_STR = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=DESKTOP-N6DB06M\\SQLEXPRESS;"
    "DATABASE=QTDN;"
    "Trusted_Connection=yes;"
)

# =====================================================================
# Danh sách bảng cần kiểm tra — chia theo nhóm KPI
# =====================================================================
TABLES_TO_CHECK = {
    "=== PRODUCTION (OEE) ===": [
        "[Production Order Header]",
        "[Production Order Header Posted]",
        "[Production Order Line]",
        "[Production Order Routing Finished]",
    ],
    "=== SALES (DELAY) ===": [
        "[Sales Order Header]",
        "[Sales Order Line]",
        "[Sales Order Line Detail]",
        "[Sales Order Line Factory]",
    ],
    "=== REVENUE ===": [
        "[Cust_ Ledger Entry]",
        "[Customer Ledger Entry]",
        "[Import and Export Revenue Line]",
    ],
}

# =====================================================================
# Các cột quan trọng cần kiểm tra sự tồn tại
# =====================================================================
CRITICAL_COLUMNS = {
    "[Production Order Header]": [
        "No_", "Status", "Starting Date", "Ending Date",
        "Source No_", "Description",
    ],
    "[Production Order Header Posted]": [
        "No_", "Posting Date", "Source No_", "Description",
    ],
    "[Production Order Line]": [
        "Prod_ Order No_", "Status", "Item No_",
        "Quantity", "Finished Quantity", "Remaining Quantity", "Scrap %",
    ],
    "[Production Order Routing Finished]": [
        "Prod_ Order No_", "Run Time", "Setup Time", "Move Time",
    ],
    "[Sales Order Header]": [
        "No_", "Sell-to Customer No_",
        "Shipment Date", "Requested Delivery Date",
    ],
    "[Cust_ Ledger Entry]": [
        "Document No_", "Customer No_", "Document Type",
        "Sales (LCY)", "Posting Date",
    ],
}


def main():
    print("=" * 70)
    print("  CHẨN ĐOÁN CSDL QTDN — Kiểm tra bảng và cột cho Tầng 1")
    print("=" * 70)
    print()

    # --- Kết nối ---
    try:
        conn = pyodbc.connect(CONN_STR, timeout=10)
        cursor = conn.cursor()
        print("[OK] Kết nối SQL Server thành công.\n")
    except Exception as e:
        print(f"[LỖI] Không thể kết nối SQL Server: {e}")
        sys.exit(1)

    # --- Phần 1: Đếm dòng từng bảng ---
    print("-" * 70)
    print("  PHẦN 1: SỐ DÒNG TỪNG BẢNG")
    print("-" * 70)

    for group_name, tables in TABLES_TO_CHECK.items():
        print(f"\n{group_name}")
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"  {table:<45} → {count:>10,} dòng")
            except pyodbc.ProgrammingError:
                print(f"  {table:<45} → KHÔNG TỒN TẠI")
            except Exception as e:
                print(f"  {table:<45} → LỖI: {e}")

    # --- Phần 2: Kiểm tra cột quan trọng ---
    print()
    print("-" * 70)
    print("  PHẦN 2: KIỂM TRA CỘT QUAN TRỌNG")
    print("-" * 70)

    for table, columns in CRITICAL_COLUMNS.items():
        print(f"\n  {table}:")
        # Lấy danh sách cột thực tế từ INFORMATION_SCHEMA
        table_clean = table.strip("[]")
        try:
            cursor.execute(
                "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_NAME = ? ORDER BY ORDINAL_POSITION",
                [table_clean],
            )
            actual_cols = {row[0] for row in cursor.fetchall()}

            if not actual_cols:
                print("    → Bảng không tồn tại hoặc không có cột nào.")
                continue

            for col in columns:
                status = "OK" if col in actual_cols else "THIẾU"
                print(f"    [{status:>5}] {col}")

        except Exception as e:
            print(f"    → LỖI: {e}")

    # --- Phần 3: Xem mẫu dữ liệu (TOP 3) cho bảng có dữ liệu ---
    print()
    print("-" * 70)
    print("  PHẦN 3: MẪU DỮ LIỆU (TOP 3 DÒNG)")
    print("-" * 70)

    sample_tables = [
        "[Production Order Header]",
        "[Production Order Header Posted]",
        "[Production Order Line]",
        "[Cust_ Ledger Entry]",
    ]

    for table in sample_tables:
        print(f"\n  {table}:")
        try:
            cursor.execute(f"SELECT TOP 3 * FROM {table}")
            cols = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()

            if not rows:
                print("    (rỗng)")
                continue

            # In tên cột
            print(f"    Cột: {cols}")
            for i, row in enumerate(rows, 1):
                # Chỉ in 5 cột đầu để không quá dài
                preview = list(row[:5])
                suffix = f"  ... (+{len(row)-5} cột)" if len(row) > 5 else ""
                print(f"    Dòng {i}: {preview}{suffix}")

        except pyodbc.ProgrammingError:
            print("    → Bảng KHÔNG TỒN TẠI")
        except Exception as e:
            print(f"    → LỖI: {e}")

    # --- Phần 4: Đếm OEE và Revenue theo điều kiện filter hiện tại ---
    print()
    print("-" * 70)
    print("  PHẦN 4: ĐẾM THEO FILTER CỦA TẦNG 1")
    print("-" * 70)

    checks = [
        (
            "OEE (Header có Ending Date)",
            "SELECT COUNT(*) FROM [Production Order Header] "
            "WHERE [Ending Date] IS NOT NULL",
        ),
        (
            "OEE (Header Posted — tổng)",
            "SELECT COUNT(*) FROM [Production Order Header Posted]",
        ),
        (
            "OEE (Header — tổng, mọi Status)",
            "SELECT COUNT(*) FROM [Production Order Header]",
        ),
        (
            "OEE (Header theo Status)",
            "SELECT [Status], COUNT(*) AS cnt "
            "FROM [Production Order Header] GROUP BY [Status]",
        ),
        (
            "Revenue (Cust_ Ledger, Doc Type=2, Sales<>0)",
            "SELECT COUNT(*) FROM [Cust_ Ledger Entry] "
            "WHERE [Document Type] = 2 AND [Sales (LCY)] <> 0",
        ),
        (
            "Revenue (Cust_ Ledger, mọi loại)",
            "SELECT COUNT(*) FROM [Cust_ Ledger Entry]",
        ),
        (
            "Revenue (theo Document Type)",
            "SELECT [Document Type], COUNT(*) AS cnt "
            "FROM [Cust_ Ledger Entry] GROUP BY [Document Type]",
        ),
    ]

    for label, sql in checks:
        print(f"\n  {label}:")
        try:
            cursor.execute(sql)
            rows = cursor.fetchall()
            cols = [desc[0] for desc in cursor.description]

            if len(cols) == 1:
                print(f"    → {rows[0][0]:,}")
            else:
                for row in rows:
                    parts = [f"{c}={v}" for c, v in zip(cols, row)]
                    print(f"    → {', '.join(parts)}")

        except pyodbc.ProgrammingError as e:
            print(f"    → KHÔNG THỂ CHẠY: {e}")
        except Exception as e:
            print(f"    → LỖI: {e}")

    # --- Kết thúc ---
    conn.close()
    print()
    print("=" * 70)
    print("  CHẨN ĐOÁN HOÀN TẤT")
    print("  Gửi toàn bộ output ở trên cho Claude để phân tích tiếp.")
    print("=" * 70)


if __name__ == "__main__":
    main()
