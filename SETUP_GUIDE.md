# SETUP_GUIDE.md — Hướng dẫn Cài đặt và Vận hành

> Phiên bản: 2.0 | Cập nhật: 2026-08-10  
> Dự án: Hybrid Causal Forecasting — Phương án 3-A (Kiến trúc 4 Tầng)

---

## 1. Yêu cầu hệ thống (Prerequisites)

| Thành phần | Phiên bản tối thiểu | Ghi chú |
|---|---|---|
| Python | 3.9+ | Khuyến nghị 3.11 trở lên |
| Git | 2.30+ | Quản lý phiên bản mã nguồn |
| ODBC Driver for SQL Server | 17+ | Bắt buộc cho Tầng 1 (kết nối database) |
| pip | 21.0+ | Quản lý package Python |

**Kiểm tra nhanh:**

```bash
python --version        # >= 3.9
git --version           # >= 2.30
pip --version           # >= 21.0
```

Kiểm tra ODBC Driver đã cài:
- **Windows:** Mở ODBC Data Source Administrator → tab Drivers → xác nhận có "ODBC Driver 17 for SQL Server"
- **macOS/Linux:** `odbcinst -q -d` → phải thấy dòng `[ODBC Driver 17 for SQL Server]`

---

## 2. Thiết lập môi trường (Setup)

### 2.1. Clone repository

```bash
git clone https://github.com/daominhtri2025-crypto/Hybrid_Causal_Forecasting_3A.git
cd Hybrid_Causal_Forecasting_3A
```

### 2.2. Tạo Virtual Environment

**Windows (Command Prompt / PowerShell):**

