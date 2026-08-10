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
set DB_DATABASE=qtdn_datamining
set DB_DRIVER={ODBC Driver 17 for SQL Server}
set DB_TRUSTED=true
```

**Windows (PowerShell):**

```powershell
$env:DB_SERVER = "192.168.1.100\SQLEXPRESS"
$env:DB_DATABASE = "qtdn_datamining"
$env:DB_DRIVER = "{ODBC Driver 17 for SQL Server}"
$env:DB_TRUSTED = "true"
```

**macOS / Linux:**

```bash
export DB_SERVER="192.168.1.100\\SQLEXPRESS"
export DB_DATABASE="qtdn_datamining"
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
| `DB_DATABASE` | Tên database chứa bảng ERP | `qtdn_datamining` |
| `DB_DRIVER` | ODBC Driver string | `{ODBC Driver 17 for SQL Server}` |
| `DB_TRUSTED` | `true` = Windows Auth, `false` = SQL Auth | `true` |
| `DB_USERNAME` | Username (chỉ khi `DB_TRUSTED=false`) | _(trống)_ |
| `DB_PASSWORD` | Password (chỉ khi `DB_TRUSTED=false`) | _(trống)_ |

**Cách 2: Sửa trực tiếp trong code (Chỉ dùng khi test local)**

Mở `scripts/tang1_db_extractor.py`, tìm dict `DB_CONFIG` và sửa giá trị mặc định:

```python
DB_CONFIG = {
    "server": os.environ.get("DB_SERVER", "192.168.1.100\\SQLEXPRESS"),
    "database": os.environ.get("DB_DATABASE", "qtdn_datamining"),
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

### 3.3. Tiền điều kiện: 4 bảng ERP gốc phải tồn tại trong CSDL

> **Quan trọng:** Script `tang1_db_extractor.py` truy vấn trực tiếp **4 bảng
> ERP gốc** trong database `qtdn_datamining` để tính toán 3 chỉ số phân tích:
>
> | Bảng ERP gốc | Vai trò | Các cột chính |
> |---|---|---|
> | `WorkOrders` | Lệnh sản xuất | `OrderNo`, `PlanQty`, `ActualEndDate`, `MachineLine` |
> | `ProductionLogs` | Dữ liệu vận hành máy | `PlannedOperatingMinutes`, `ActualWorkingMinutes`, `TotalQty`, `GoodQty`, `StandardCycleTime` |
> | `SalesOrders` | Đơn hàng bán | `OrderNo`, `PlannedShipmentDate`, `ActualShipDate` |
> | `Invoices` | Hóa đơn/doanh thu | `OrderNo`, `Quantity`, `UnitPrice`, `ShipmentDate` |
>
> **Chỉ số đầu ra:**
>
> | File CSV | Công thức | Nguồn |
> |---|---|---|
> | `cmt_oee_results.csv` | `OEE = A × P × Q` (phân rã 3 thành phần) | `WorkOrders` JOIN `ProductionLogs` |
> | `cmt_delay_results.csv` | `IsDelayed`, `DelayDays` | `SalesOrders` |
> | `fob_revenue.csv` | `Revenue = Quantity × UnitPrice` | `Invoices` |
>
> **Trước khi chạy Tầng 1, phải xác nhận** 4 bảng trên đã tồn tại và có
> dữ liệu trong CSDL. Kiểm tra nhanh bằng SQL:
>
> ```sql
> SELECT COUNT(*) FROM WorkOrders     WHERE ActualEndDate IS NOT NULL;
> SELECT COUNT(*) FROM ProductionLogs WHERE OrderNo IS NOT NULL;
> SELECT COUNT(*) FROM SalesOrders    WHERE ActualShipDate IS NOT NULL;
> SELECT COUNT(*) FROM Invoices       WHERE ShipmentDate IS NOT NULL;
> ```
>
> Nếu tên bảng/cột trong database thực tế khác tên placeholder ở trên
> (vd: `TotalQty` thực tế là `ProducedQuantity`), cần sửa lại các biến
> `SQL_OEE`, `SQL_DELAY`, `SQL_REVENUE` trong `scripts/tang1_db_extractor.py`
> cho khớp với schema thật.

---

## 4. Vận hành (Execution)

Chạy tuần tự từ Tầng 1 đến Tầng 4. Mỗi tầng đọc output của tầng trước —
**không được bỏ qua bước nào**.

### Tầng 1 — Khai thác dữ liệu từ SQL Server

```bash
python scripts/tang1_db_extractor.py
```

> Yêu cầu: 4 bảng ERP gốc (`WorkOrders`, `ProductionLogs`, `SalesOrders`,
> `Invoices`) phải tồn tại trong CSDL — xem mục 3.3 trước khi chạy.
> Cấu hình kết nối phải hoàn tất — xem mục 3.1.

- Kết nối SQL Server qua `pyodbc`, truy vấn 4 bảng ERP gốc và TÍNH TOÁN:
  - `OEE_Score` = A × P × Q (từ `WorkOrders` JOIN `ProductionLogs`)
    - A = ActualWorkingMinutes / PlannedOperatingMinutes
    - P = (TotalQty × StandardCycleTime) / ActualWorkingMinutes
    - Q = GoodQty / TotalQty
  - `IsDelayed`, `DelayDays` (từ `SalesOrders`)
  - `Revenue` = Quantity × UnitPrice (từ `Invoices`)
- Tính Jaccard Index kiểm tra overlap OrderNo giữa các bảng
- Tính SHA-256 checksum cho từng file đầu ra
- Ghi snapshot bất biến vào `data/raw/snapshot_YYYYMMDD_HHMM/`

### Tầng 2 — Tiền xử lý và xây dựng dataset tuần (Phase 0)

```bash
python scripts/phase0_data_reengineering.py
```

- Gộp 3 bảng theo OrderNo, tổng hợp theo tuần (ISO week)
- Tính weighted average OEE, interpolate giá trị thiếu (limit=2)
- Ghi `data/processed/causal_weekly_dataset.csv`

> **Điểm dừng xác nhận #1:** Kiểm tra file CSV đầu ra trước khi tiếp tục.

### Tầng 3 — Kiểm định kinh tế lượng (Phase 1 → Phase 3b)

Chạy lần lượt 4 script:

```bash
# Phase 1: Kiểm định tính dừng (ADF + KPSS Dual Confirmation)
python scripts/phase1_stationarity.py

