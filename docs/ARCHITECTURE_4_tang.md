# Kiến trúc 4 tầng — Phương án 3-A (Rebuild)

**Trạng thái:** Đã duyệt (Anh Béo, phiên làm việc rebuild toàn bộ pipeline)
**Phạm vi:** Mô tả thiết kế luồng dữ liệu từ SQL Server đến kết quả dự báo cuối
cùng. Đây là tài liệu THIẾT KẾ (chưa có code) — dùng làm chuẩn đối chiếu khi
triển khai từng Phase ở các bước sau. Tuân thủ `CLAUDE.md` v2.0 và `skill.md`.

---

## Sơ đồ tổng thể

```
SQL Server
    │
    ▼
┌─────────────────────────────────────────────┐
│ Tầng 1 — DB Layer                            │
│ db_extractor.py: snapshot đồng thời 1 thời điểm │
└─────────────────────────────────────────────┘
    │
    ▼
data/raw/snapshot_YYYYMMDD_HHMM/  (bất biến)
    │
    ▼
┌─────────────────────────────────────────────┐
│ Tầng 2 — Phase 0                             │
│ Đồng bộ trục thời gian, weighting, nội suy NaN│
└─────────────────────────────────────────────┘
    │
    ▼
data/processed/causal_weekly_dataset.csv
    │
    ⏸  ĐIỂM DỪNG XÁC NHẬN 1 (duyệt dataset tuần)
    │
    ▼
┌─────────────────────────────────────────────┐
│ Tầng 3 — Econometrics                        │
│ Phase 1→3b: d(i), Granger, Johansen, Toda-Yamamoto │
└─────────────────────────────────────────────┘
    │
    ⏸  ĐIỂM DỪNG XÁC NHẬN 2 (duyệt route VECM/VAR)
    │
    ▼
┌─────────────────────────────────────────────┐
│ Tầng 4 — Routing & Forecast                  │
│ Phase 4 (LSTM) ‖ Phase 5 (VECM/VAR route) → Phase 6 │
│ main.py điều phối toàn bộ                    │
└─────────────────────────────────────────────┘
```

---

## Tầng 1: Khai thác & Giám sát Dữ liệu Gốc (`tang1_db_extractor.py`)

**Vấn đề cốt lõi cần giải quyết:** 3 nguồn dữ liệu (`cmt_oee_results`,
`cmt_delay_results`, `fob_revenue`) phải phản ánh **cùng một lát cắt thời
gian** của database — nếu không, `OrderNo` giữa các file sẽ lệch nhau do đơn
hàng mới phát sinh giữa các lần truy vấn.

**Thiết kế:**

1. Mở **một** kết nối SQL Server duy nhất, chốt biến `snapshot_time =
   datetime.now()` **một lần** ngay khi bắt đầu chạy — dùng chung cho cả 3
   truy vấn.
2. Chạy 3 truy vấn trong cùng một session, mỗi truy vấn lọc
   `WHERE <cột thời gian tạo/cập nhật bản ghi> <= snapshot_time` — đảm bảo dù
   truy vấn nào chạy sau vài giây cũng không "nhìn thấy" dữ liệu phát sinh
   sau mốc chốt.
3. Ghi nguyên trạng ra `data/raw/snapshot_YYYYMMDD_HHMM/*.csv` — **không
   transform gì**, kể cả đổi tên cột (tuân thủ nguyên tắc bất biến, `CLAUDE.md`
   mục 2).
4. Tự động cập nhật `data/raw/MANIFEST.md`: timestamp, checksum SHA-256, số
   dòng mỗi file, và **tỉ lệ khớp OrderNo giữa 3 file** tính ngay tại đây.
5. Logging (theo `CLAUDE.md` mục 7): INFO cho số dòng mỗi bảng; WARNING nếu
   bảng nào rỗng hoặc tỉ lệ khớp OrderNo < 95%; CRITICAL nếu kết nối SQL thất
   bại sau các lần thử lại.

**Output:** `data/raw/snapshot_YYYYMMDD_HHMM/{cmt_oee_results,cmt_delay_results,fob_revenue}.csv` + `data/raw/MANIFEST.md`.

---

## Tầng 2: Tái cấu trúc & Đồng bộ hóa (`phase0_data_reengineering.py`)

