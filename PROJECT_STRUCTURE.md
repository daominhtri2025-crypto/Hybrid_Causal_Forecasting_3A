# PROJECT_STRUCTURE.md — Bản đồ dự án Phương án 3-A

> **Mục đích:** Giúp thành viên mới (hoặc chính tác giả trong tương lai) nắm
> bắt nhanh toàn bộ cấu trúc, chức năng, và luồng dữ liệu của dự án mà không
> cần đọc từng file.
>
> **Cập nhật lần cuối:** 2026-08-11

---

## 1. Tree View — Cấu trúc thư mục tổng quan

```
Hybrid_Causal_Forecasting_3A/
│
├── main_pipeline.py                  # Orchestrator — điều phối toàn bộ pipeline
├── requirements.txt                  # Danh sách thư viện Python
├── .gitignore                        # Quy tắc loại trừ Git
│
├── CLAUDE.md                         # Quy tắc quản trị dự án (single source of truth)
├── skill.md                          # Phân vai trò Agent + hợp đồng I/O giữa các Tầng
├── README.md                         # Giới thiệu tổng quan dự án
├── PROJECT_STRUCTURE.md              # File này — bản đồ dự án
├── SETUP_GUIDE.md                    # Hướng dẫn cài đặt & chạy pipeline
├── DEMO_GUIDE.md                     # Kịch bản demo 30-38 phút
├── INNOVATIONS.md                    # Tổng hợp điểm mới so với văn khoa
├── MATH_AND_ALGORITHMS.md            # Nền tảng toán học & thuật toán
│
├── scripts/                          # Toàn bộ mã nguồn xử lý
│   ├── __init__.py
│   ├── utils.py                      # Tiện ích dùng chung (get_logger)
│   ├── tang1_db_extractor.py         # Tầng 1 — Trích xuất SQL Server
│   ├── diagnostic_sql_check.py       # Kiểm tra cấu trúc bảng NAV trước pipeline
│   ├── phase0_data_reengineering.py  # Tầng 2 — Xử lý dữ liệu thô → dataset tuần
│   ├── phase0_synthetic_pipeline.py  # Tầng 2 — Tạo dataset tổng hợp (hybrid synthetic)
│   ├── phase1_stationarity.py        # Tầng 3 — Kiểm định tính dừng (ADF+KPSS+ZA)
│   ├── phase2_granger_causality.py   # Tầng 3 — Nhân quả Granger
│   ├── phase3_cointegration.py       # Tầng 3 — Đồng tích hợp Johansen
│   ├── phase3b_toda_yamamoto.py      # Tầng 3 — Kiểm chứng chéo Toda-Yamamoto
│   ├── tang4_vecm_forecasting.py     # Tầng 4 — Dự báo VECM/VAR + khoảng tin cậy
│   └── phase5_visualization.py       # Tầng 4 — Trực quan hóa IRF & FEVD
│
├── data/
│   ├── raw/                          # DỮ LIỆU THÔ — BẤT BIẾN, CHỈ ĐỌC
│   │   └── snapshot_20260801_0900/
│   │       ├── cmt_oee_results.csv
│   │       ├── cmt_delay_results.csv
│   │       └── fob_revenue.csv
│   └── processed/                    # Kết quả đã xử lý
│       ├── causal_weekly_dataset.csv
│       └── figures/
│           ├── fevd_delayrate_decomposition.png
│           └── irf_delayrate_response.png
│
├── models/                           # Trọng số mô hình (.pt) — hiện chưa có
│
├── reports/                          # Kết quả từng Phase (JSON, machine-readable)
│   ├── phase0_synthetic_metadata.json
│   ├── phase1_stationarity.json
│   ├── phase2_granger_causality.json
│   ├── phase3_cointegration.json
│   ├── phase3b_toda_yamamoto.json
│   ├── phase5_irf_fevd_results.json
│   ├── tang4_vecm_results.json
│   ├── forecasts/
│   │   └── vecm_forecast.csv
│   ├── logs/                         # Log pipeline (không version control)
│   │   ├── phase_transitions.jsonl
│   │   └── pipeline_YYYYMMDD_HHMM.log
│   └── qa/                           # Báo cáo QA (dự phòng)
│
└── docs/
    ├── ARCHITECTURE_4_tang.md        # Kiến trúc 4 tầng chi tiết
    └── thesis_draft/
        └── chapter4_draft.md         # Bản thảo Chương 4 luận án
```

---

## 2. Orchestration & Core — Điều phối và cấu hình