```cmd
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**macOS / Linux (Terminal):**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2.3. Xác nhận cài đặt thành công

```bash
python -c "import pandas, pyodbc, statsmodels, torch; print('OK — Tất cả dependencies đã sẵn sàng')"
```

---

## 3. Cấu hình (Configuration)

### 3.1. Cấu hình kết nối Database (Bắt buộc cho Tầng 1)

Script `tang1_db_extractor.py` sử dụng thư viện `pyodbc` kết nối trực tiếp
vào SQL Server để truy vấn 4 bảng ERP gốc (`WorkOrders`, `ProductionLogs`,
`SalesOrders`, `Invoices`) và tính toán OEE/Delay/Revenue bằng SQL.

**Cách 1: Biến môi trường (Khuyến nghị — bảo mật)**

**Windows (Command Prompt):**

```cmd
set DB_SERVER=192.168.1.100\SQLEXPRESS
set DB_DATABASE=QTDN
set DB_DRIVER={ODBC Driver 17 for SQL Server}
set DB_TRUSTED=true
```

**Windows (PowerShell):**

```powershell
$env:DB_SERVER = "192.168.1.100\SQLEXPRESS"
$env:DB_DATABASE = "QTDN"
$env:DB_DRIVER = "{ODBC Driver 17 for SQL Server}"
$env:DB_TRUSTED = "true"
```

**macOS / Linux:**

```bash
export DB_SERVER="192.168.1.100\\SQLEXPRESS"
export DB_DATABASE="QTDN"
export DB_DRIVER="{ODBC Driver 17 for SQL Server}"
export DB_TRUSTED="true"
```

Nếu dùng SQL Server Authentication (thay vì Windows Auth):

```bash
export DB_TRUSTED="false"
export DB_USERNAME="sa"
export DB_PASSWORD="YourPassword123"
```

| Biến môi trường | Mô tả | Giá trị mặc định |
|---|---|---|
| `DB_SERVER` | Tên hoặc IP của SQL Server instance | `localhost` |
| `DB_DATABASE` | Tên database chứa bảng ERP | `QTDN` |
| `DB_DRIVER` | ODBC Driver string | `{ODBC Driver 17 for SQL Server}` |
| `DB_TRUSTED` | `true` = Windows Auth, `false` = SQL Auth | `true` |
| `DB_USERNAME` | Username (chỉ khi `DB_TRUSTED=false`) | _(trống)_ |
| `DB_PASSWORD` | Password (chỉ khi `DB_TRUSTED=false`) | _(trống)_ |

**Cách 2: Sửa trực tiếp trong code (Chỉ dùng khi test local)**

Mở `scripts/tang1_db_extractor.py`, tìm dict `DB_CONFIG` và sửa giá trị mặc định:

```python
DB_CONFIG = {
    "server": os.environ.get("DB_SERVER", "192.168.1.100\\SQLEXPRESS"),
    "database": os.environ.get("DB_DATABASE", "QTDN"),
    ...
}
```

> **Lưu ý bảo mật:** Không commit thông tin kết nối (đặc biệt password)
> lên Git. Nếu sửa trực tiếp trong code, đảm bảo file đã nằm trong
> `.gitignore` hoặc dùng biến môi trường thay thế.

### 3.2. Thư mục dữ liệu

Đảm bảo cấu trúc thư mục sau tồn tại trước khi chạy:

```
data/
├── raw/           # Tầng 1 sẽ ghi snapshot vào đây
└── processed/     # Tầng 2-4 sẽ ghi kết quả vào đây
```

Nếu chưa có, tạo bằng lệnh:

```bash
mkdir -p data/raw data/processed reports/logs
```

### 3.3. Tiền điều kiện: Bảng Dynamics NAV phải tồn tại trong CSDL

> **Quan trọng:** Script `tang1_db_extractor.py` truy vấn trực tiếp các bảng
> **Microsoft Dynamics NAV** trong database **QTDN** để tính toán 3 chỉ số:
>
> | Bảng NAV | Vai trò | Các cột chính |
> |---|---|---|
> | `[Production Order Header]` | Lệnh sản xuất | `No_`, `Starting Date`, `Ending Date`, `Source No_` |
> | `[Production Order Line]` | Chi tiết lệnh SX | `Prod_Order No_`, `Quantity`, `Finished Quantity`, `Scrap %` |
> | `[Sales Order Header]` | Đơn hàng bán | `No_`, `Sell-to Customer No_`, `Shipment Date`, `Requested Delivery Date` |
> | `[Cust_ Ledger Entry]` | Sổ cái khách hàng (doanh thu) | `Document No_`, `Customer No_`, `Sales (LCY)`, `Posting Date`, `Document Type` |
>
> **Lưu ý:** Doanh thu lấy từ `[Cust_ Ledger Entry].[Sales (LCY)]` — đây là
> bảng mà các hàm KPI trong CSDL QTDN thực sự sử dụng (KPI_0_91, KPI_2_51).
> Phiên bản trước dùng `[Import and Export Revenue Line]` nhưng bảng đó không
> được tham chiếu bởi bất kỳ hàm KPI nào trong CSDL.
>
> **Chỉ số đầu ra:**
>
> | File CSV | Công thức | Nguồn NAV |
> |---|---|---|
> | `cmt_oee_results.csv` | `OEE = P × Q` (Performance × Quality) | `[Production Order Header]` JOIN `[Production Order Line]` |
> | `cmt_delay_results.csv` | `IsDelayed`, `DelayDays` | `[Sales Order Header]` |
> | `fob_revenue.csv` | `Revenue = Sales (LCY)` | `[Cust_ Ledger Entry]` (Document Type = Invoice) |
>
> **Trước khi chạy Tầng 1, phải xác nhận** các bảng trên đã tồn tại:
>
> ```sql
> SELECT COUNT(*) FROM [Production Order Header]  WHERE [Ending Date] IS NOT NULL;
> SELECT COUNT(*) FROM [Production Order Line]     WHERE [Quantity] > 0;
> SELECT COUNT(*) FROM [Sales Order Header]        WHERE [Shipment Date] IS NOT NULL;
> SELECT COUNT(*) FROM [Cust_ Ledger Entry]        WHERE [Document Type] = 2 AND [Sales (LCY)] <> 0;
> ```
>
> Nếu thấy lỗi `Invalid object name 'Cust_ Ledger Entry'`, thử thay bằng
> `[Customer Ledger Entry]` (tên NAV Business Central). Nếu thấy lỗi
> `Invalid column name`, chạy `SELECT TOP 1 * FROM [tên bảng]` để xem tên
> cột thực tế, rồi sửa biến `SQL_OEE`, `SQL_DELAY`, `SQL_REVENUE` trong
> `scripts/tang1_db_extractor.py` cho khớp.

---

## 4. Vận hành (Execution)

Chạy tuần tự từ Tầng 1 đến Tầng 4. Mỗi tầng đọc output của tầng trước —
**không được bỏ qua bước nào**.

### Tầng 1 — Khai thác dữ liệu từ SQL Server

```bash
python -m scripts.tang1_db_extractor
```

> Yêu cầu: Các bảng Dynamics NAV phải tồn tại trong CSDL QTDN — xem mục 3.3.
> Cấu hình kết nối phải hoàn tất — xem mục 3.1.

- Kết nối SQL Server qua `pyodbc`, truy vấn bảng NAV và TÍNH TOÁN:
  - `OEE_Score` = P × Q (từ `[Production Order Header]` JOIN `[Production Order Line]`)
    - P (Performance) = `Finished Quantity` / `Quantity`
    - Q (Quality) = 1 - `Scrap %` / 100
  - `IsDelayed`, `DelayDays` (từ `[Sales Order Header]`)
  - `Revenue` = `Sales (LCY)` (từ `[Cust_ Ledger Entry]`, chỉ lấy hóa đơn)
- Tính Jaccard Index kiểm tra overlap OrderNo giữa các bảng
- Tính SHA-256 checksum cho từng file đầu ra
- Ghi snapshot bất biến vào `data/raw/snapshot_YYYYMMDD_HHMM/`

### Tầng 2 — Tiền xử lý và xây dựng dataset tuần (Phase 0)

```bash
python -m scripts.phase0_data_reengineering
```

- Gộp 3 bảng theo OrderNo, tổng hợp theo tuần (ISO week)
- Tính weighted average OEE, interpolate giá trị thiếu (limit=2)
- Ghi `data/processed/causal_weekly_dataset.csv`

> **Điểm dừng xác nhận #1:** Kiểm tra file CSV đầu ra trước khi tiếp tục.

### Tầng 3 — Kiểm định kinh tế lượng (Phase 1 → Phase 3b)

Chạy lần lượt 4 script:

```bash
# Phase 1: Kiểm định tính dừng (ADF + KPSS Dual Confirmation)
python -m scripts.phase1_stationarity

