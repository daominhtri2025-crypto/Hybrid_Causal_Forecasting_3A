# Hybrid Causal Forecasting 3-A

> **Hệ thống dự báo nhân quả lai (Hybrid Causal Forecasting)** — kiến trúc
> 4 tầng kết hợp phân tích nhân quả kinh tế lượng (Granger, Johansen) với
> mô hình dự báo VECM, tối ưu hóa dự báo OEE và Doanh thu cho quyết định
> sản xuất chiến lược.

---

## 1. Tổng quan Dự án (Project Overview)

### 1.1. Bài toán

Trong quản trị sản xuất, các chỉ số hiệu suất — **OEE** (Overall Equipment
Effectiveness), **tỷ lệ trễ đơn hàng** (Delay Rate), **doanh thu** (Revenue),
và **khối lượng đơn hàng** (Order Volume) — có mối quan hệ nhân quả phức tạp
và biến thiên theo thời gian. Dự báo chính xác các chỉ số này giúp nhà quản lý:

- Lên kế hoạch sản xuất chủ động, giảm tồn kho và thời gian chờ.
- Phát hiện sớm tín hiệu suy giảm OEE trước khi ảnh hưởng đến giao hàng.
- Ước lượng doanh thu kỳ vọng dựa trên dữ liệu sản xuất thực tế.

### 1.2. Mục tiêu hệ thống

1. **Trích xuất** dữ liệu sản xuất từ SQL Server với cơ chế snapshot bất biến.
2. **Đồng bộ** trục thời gian, triệt tiêu look-ahead bias.
3. **Kiểm định** mối quan hệ nhân quả và đồng tích hợp giữa các biến bằng
   bộ công cụ kinh tế lượng chuẩn.
4. **Dự báo** 4 tuần tiếp theo kèm khoảng tin cậy 95% bằng mô hình VECM.

### 1.3. Kiến trúc 4 tầng

```
SQL Server (qtdn_datamining)
    │
    ▼
┌──────────────────────────────────────────────────────────┐
│  TẦNG 1 — Raw Data Extraction                           │
│  tang1_db_extractor.py                                   │
│  Snapshot đồng thời 1 mốc thời gian, SHA-256, MANIFEST  │
└──────────────────────────────────────────────────────────┘
    │
    ▼  data/raw/snapshot_YYYYMMDD_HHMM/*.csv  (BẤT BIẾN)
    │
┌──────────────────────────────────────────────────────────┐
│  TẦNG 2 — Data Re-engineering (Phase 0)                  │
│  phase0_data_reengineering.py                            │
│  Chống look-ahead bias, weighting, nội suy NaN (limit=2)│
└──────────────────────────────────────────────────────────┘
    │
    ▼  data/processed/causal_weekly_dataset.csv
    │
    ⏸  ĐIỂM DỪNG XÁC NHẬN 1 — duyệt dataset tuần
    │
┌──────────────────────────────────────────────────────────┐
│  TẦNG 3 — Econometrics (Phase 1 → 3b)                    │
│  ADF/KPSS → Granger → Johansen → Toda-Yamamoto          │
│  Xác định d(i), rank r, route VECM/VAR                   │
└──────────────────────────────────────────────────────────┘
    │
    ⏸  ĐIỂM DỪNG XÁC NHẬN 2 — duyệt route VECM/VAR
    │
┌──────────────────────────────────────────────────────────┐
│  TẦNG 4 — VECM Forecasting                              │
│  tang4_vecm_forecasting.py                               │
│  Dự báo h=4 tuần, CI 95% (IRF/MA), cointegrating eqs    │
└──────────────────────────────────────────────────────────┘
    │
    ▼  reports/forecasts/vecm_forecast.csv
       reports/tang4_vecm_results.json
```

---

## 2. Chi tiết Quy trình & Thuật toán (Pipeline & Algorithms)

### 2.1. Tầng 1 — Raw Data Extraction (`tang1_db_extractor.py`)

**Nguyên tắc cốt lõi: Bất biến dữ liệu gốc (Data Immutability)**

Mọi file trong `data/raw/` là **BẤT BIẾN** — không script nào được phép
chỉnh sửa, ghi đè, hay xóa. Đây là "nguồn chân lý" (single source of truth)
của dữ liệu gốc.