| File | Chức năng |
|------|-----------|
| `main_pipeline.py` | **Orchestrator trung tâm.** Chạy tuần tự Phase 0 → 1 → 2 → 3 → 3b → 4 → 5, hỗ trợ `--resume-from` và `--stop-after` để chạy lại từ Phase bất kỳ mà không cần chạy lại toàn bộ. |
| `requirements.txt` | Danh sách thư viện Python cần cài đặt (`statsmodels`, `pandas`, `numpy`, `torch`, `matplotlib`, `scipy`, `pyodbc`). |
| `scripts/utils.py` | Cung cấp hàm `get_logger()` dùng chung cho toàn pipeline — ghi log đồng thời ra console và file `reports/logs/pipeline_YYYYMMDD_HHMM.log`, đảm bảo mọi Phase dùng cùng định dạng log. |
| `scripts/__init__.py` | Đánh dấu `scripts/` là Python package để các module import lẫn nhau. |
| `.gitignore` | Loại trừ `reports/logs/`, `__pycache__/`, `models/*.pt`, và các file tạm khỏi Git. |

---

## 3. Data Pipeline & Modeling — Luồng dữ liệu theo Phase

### Tầng 1 — Trích xuất dữ liệu (Database Layer)

| File | Chức năng | Input | Output |
|------|-----------|-------|--------|
| `scripts/tang1_db_extractor.py` | **Điểm truy cập SQL Server DUY NHẤT** của dự án. Kết nối NAV database, trích xuất bảng OEE/Delay/Revenue cùng một thời điểm (snapshot), ghi ra CSV kèm timestamp. | SQL Server (NAV tables) | `data/raw/snapshot_YYYYMMDD_HHMM/*.csv` |
| `scripts/diagnostic_sql_check.py` | Kiểm tra sơ bộ cấu trúc bảng NAV (tên cột, kiểu dữ liệu) trước khi chạy pipeline chính — phát hiện sớm lỗi schema. | SQL Server | Console output (không ghi file) |

### Tầng 2 — Kỹ thuật dữ liệu (Data Engineering)

| File | Chức năng | Input | Output |
|------|-----------|-------|--------|
| `scripts/phase0_data_reengineering.py` | **Phase 0.** Đọc 3 file CSV thô, merge theo `OrderNo`, gộp theo tuần (`W-MON`), áp dụng Forward-fill Strategy A (limit=4 tuần), tính trung bình có trọng số, chống look-ahead bias. Tạo cột `is_filled` đánh dấu tuần được nội suy. | `data/raw/snapshot_*/cmt_oee_results.csv`, `cmt_delay_results.csv`, `fob_revenue.csv` | `data/processed/causal_weekly_dataset.csv`, `reports/phase0_synthetic_metadata.json` |
| `scripts/phase0_synthetic_pipeline.py` | **Phase 0 (Hybrid Synthetic).** Tạo dataset tuần tổng hợp khi dữ liệu thực không đủ dài cho kiểm định chuỗi thời gian — dùng phân phối thống kê ước lượng từ dữ liệu thực để sinh mẫu bổ sung. | `data/raw/snapshot_*/*.csv` | `data/processed/causal_weekly_dataset.csv`, `reports/phase0_synthetic_metadata.json` |

### Tầng 3 — Kiểm định kinh tế lượng (Econometric Testing)

| File | Chức năng | Input | Output |
|------|-----------|-------|--------|
| `scripts/phase1_stationarity.py` | **Phase 1.** Kiểm định tính dừng bằng chiến lược kép ADF + KPSS (Pfaff 2008). Khi hai kiểm định mâu thuẫn (Case 3), tự động chạy Zivot-Andrews (1992) làm tiebreaker. Xác định bậc tích hợp `d(i)` cho từng biến. | `data/processed/causal_weekly_dataset.csv` | `reports/phase1_stationarity.json` |
| `scripts/phase2_granger_causality.py` | **Phase 2.** Kiểm định nhân quả Granger theo cặp trên chuỗi đã sai phân (bậc `d(i)` lấy từ Phase 1). Xác định hướng nhân quả giữa OEE, DelayRate, Revenue. | `data/processed/causal_weekly_dataset.csv`, `reports/phase1_stationarity.json` | `reports/phase2_granger_causality.json` |
| `scripts/phase3_cointegration.py` | **Phase 3.** Kiểm định đồng tích hợp Johansen (Trace + Max-Eigenvalue). Xác định hạng đồng tích hợp `r` — quyết định dùng VECM (r ≥ 1) hay VAR (r = 0). **Điểm dừng xác nhận** — chờ Anh Béo xác nhận route trước khi Tầng 4 chạy. | `data/processed/causal_weekly_dataset.csv`, `reports/phase1_stationarity.json` | `reports/phase3_cointegration.json` |
| `scripts/phase3b_toda_yamamoto.py` | **Phase 3b.** Kiểm chứng chéo nhân quả bằng Toda-Yamamoto — chạy trên chuỗi gốc (levels), không cần sai phân, tránh mất thông tin dài hạn. So sánh với kết quả Granger ở Phase 2. | `data/processed/causal_weekly_dataset.csv`, `reports/phase1_stationarity.json` | `reports/phase3b_toda_yamamoto.json` |