Tầng quan trọng nhất — nơi khắc phục 2 lỗi trọng yếu đã phát hiện ở Bước 3.

### 2.1. Triệt tiêu look-ahead bias — đổi mốc gán tuần

**Nguyên nhân gốc:** `OEE_Score` được tính từ `RealQty` — giá trị này chỉ
**biết được** sau khi đơn hàng hoàn thành (`ActualEndDate`). Bản cũ gán chỉ
số này vào tuần theo `PlannedShipmentDate` (ngày dự kiến, thường sớm hơn ngày
hoàn thành thực) — tức gán một giá trị "biết sau" vào một tuần "trước khi
biết", tạo look-ahead bias.

**Thiết kế mới:** gán `OEE_Score` và `IsDelayed` theo **`ActualEndDate`**
(thời điểm giá trị thực sự tồn tại), thay vì `PlannedShipmentDate`. `Revenue`
tiếp tục dùng `ShipmentDate` như cũ. Cả hai mốc giờ đều là "ngày biết được" —
nhất quán về triết lý *point-in-time correctness*.

Đơn hàng chưa có `ActualEndDate` (chưa hoàn thành tại thời điểm snapshot) bị
**loại khỏi tính toán tuần đó** — không gán 0 hay NaN giả cho một chỉ số
chưa tồn tại.

### 2.2. Lệch ca làm việc

**Quyết định (đã chốt với Anh Béo):** tạm thời áp dụng quy tắc **ngày dương
lịch chuẩn (00:00–23:59)** để xác định ngày/tuần của một bản ghi — chưa có
quy tắc ca làm việc thực tế từ nhà máy để áp dụng ngưỡng giờ khác.

**Cơ chế giám sát đi kèm:** với mọi bản ghi có timestamp (`ActualEndDate`,
`ShipmentDate`) nằm trong khung **±2 giờ quanh nửa đêm** (22:00–02:00), script
ghi **WARNING** (kèm `OrderNo` và timestamp cụ thể) — đây là các bản ghi có
rủi ro cao nhất bị gán sai ngày/tuần nếu ca làm việc thực tế không trùng ranh
giới dương lịch. Log này tích lũy theo từng lần chạy, cho phép Anh Béo review
định kỳ và quyết định có cần bổ sung quy tắc ca làm việc chính thức hay
không, mà không chặn tiến độ pipeline hiện tại.

### 2.3. Trọng số (Weighting)

Trung bình tuần chuyển từ `mean()` đơn giản sang
`np.average(OEE_Score, weights=RealQty)` — dùng `RealQty` (sản lượng thực)
làm trọng số, phản ánh đúng khối lượng công việc thực tế trong tuần thay vì
coi mọi đơn hàng ngang nhau bất kể quy mô.

### 2.4. Nội suy NaN

- `OEE` / `DelayRate` (là tỷ lệ, cần có mẫu mới có ý nghĩa): dùng
  `interpolate(limit=2)` — nội suy tối đa 2 tuần liên tiếp; vượt ngưỡng thì
  giữ NaN và ghi WARNING thay vì nội suy không giới hạn.