| Cơ chế | Mô tả |
|--------|-------|
| **Khóa mốc thời gian (Snapshot Time)** | Một biến `snapshot_time` được chốt **một lần duy nhất** khi script bắt đầu. Cả 3 truy vấn SQL (`cmt_oee_results`, `cmt_delay_results`, `fob_revenue`) đều lọc `WHERE timestamp <= snapshot_time` — đảm bảo dữ liệu phản ánh cùng một lát cắt thời gian, tránh lệch `OrderNo` giữa các file. |
| **Toàn vẹn dữ liệu (SHA-256)** | Mỗi file CSV được tính checksum SHA-256 ngay sau khi ghi. Checksum, số dòng, và timestamp trích xuất được lưu vào `data/raw/MANIFEST.md` — cho phép kiểm tra xem file có bị thay đổi sau khi snapshot. |
| **Kiểm tra chéo OrderNo** | Tỷ lệ khớp `OrderNo` giữa 3 file được tính tại thời điểm snapshot. Nếu < 95% → ghi WARNING. |

### 2.2. Tầng 2 — Data Re-engineering (`phase0_data_reengineering.py`)

Tầng này giải quyết 3 vấn đề kỹ thuật quan trọng:

#### a) Triệt tiêu Look-ahead Bias

> **Look-ahead bias** xảy ra khi gán một giá trị "biết sau" vào một thời
> điểm "trước khi biết" — ví dụ: gán OEE (tính từ `RealQty` — chỉ biết khi
> đơn hàng hoàn thành) theo `PlannedShipmentDate` (ngày dự kiến, thường sớm
> hơn ngày hoàn thành thực).

**Giải pháp:** Đồng bộ trục thời gian bằng cách gán tuần theo **ngày biết
được** (*point-in-time correctness*):

| Chỉ số | Mốc thời gian gán tuần | Lý do |
|--------|------------------------|-------|
| OEE_Score | `ActualEndDate` | OEE chỉ tồn tại khi đơn hàng hoàn thành |
| DelayRate | `ActualEndDate` | Trễ/đúng hạn chỉ biết khi đã giao |
| Revenue | `ShipmentDate` | Doanh thu ghi nhận tại thời điểm xuất kho |

Đơn hàng chưa có `ActualEndDate` bị **loại khỏi tính toán** — không gán 0
hay NaN giả.

#### b) Nội suy hai chiều có giới hạn (`limit=2`)

| Loại biến | Phương pháp | Lý do |
|-----------|-------------|-------|
| Tỷ lệ (OEE, DelayRate) | `interpolate(method='linear', limit=2)` | Tỷ lệ cần có mẫu mới có ý nghĩa — nội suy tối đa 2 tuần liên tiếp, vượt ngưỡng thì giữ NaN |
| Tổng/Đếm (Revenue, OrderVolume) | `fillna(0)` | Giá trị 0 có ý nghĩa thật: "không có giao dịch trong tuần đó" |

Mỗi dòng được đánh dấu `is_interpolated_oee`, `is_interpolated_delay` để
Tầng 3 thực hiện kiểm định độ nhạy (sensitivity analysis).

#### c) Trọng số sản lượng (Weighted Average)

Trung bình tuần dùng `np.average(OEE_Score, weights=RealQty)` — phản ánh
khối lượng sản xuất thực tế. Fallback về `mean()` khi tổng trọng số = 0
(tránh chia cho 0).

### 2.3. Tầng 3 — Econometrics (Phase 1 → 3b)

Chuỗi 4 kiểm định kinh tế lượng, mỗi Phase đọc kết quả từ Phase trước qua
file JSON — **không hard-code** tham số.

#### Phase 1: Kiểm định tính dừng (ADF + KPSS)

**Phương pháp xác nhận kép** (Pfaff 2008): chạy song song 2 kiểm định có giả
thuyết H₀ **ngược nhau** để giảm rủi ro sai lầm loại I/II.

| Kiểm định | H₀ | H₁ | Bác bỏ H₀ nghĩa là |
|-----------|----|----|---------------------|
| ADF (Augmented Dickey-Fuller) | Có nghiệm đơn vị (non-stationary) | Stationary | Chuỗi dừng |
| KPSS (Kwiatkowski-Phillips-Schmidt-Shin) | Stationary | Non-stationary | Chuỗi không dừng |

**Ma trận quyết định:**

| ADF bác bỏ? | KPSS giữ? | Kết luận |
|-------------|-----------|----------|
| Có | Có | **Dừng** (cả 2 đồng thuận) |
| Không | Không | **Không dừng** (cả 2 đồng thuận) |
| Có | Không | Mâu thuẫn → coi là dừng (bảo thủ) |
| Không | Có | Không rõ ràng → coi là không dừng (an toàn) |