### Tầng 4 — Dự báo & Trực quan hóa (Forecasting & Visualization)

| File | Chức năng | Input | Output |
|------|-----------|-------|--------|
| `scripts/tang4_vecm_forecasting.py` | **Tầng 4 — Dự báo.** Đọc route (VECM/VAR) và tham số (`r`, `d(i)`, lag `p`) từ JSON Phase 3. Ước lượng mô hình, dự báo 4 tuần với khoảng tin cậy 95%. Tự động clamping eigenvalue khi ma trận hiệp phương sai suy biến (self-healing). | `data/processed/causal_weekly_dataset.csv`, `reports/phase3_cointegration.json` | `reports/tang4_vecm_results.json`, `reports/forecasts/vecm_forecast.csv` |
| `scripts/phase5_visualization.py` | **Phase 5 — Trực quan hóa.** Tạo biểu đồ IRF (Impulse Response Function) và FEVD (Forecast Error Variance Decomposition) cho Chương 4 luận án. | `reports/tang4_vecm_results.json`, `data/processed/causal_weekly_dataset.csv` | `data/processed/figures/irf_*.png`, `data/processed/figures/fevd_*.png`, `reports/phase5_irf_fevd_results.json` |

---

## 4. Documentation — Hệ thống tài liệu

| File | Chức năng |
|------|-----------|
| `CLAUDE.md` | **Nguồn chân lý duy nhất** cho quy tắc cấu trúc, xử lý dữ liệu, và coding convention. Mọi script phải tuân thủ file này. |
| `skill.md` | Định nghĩa vai trò Agent (Claude) theo từng Tầng, hợp đồng input/output giữa các Phase, và 2 điểm dừng bắt buộc chờ xác nhận. |
| `README.md` | Giới thiệu tổng quan dự án: bối cảnh nghiên cứu, mục tiêu, và hướng dẫn bắt đầu nhanh. |
| `PROJECT_STRUCTURE.md` | File này — bản đồ dự án giúp nắm bắt nhanh cấu trúc và chức năng từng file. |
| `SETUP_GUIDE.md` | Hướng dẫn cài đặt môi trường (Python, SQL Server, thư viện), cách chạy pipeline, và CLI flags (`--resume-from`, `--stop-after`). |
| `DEMO_GUIDE.md` | Kịch bản demo 30-38 phút cho hội đồng/seminar, bao gồm fault tolerance và self-healing eigenvalue clamping. |
| `INNOVATIONS.md` | Tổng hợp 6 điểm mới/khác biệt so với văn khoa hiện có — dùng để trả lời câu hỏi phản biện. |
| `MATH_AND_ALGORITHMS.md` | Nền tảng toán học chi tiết: công thức ADF, KPSS, Zivot-Andrews, Johansen, Granger, forward-fill, eigenvalue clamping. |
| `docs/ARCHITECTURE_4_tang.md` | Kiến trúc 4 tầng chi tiết với sơ đồ luồng dữ liệu, trách nhiệm từng tầng, và cơ chế JSON contract. |
| `docs/thesis_draft/chapter4_draft.md` | Bản thảo Chương 4 luận án — phương pháp nghiên cứu (academic voice), sẵn sàng đưa vào file `.docx`. |

---

## 5. Outputs & Logs — Kết quả và nhật ký

### 5.1. JSON Reports (`reports/`)

Mỗi Phase ghi kết quả ra file JSON — đây là **hợp đồng dữ liệu** (JSON contract) giữa các Phase. Phase sau đọc tham số từ JSON của Phase trước, không hard-code.

| File | Nội dung |
|------|----------|
| `phase0_synthetic_metadata.json` | Metadata dataset: số tuần, khoảng thời gian, số tuần forward-filled, phương pháp tạo dữ liệu. |
| `phase1_stationarity.json` | Kết quả ADF/KPSS/ZA cho từng biến: p-value, bậc tích hợp `d(i)`, kết luận (stationary/non-stationary/contradictory). |
| `phase2_granger_causality.json` | Ma trận nhân quả Granger: hướng, p-value, lag tối ưu cho từng cặp biến. |
| `phase3_cointegration.json` | Kết quả Johansen: hạng `r`, trace/max-eigenvalue statistics, route quyết định (VECM hay VAR). |
| `phase3b_toda_yamamoto.json` | Kết quả Toda-Yamamoto: so sánh chéo với Granger, Wald statistic, p-value. |
| `tang4_vecm_results.json` | Tham số mô hình VECM/VAR đã ước lượng, thống kê chẩn đoán, eigenvalue clamping log (nếu có). |
| `phase5_irf_fevd_results.json` | Dữ liệu IRF/FEVD dạng số — dùng để tái tạo biểu đồ hoặc phân tích thêm. |