# Phase 2: Kiểm định nhân quả Granger
python -m scripts.phase2_granger_causality

# Phase 3: Kiểm định đồng tích hợp Johansen (Trace + Max-Eigenvalue)
python -m scripts.phase3_cointegration

# Phase 3b: Kiểm định Toda-Yamamoto (Cross-check nhân quả trên biến levels)
python -m scripts.phase3b_toda_yamamoto
```

| Script | Chức năng | Output JSON |
|---|---|---|
| `phase1_stationarity.py` | Xác định bậc tích hợp d(i) cho từng biến | `reports/phase1_stationarity.json` |
| `phase2_granger_causality.py` | Kiểm định quan hệ nhân quả Granger pairwise | `reports/phase2_granger_causality.json` |
| `phase3_cointegration.py` | Xác định rank đồng tích hợp r, chọn route VECM/VAR | `reports/phase3_cointegration.json` |
| `phase3b_toda_yamamoto.py` | Cross-check nhân quả bằng Toda-Yamamoto | `reports/phase3b_toda_yamamoto.json` |

> **Điểm dừng xác nhận #2:** Kiểm tra kết quả route (VECM hay VAR) trong
> `reports/phase3_cointegration.json` trước khi chạy Tầng 4.

### Tầng 4 — Dự báo VECM

```bash
python -m scripts.tang4_vecm_forecasting
```

- Đọc tham số từ JSON của Tầng 3 (k_ar_diff, coint_rank, deterministic)
- Ước lượng mô hình VECM, tính dự báo 12 tuần + khoảng tin cậy 95%
- Ghi kết quả ra `reports/` và `data/processed/figures/`

### 4.2b. Orchestrator — `main_pipeline.py` (Khuyến nghị)

Thay vì chạy từng script riêng lẻ, có thể sử dụng **orchestrator** để chạy
toàn bộ pipeline tự động, bao gồm error handling và ghi nhật ký chuyển tiếp
giữa các Phase:

```bash
python -m main_pipeline
```

#### Tham số dòng lệnh (CLI Arguments)

| Tham số | Mô tả | Ví dụ |
|---|---|---|
| `--resume-from` | Tiếp tục pipeline từ Phase chỉ định — bỏ qua các Phase trước nếu output đã có | `--resume-from phase3` |
| `--stop-after` | Dừng pipeline sau Phase chỉ định (không chạy Phase tiếp theo) | `--stop-after phase1` |

#### Checkpoint/Resume — Tiếp tục từ Phase bất kỳ

Cơ chế `--resume-from` cho phép **bỏ qua các Phase đã chạy thành công** —
tiết kiệm thời gian khi debug hoặc phát triển Phase cụ thể:

```bash
# Chạy toàn bộ pipeline từ đầu
python -m main_pipeline