Bậc tích hợp d(i) được xác định bằng sai phân tuần tự (level → 1st diff →
2nd diff) cho đến khi chuỗi dừng.

**Kết quả trên dữ liệu hiện tại:**

| Biến | d(i) | Ý nghĩa |
|------|------|---------|
| OEE_Score | 1 | I(1) — cần sai phân 1 lần |
| DelayRate | 0 | I(0) — dừng tại mức gốc |
| Revenue | 0 | I(0) — dừng tại mức gốc |
| OrderVolume | 0 | I(0) — dừng tại mức gốc |

→ **d_max = 1** (bậc tích hợp cao nhất, dùng cho Toda-Yamamoto).

#### Phase 2: Granger Causality

Kiểm định pairwise Granger cho tất cả 12 cặp có hướng (4 biến × 3 biến
đích). Sử dụng F-test (chính xác hơn χ² cho mẫu nhỏ), lag tối ưu theo AIC.

**Kết quả:** 0/12 cặp có ý nghĩa thống kê (p < 0.05) — null finding hợp lệ
do mẫu nhỏ (N=10, power thống kê thấp).

#### Phase 3: Johansen Cointegration

Kiểm định tuần tự (sequential testing) xác định rank đồng tích hợp r, dùng
`det_order=1` (unrestricted constant — Lütkepohl 2005).

| Thống kê | Rank xác định |
|----------|---------------|
| **Trace** (Johansen & Juselius 1990) | **r = 2** |
| Max-Eigenvalue | r = 1 |

Khi Trace và Max-Eigen không đồng thuận → **ưu tiên Trace** theo khuyến nghị
của Johansen & Juselius (1990), vì Trace test có power tổng thể cao hơn trong
hệ thống nhiều biến.

**Kết luận: Rank r = 2** → Route **VECM** (0 < r < n).

#### Phase 3b: Toda-Yamamoto (Cross-check)

Kiểm định nhân quả độc lập trên **mức gốc** (levels) — không yêu cầu
pre-testing d(i). Dùng VAR(k + d_max) augmented, Wald test trên k lag đầu
tiên.

**Kết quả:** 0/12 cặp có ý nghĩa, **12/12 đồng thuận** với Granger (100%
agreement) — xác nhận tính nhất quán của kết luận.

### 2.4. Tầng 4 — VECM Forecasting (`tang4_vecm_forecasting.py`)

#### Cấu hình mô hình

```
VECM(k_ar_diff=0, coint_rank=2, deterministic='co')
```

| Tham số | Giá trị | Nguồn gốc |
|---------|---------|------------|
| `coint_rank` | 2 | Phase 3 Johansen Trace test |
| `k_ar_diff` | 0 | Phase 3 JSON (VAR lag p=1 → VECM k=p−1=0) |
| `deterministic` | `'co'` | Unrestricted constant (khớp Phase 3 det_order=1) |

**Tại sao k_ar_diff = 0 thay vì 1?**

Với cỡ mẫu N=10, k_ar_diff=1 cần 7 tham số/phương trình nhưng chỉ có 8
quan sát hữu hiệu → **DoF = 1** → overfitting nghiêm trọng (dự báo bùng nổ
lên hàng triệu). k_ar_diff=0 chỉ cần 3 tham số/phương trình → **DoF = 6** →
ước lượng ổn định, dự báo hợp lệ.

#### Phương trình đồng tích hợp (Cointegrating Equations)

Mô hình VECM phân tách thành 2 thành phần:

**Quan hệ dài hạn** — `β'·y_{t-1} ≈ 0` (cân bằng):

| | OEE_Score | DelayRate | Revenue | OrderVolume |
|---|---|---|---|---|
| **CE1** | +1.000 | ≈ 0 | −0.000001 | **+0.091** |
| **CE2** | ≈ 0 | +1.000 | +0.000007 | **−0.659** |

**Diễn giải:**
- **CE1**: OEE ↔ OrderVolume có quan hệ dài hạn dương — khi khối lượng
  đơn hàng tăng, OEE cũng tăng (quy mô sản xuất lớn giúp tận dụng thiết bị
  hiệu quả hơn).
- **CE2**: DelayRate ↔ OrderVolume có quan hệ dài hạn nghịch — khi khối
  lượng đơn hàng tăng, tỷ lệ trễ giảm trong dài hạn (hệ thống tối ưu
  hóa lịch trình khi có nhiều đơn).

**Tốc độ điều chỉnh (α):** OEE_Score có α₁ = −1.13 (error correcting mạnh —
tự điều chỉnh nhanh về cân bằng khi lệch), OrderVolume có α₂ = −2.35.