### 5.2. Forecasts (`reports/forecasts/`)

| File | Nội dung |
|------|----------|
| `vecm_forecast.csv` | Dự báo 4 tuần tiếp theo cho OEE, DelayRate, Revenue — kèm khoảng tin cậy 95% (CI_lower, CI_upper). |

### 5.3. Figures (`data/processed/figures/`)

| File | Nội dung |
|------|----------|
| `irf_delayrate_response.png` | Biểu đồ Impulse Response: phản ứng của DelayRate khi OEE/Revenue chịu cú sốc 1 độ lệch chuẩn. |
| `fevd_delayrate_decomposition.png` | Biểu đồ Forecast Error Variance Decomposition: tỷ lệ phương sai dự báo DelayRate được giải thích bởi từng biến theo thời gian. |

### 5.4. Logs (`reports/logs/`)

| File | Nội dung |
|------|----------|
| `pipeline_YYYYMMDD_HHMM.log` | Log đầy đủ của mỗi lần chạy pipeline — mỗi lần chạy tạo 1 file riêng, không ghi đè. Dùng để tra cứu lỗi và so sánh kết quả giữa các lần chạy. |
| `phase_transitions.jsonl` | Nhật ký chuyển tiếp Phase (JSONL, 1 dòng/transition): Phase nào chạy, Phase nào bỏ qua (skipped), thời gian mỗi Phase. |

---

## 6. Luồng dữ liệu tổng quan (Data Flow)

```
SQL Server (NAV)
      │
      ▼
 ┌─────────────────┐
 │  tang1_db_       │    data/raw/snapshot_YYYYMMDD_HHMM/
 │  extractor.py    │───►  cmt_oee_results.csv
 │  (Tầng 1)        │      cmt_delay_results.csv
 └─────────────────┘      fob_revenue.csv
                               │  (BẤT BIẾN — CHỈ ĐỌC)
                               ▼
                    ┌─────────────────────┐
                    │  phase0_data_        │    data/processed/
                    │  reengineering.py    │───► causal_weekly_dataset.csv
                    │  (Tầng 2 — Phase 0)  │    reports/phase0_*.json
                    └─────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
     ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
     │ phase1_      │ │ phase2_      │ │ phase3_      │
     │ stationarity │ │ granger_     │ │ cointegration│
     │ (Phase 1)    │ │ causality    │ │ (Phase 3)    │
     │              │ │ (Phase 2)    │ │              │
     └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
            │                │                │
            ▼                ▼                ▼
     phase1_*.json    phase2_*.json    phase3_*.json
                                              │
                               ┌──────────────┤
                               ▼              ▼
                    ┌──────────────┐  ┌──────────────────┐
                    │ phase3b_     │  │ tang4_vecm_      │
                    │ toda_yamamoto│  │ forecasting.py   │
                    │ (Phase 3b)   │  │ (Tầng 4)         │
                    └──────────────┘  └────────┬─────────┘
                                               │
                                               ▼
                                    tang4_vecm_results.json
                                    forecasts/vecm_forecast.csv
                                               │
                                               ▼
                                    ┌──────────────────┐
                                    │ phase5_          │
                                    │ visualization.py │
                                    │ (Phase 5)        │
                                    └────────┬─────────┘
                                             │
                                             ▼
                                    figures/irf_*.png
                                    figures/fevd_*.png
                                    phase5_*.json
```

---

## 7. Quy tắc quan trọng cần nhớ

1. **`data/raw/` là BẤT BIẾN** — không script nào được ghi đè, sửa, hoặc xóa file trong thư mục này.
2. **Chỉ `tang1_db_extractor.py` được kết nối SQL Server** — không script nào khác ở Tầng 2–4 được mở kết nối database.
3. **Không hard-code tham số** — mọi tham số thống kê (`d(i)`, `r`, lag `p`) phải đọc từ JSON của Phase trước đó.
4. **Comment tiếng Việt bắt buộc** — mọi file `.py` phải có docstring đầu file và comment tiếng Việt trước mỗi khối logic quan trọng.
5. **Logging bằng module `logging`** — cấm `print()` trong scripts pipeline. Dùng `get_logger()` từ `scripts/utils.py`.
6. **2 điểm dừng xác nhận**: sau Phase 0 (dataset hợp lệ?) và sau Phase 3 (route VECM/VAR?).

> Chi tiết đầy đủ: xem `CLAUDE.md` (quy tắc quản trị) và `skill.md` (phân vai trò Agent).