# Phase 2: Kiểm định nhân quả Granger
python scripts/phase2_granger_causality.py

# Phase 3: Kiểm định đồng tích hợp Johansen (Trace + Max-Eigenvalue)
python scripts/phase3_cointegration.py

# Phase 3b: Kiểm định Toda-Yamamoto (Cross-check nhân quả trên biến levels)
python scripts/phase3b_toda_yamamoto.py
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
python scripts/tang4_vecm_forecasting.py
```

- Đọc tham số từ JSON của Tầng 3 (k_ar_diff, coint_rank, deterministic)
- Ước lượng mô hình VECM, tính dự báo 12 tuần + khoảng tin cậy 95%
- Ghi kết quả ra `reports/` và `data/processed/figures/`

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
| `Invalid object name 'WorkOrders'` (hoặc `ProductionLogs`/`SalesOrders`/`Invoices`) | Bảng ERP gốc chưa tồn tại trong CSDL hoặc sai tên | Kiểm tra schema CSDL thực tế, sửa tên bảng/cột trong biến `SQL_OEE`, `SQL_DELAY`, `SQL_REVENUE` ở `tang1_db_extractor.py`; xem mục 3.3 |
| `Login failed for user` | Sai username/password hoặc chưa cấu hình | Kiểm tra biến môi trường `DB_USERNAME`, `DB_PASSWORD`, `DB_TRUSTED`; xem mục 3.1 |

---

## 7. Liên hệ hỗ trợ

- **Quản lý dự án:** Đào Minh Trí (daominhtri2025@gmail.com)
- **Repository:** https://github.com/daominhtri2025-crypto/Hybrid_Causal_Forecasting_3A