# Tiếp tục từ Phase 3 — Phase 0 và 1 được bỏ qua nếu output JSON/CSV đã tồn tại
python -m main_pipeline --resume-from phase3

# Chỉ chạy Phase 4
python -m main_pipeline --resume-from phase4 --stop-after phase4
```

**Cơ chế hoạt động:**

Mỗi Phase có **file output kỳ vọng** (JSON contract):

| Phase | File output kỳ vọng |
|---|---|
| Phase 0 | `data/processed/causal_weekly_dataset.csv` |
| Phase 1 | `reports/phase1_stationarity.json` |
| Phase 2 | `reports/phase2_granger_causality.json` |
| Phase 3 | `reports/phase3_cointegration.json` |
| Phase 3b | `reports/phase3b_toda_yamamoto.json` |

Khi `--resume-from` được truyền:
1. Các Phase **trước** điểm resume sẽ kiểm tra file output: nếu tồn tại và
   không rỗng → bỏ qua (status = `skipped (resume)`).
2. Nếu file output không tồn tại → Phase đó **vẫn chạy** (không crash).
3. Nhật ký chuyển tiếp được ghi vào `reports/logs/phase_transitions.jsonl`
   (định dạng JSONL, 1 dòng/transition).

**Lưu ý quan trọng:**
- `--resume-from` **không đảm bảo** kết quả Phase trước vẫn hợp lệ — nếu đã
  thay đổi dữ liệu đầu vào hoặc tham số, nên chạy lại từ đầu.
- Dùng chủ yếu để **debug** và **phát triển** — trong production nên chạy
  toàn bộ pipeline (`python -m main_pipeline` không có flag).

---

## 5. Kiểm tra đầu ra (Output)

Sau khi chạy xong toàn bộ pipeline, kiểm tra các thư mục sau:

| Thư mục | Nội dung | Kiểm tra |
|---|---|---|
| `data/raw/` | Snapshot thô từ SQL Server (bất biến) | File CSV + `MANIFEST.md` |
| `data/processed/` | Dataset tuần, biểu đồ, kết quả trung gian | `causal_weekly_dataset.csv` |
| `data/processed/figures/` | Biểu đồ IRF, forecast, CI | Các file `.png` |
| `reports/` | Kết quả kiểm định dạng JSON (machine-readable) | `phase1_*.json` → `phase3b_*.json` |
| `reports/logs/` | Log vận hành từng lần chạy | `pipeline_YYYYMMDD_HHMM.log` |

### Kiểm tra nhanh bằng lệnh:

```bash
# Xác nhận các file JSON kết quả đã được tạo
ls reports/phase*.json

# Xem log của lần chạy gần nhất
ls -lt reports/logs/ | head -5

# Đếm số tuần trong dataset
wc -l data/processed/causal_weekly_dataset.csv
```

---

## 6. Xử lý sự cố (Troubleshooting)

| Lỗi | Nguyên nhân | Giải pháp |
|---|---|---|
| `ModuleNotFoundError: pyodbc` | Chưa cài dependencies | `pip install -r requirements.txt` |
| `[IM002] Data source name not found` | Thiếu ODBC Driver | Cài ODBC Driver 17 for SQL Server |
| `FileNotFoundError: reports/phase1_*.json` | Chạy sai thứ tự | Chạy lại từ Tầng 1, tuần tự |
| `Connection timeout` | SQL Server không truy cập được | Kiểm tra firewall, IP, tên instance |
| `Invalid object name 'Production Order Header'` | Bảng NAV chưa tồn tại trong CSDL hoặc sai tên | Chạy `SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME LIKE '%Production%'` để tìm tên đúng; xem mục 3.3 |
| `Invalid column name 'Finished Quantity'` | Tên cột NAV khác với mặc định | Chạy `SELECT TOP 1 * FROM [tên bảng]` để xem cột thực tế, sửa biến `SQL_OEE`/`SQL_DELAY`/`SQL_REVENUE` |
| `Login failed for user` | Sai username/password hoặc chưa cấu hình | Kiểm tra biến môi trường `DB_USERNAME`, `DB_PASSWORD`, `DB_TRUSTED`; xem mục 3.1 |

---

## 7. Liên hệ hỗ trợ

- **Quản lý dự án:** Đào Minh Trí (daominhtri2025@gmail.com)
- **Repository:** https://github.com/daominhtri2025-crypto/Hybrid_Causal_Forecasting_3A
