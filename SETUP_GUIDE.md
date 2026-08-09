# SETUP_GUIDE.md — Hướng dẫn Cài đặt và Vận hành

> Phiên bản: 1.0 | Cập nhật: 2026-08-09  
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

### 3.1. Thông tin Database (Bắt buộc cho Tầng 1)

Mở file `scripts/tang1_db_extractor.py` và cập nhật các hằng số kết nối:

| Biến | Mô tả | Ví dụ |
|---|---|---|
| `SERVER_NAME` | Tên hoặc IP của SQL Server | `"192.168.1.100\\SQLEXPRESS"` |
| `DATABASE_NAME` | Tên database chứa dữ liệu CMT | `"CMT_Production"` |
| `DRIVER` | ODBC Driver string | `"{ODBC Driver 17 for SQL Server}"` |

> **Lưu ý bảo mật:** Không commit thông tin kết nối database lên Git. Nếu cần
> chia sẻ code, hãy dùng biến môi trường hoặc file `.env` (đã có trong `.gitignore`).

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

---

## 4. Vận hành (Execution)

Chạy tuần tự từ Tầng 1 đến Tầng 4. Mỗi tầng đọc output của tầng trước —
**không được bỏ qua bước nào**.

### Tầng 1 — Khai thác dữ liệu từ SQL Server

```bash
python scripts/tang1_db_extractor.py
```

- Kết nối SQL Server, trích xuất 3 bảng (`cmt_oee_results`, `cmt_delay_results`, `fob_revenue`)
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

---

## 7. Liên hệ hỗ trợ

- **Quản lý dự án:** Đào Minh Trí (daominhtri2025@gmail.com)
- **Repository:** https://github.com/daominhtri2025-crypto/Hybrid_Causal_Forecasting_3A