#### Khoảng tin cậy

Tính bằng phương pháp **IRF/MA** (Lütkepohl 2005):

$$\text{Var}(e_{T+h|T}) = \sum_{i=0}^{h-1} \Psi_i \cdot \Sigma_u \cdot \Psi_i'$$

trong đó Ψᵢ là ma trận hệ số Moving Average (trích từ Impulse Response
Function), Σᵤ là ma trận hiệp phương sai innovation.

#### Kết quả dự báo

| Tuần | OEE_Score | DelayRate | Revenue | OrderVolume |
|------|-----------|-----------|---------|-------------|
| 2026-08-24 (T+1) | 0.857 [0.831, 0.884] | 0.307 [0.102, 0.512] | 555K [310K, 801K] | 4.0 [1.7, 6.2] |
| 2026-08-31 (T+2) | 0.838 [0.796, 0.880] | 0.263 [−0.030, 0.555] | 316K [−21K, 653K] | 2.9 [−0.2, 6.0] |
| 2026-09-07 (T+3) | 0.874 [0.828, 0.920] | 0.230 [−0.127, 0.587] | 561K [111K, 1,011K] | 4.2 [0.2, 8.1] |
| 2026-09-14 (T+4) | 0.846 [0.795, 0.897] | 0.192 [−0.222, 0.605] | 431K [−65K, 927K] | 3.5 [−1.0, 8.0] |

---

## 3. Cảnh báo Khoa học (Scientific Disclaimer)

### 3.1. Giới hạn cỡ mẫu

Tập dữ liệu hiện tại chỉ có **N = 10 tuần** quan sát — thấp hơn đáng kể so
với ngưỡng khuyến nghị tối thiểu (N ≥ 30) cho kiểm định kinh tế lượng chuỗi
thời gian. Hệ quả:

| Ảnh hưởng | Mô tả |
|-----------|-------|
| **Power thống kê thấp** | Các kiểm định Granger và Toda-Yamamoto cho kết quả 0/12 cặp có ý nghĩa — đây có thể là null finding thật HOẶC do không đủ mẫu để phát hiện quan hệ nhân quả yếu. |
| **Khoảng tin cậy mở rộng** | CI 95% mở rộng đáng kể ở tầm xa (T+3, T+4) — đặc biệt Revenue và OrderVolume có CI bao gồm giá trị âm (vô nghĩa kinh tế). Đây là hệ quả tự nhiên, không phải lỗi mô hình. |
| **Sensitivity analysis hạn chế** | Sau khi loại 4 tuần nội suy, chỉ còn 6 quan sát — quá ít cho Johansen hay Granger, nên kết quả sensitivity cần diễn giải thận trọng. |
| **Bậc tích hợp nhạy cảm** | d(OEE_Score) thay đổi từ 1 (dataset đầy đủ) sang 0 (loại tuần nội suy), cho thấy kết luận tính dừng **có thể phụ thuộc** vào bước nội suy ở Tầng 2. |

### 3.2. Khuyến nghị

- **Khi N ≥ 30:** chạy lại toàn bộ pipeline (Tầng 3 → Tầng 4) — các kiểm
  định sẽ có power đủ mạnh, CI thu hẹp đáng kể, và kết luận nhân quả đáng
  tin cậy hơn.
- **Khi N ≥ 50:** có thể bổ sung mô hình LSTM (Phase 4) và ensemble (Phase
  6) để so sánh hiệu quả giữa phương pháp kinh tế lượng và deep learning.
- Kết quả "null finding" (không có ý nghĩa thống kê) là **kết quả khoa học
  hợp lệ** — dự án tuân thủ nghiêm ngặt nguyên tắc không p-hacking.

---

## 4. Hướng dẫn Vận hành (How to Run)

### 4.1. Yêu cầu

```bash
pip install -r requirements.txt
```

Các thư viện chính: `pandas`, `numpy`, `statsmodels`, `scipy`.

### 4.2. Chạy pipeline tuần tự