- `Revenue` / `OrderVolume` (là tổng/đếm, giá trị 0 có ý nghĩa thật — "không
  có giao dịch"): tiếp tục `fillna(0)`.
- Output có thêm cột **`is_interpolated`** (boolean, theo từng biến) để Tầng
  3 biết dòng nào là dữ liệu thật, dòng nào là nội suy — phục vụ kiểm định độ
  nhạy (xem mục Tầng 3).

**Output:** `data/processed/causal_weekly_dataset.csv` (có thêm cột `is_interpolated`).

---

## Tầng 3: Kinh tế lượng & Thống kê (Phase 1 → 3b)

Giữ nguyên toàn bộ logic đã kiểm chứng chạy đúng ở Bước 3 (ADF+KPSS xác định
d(i) riêng từng biến, Granger trên chuỗi đã sai phân đúng bậc, Johansen theo
đúng thủ tục tuần tự, Toda-Yamamoto đối chiếu chéo độc lập).

**Bổ sung mới:** vì input giờ có cột `is_interpolated`, mỗi script Phase 2/3/3b
chạy thêm một lượt **kiểm định độ nhạy tùy chọn** (loại bỏ các tuần có
`is_interpolated=True`, chạy lại kiểm định trên tập dữ liệu "sạch"). Nếu kết
luận (có ý nghĩa thống kê hay không, rank bao nhiêu) **thay đổi** giữa 2 lần
chạy (đầy đủ vs. đã loại tuần nội suy) → ghi WARNING rõ ràng — đây là dấu
hiệu kết luận có thể phụ thuộc vào chính bước nội suy ở Tầng 2, cần thận
trọng khi đưa vào bản thảo.

**Output:** `reports/phase1_stationarity.json`, `phase2_granger_causality.json`,
`phase3_cointegration.json`, `phase3b_toda_yamamoto.json` (mỗi file kèm thêm
kết quả kiểm định độ nhạy nếu có khác biệt).

---

## Tầng 4: Định tuyến Mô hình & Dự báo (Phase 4/5/6 + `main.py`)

Giữ nguyên cơ chế đã xây dựng ở Bước 2–3:

- **Phase 5** đọc `coint_rank` từ `reports/phase3_cointegration.json`, tự
  động route VECM (nếu 0 < r < n) hay VAR trên chuỗi đã sai phân (nếu r=0
  hoặc full rank) — không hard-code.
- **Phase 4** huấn luyện LSTM (PyTorch) độc lập, scaler fit chỉ trên Train,
  kèm baseline Holt-Winters tính động trên đúng tập Test.
- **Phase 6** tổng hợp kết quả Phase 4 + Phase 5, không hard-code bất kỳ số
  liệu so sánh nào.

**Bổ sung mới cho `main.py`:**
- Bọc mỗi lệnh gọi Phase trong `try/except`, dùng `logger.exception(...)` để
  ghi ERROR kèm traceback đầy đủ, và **dừng chuỗi (fail-fast)** — không chạy
  Phase sau nếu Phase trước lỗi.
- Dừng đúng **2 điểm xác nhận** đã chốt: sau Tầng 2 (duyệt dataset tuần —
  số tuần, số tuần nội suy, khoảng thời gian) và sau Tầng 3 (duyệt route
  VECM/VAR trước khi tốn thời gian huấn luyện LSTM ở Tầng 4).

**Output:** `models/lstm_*.pt`, `data/processed/lstm_predictions.csv`,
`data/processed/figures/*.png`, `reports/phase4_metrics.json`,
`reports/phase5_vecm_var.json`, `reports/phase6_ensemble_comparison.json`.

---

## Bảng tổng hợp Input/Output (tham chiếu nhanh)

| Tầng | Script | Input | Output |
|---|---|---|---|
| 1 | `tang1_db_extractor.py` | SQL Server | `data/raw/snapshot_.../*.csv`, `MANIFEST.md` |
| 2 | `phase0_data_reengineering.py` | `data/raw/snapshot_.../*.csv` | `data/processed/causal_weekly_dataset.csv` (+ `is_interpolated`) |
| 3 | `phase1_stationarity.py` → `phase3b_toda_yamamoto.py` | `causal_weekly_dataset.csv` | `reports/phase1-3b_*.json` |
| 4 | `phase4_lstm.py`, `phase5_vecm_var.py`, `phase6_ensemble.py`, `main.py` | `causal_weekly_dataset.csv` + `reports/phase*.json` | `models/*.pt`, `reports/phase4-6_*.json`, figures |

---

## Quyết định đã chốt trong phiên duyệt thiết kế

1. Kiến trúc 4 tầng: **Đã duyệt** — không thay đổi.
2. Xử lý mốc thời gian look-ahead bias (Tầng 2, mục 2.1): **Đã duyệt** —
   dùng `ActualEndDate` thay `PlannedShipmentDate`.
3. Cột `is_interpolated` cho kiểm định độ nhạy (Tầng 3): **Đã duyệt**.
4. Lệch ca làm việc (Tầng 2, mục 2.2): **Đã chốt** — tạm dùng ngày dương lịch
   chuẩn (00:00–23:59), giám sát bằng WARNING log cho bản ghi trong khung
   ±2 giờ quanh nửa đêm. Sẽ xem lại nếu cần quy tắc ca làm việc chính thức.

**Bước tiếp theo:** viết code triển khai theo đúng tài liệu này, bắt đầu từ
Tầng 1 (`tang1_db_extractor.py`).