```bash
# ─── Tầng 1: Trích xuất dữ liệu từ SQL Server ───
# (Chỉ chạy trên máy có kết nối SQL Server — không chạy trên sandbox)
python scripts/tang1_db_extractor.py

# ─── Tầng 2: Tái cấu trúc dữ liệu thô → dataset tuần ───
python -c "from scripts.phase0_data_reengineering import run_phase0; run_phase0()"

#   ⏸ ĐIỂM DỪNG 1: Kiểm tra data/processed/causal_weekly_dataset.csv
#     → Xác nhận số tuần, khoảng thời gian, tỷ lệ tuần nội suy.

# ─── Tầng 3: Kiểm định kinh tế lượng (chạy theo thứ tự) ───
python scripts/phase1_stationarity.py
python scripts/phase2_granger_causality.py
python scripts/phase3_cointegration.py
python scripts/phase3b_toda_yamamoto.py

#   ⏸ ĐIỂM DỪNG 2: Kiểm tra reports/phase3_cointegration.json
#     → Xác nhận rank r, route (VECM/VAR) trước khi dự báo.

# ─── Tầng 4: Dự báo VECM ───
python scripts/tang4_vecm_forecasting.py
```

### 4.3. Output chính

| File | Nội dung |
|------|----------|
| `data/processed/causal_weekly_dataset.csv` | Dataset tuần đã clean (4 biến + cột `is_interpolated`) |
| `reports/phase1_stationarity.json` | Bậc tích hợp d(i), thống kê ADF/KPSS |
| `reports/phase2_granger_causality.json` | Kết quả Granger pairwise (12 cặp) |
| `reports/phase3_cointegration.json` | Rank r, route VECM/VAR, eigenvalues |
| `reports/phase3b_toda_yamamoto.json` | Toda-Yamamoto + cross-check với Granger |
| `reports/tang4_vecm_results.json` | Hệ số β, α, Γ, σᵤ, diagnostics |
| `reports/forecasts/vecm_forecast.csv` | Dự báo 4 tuần kèm CI 95% |

### 4.4. Cập nhật mô hình khi có dữ liệu mới

1. Chạy Tầng 1 để tạo snapshot mới.
2. Chạy lại **toàn bộ** pipeline từ Tầng 2 (Phase 0) — không chạy riêng
   Tầng 4, vì bậc tích hợp d(i) và rank r có thể thay đổi khi cỡ mẫu tăng.
3. Xác nhận tại 2 điểm dừng trước khi tiến sang bước tiếp theo.

---

## 5. Cấu trúc Thư mục

```
Hybrid_Causal_Forecasting_3A/
├── README.md                          # File này
├── CLAUDE.md                          # Quy tắc quản trị dự án (single source of truth)
├── skill.md                           # Phân vai trò Agent + hợp đồng I/O
├── requirements.txt
│
├── data/
│   ├── raw/                           # BẤT BIẾN — snapshot thô từ SQL Server
│   │   └── snapshot_YYYYMMDD_HHMM/
│   └── processed/                     # Output đã xử lý
│       └── causal_weekly_dataset.csv
│
├── scripts/
│   ├── utils.py                       # Logger dùng chung (get_logger)
│   ├── tang1_db_extractor.py          # Tầng 1: DB extraction
│   ├── phase0_data_reengineering.py   # Tầng 2: Data re-engineering
│   ├── phase1_stationarity.py         # Tầng 3: ADF + KPSS
│   ├── phase2_granger_causality.py    # Tầng 3: Granger causality
│   ├── phase3_cointegration.py        # Tầng 3: Johansen cointegration
│   ├── phase3b_toda_yamamoto.py       # Tầng 3: Toda-Yamamoto cross-check
│   └── tang4_vecm_forecasting.py      # Tầng 4: VECM forecasting
│
├── reports/
│   ├── phase1_stationarity.json
│   ├── phase2_granger_causality.json
│   ├── phase3_cointegration.json
│   ├── phase3b_toda_yamamoto.json
│   ├── tang4_vecm_results.json
│   ├── forecasts/
│   │   └── vecm_forecast.csv
│   └── logs/                          # Log pipeline (không version control)
│
├── models/                            # Trọng số mô hình (.pt)
└── docs/
    └── ARCHITECTURE_4_tang.md         # Tài liệu kiến trúc chi tiết
```

---

## 6. Tài liệu Tham khảo

- Johansen, S. (1995). *Likelihood-Based Inference in Cointegrated Vector
  Autoregressive Models*. Oxford University Press.
- Johansen, S. & Juselius, K. (1990). Maximum likelihood estimation and
  inference on cointegration. *Oxford Bulletin of Economics and Statistics*,
  52(2), 169–210.
- Lütkepohl, H. (2005). *New Introduction to Multiple Time Series Analysis*.
  Springer.
- Pfaff, B. (2008). *Analysis of Integrated and Cointegrated Time Series
  with R*. 2nd ed., Springer.
- Toda, H. Y. & Yamamoto, T. (1995). Statistical inference in vector
  autoregressions with possibly integrated processes. *Journal of
  Econometrics*, 66(1–2), 225–250.
