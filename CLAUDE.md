# CLAUDE.md — Quy tắc quản trị dự án Phương án 3-A (Rebuild)

> Phiên bản: 2.0 (đập đi xây lại) — thay thế hoàn toàn `CLAUDE.md` v1.0 (dựng
> lại thủ công ở Bước 1). File này là **nguồn chân lý duy nhất** (single
> source of truth) cho mọi quy tắc cấu trúc, xử lý dữ liệu, và coding
> convention của dự án. Mọi script — dù do Claude hay Anh Béo viết — phải
> tuân thủ file này.

---

## 1. Cấu trúc thư mục chuẩn (CỐ ĐỊNH — không tự ý đổi tên/thêm cấp)

```
Phuong_An_3/
├── CLAUDE.md                      # File này
├── skill.md                       # Phân vai trò Agent + hợp đồng input/output
├── README.md
├── main.py                        # Orchestrator — điều phối Tầng 1 -> Tầng 4
├── requirements.txt
│
├── data/
│   ├── raw/                       # BẤT BIẾN. Snapshot thô từ SQL Server.
│   │   ├── snapshot_YYYYMMDD_HHMM/
│   │   │   ├── cmt_oee_results.csv
│   │   │   ├── cmt_delay_results.csv
│   │   │   ├── cmt_schedule.csv         (chỉ nếu Tầng 2 thật sự cần ngày tháng
│   │   │   │                             gốc — KHÔNG dùng để tính lại OEE/Delay)
│   │   │   └── fob_revenue.csv
│   │   └── MANIFEST.md            # Log từng snapshot: thời điểm trích xuất,
│   │                               # checksum SHA-256, số dòng mỗi file
│   │
│   └── processed/                 # MỌI output đã qua xử lý — không giới hạn
│       ├── causal_weekly_dataset.csv
│       ├── figures/
│       └── ...
│
├── models/                        # Trọng số mô hình đã train (.pt)
├── scripts/                       # Toàn bộ mã nguồn xử lý (xem skill.md)
├── reports/                       # Kết quả từng Phase dạng JSON (machine-readable)
│   └── qa/                        # Báo cáo QA, rà soát chất lượng
├── docs/
│   └── thesis_draft/              # Bản thảo bài báo (.docx)
└── .claude/agents/                # Định nghĩa sub-agent (nếu dùng Claude Code)
```

**Quy tắc đặt tên:** file script đặt tên theo `tangN_ten-chuc-nang.py` hoặc
`phaseN_ten-chuc-nang.py` (giữ quy ước Phase đã dùng cho Tầng 3–4, dùng tiền
tố `tang1_` cho Tầng 1 vì chưa có số Phase tương ứng). Không đặt tên viết tắt
mơ hồ (ví dụ cấm `p3.py`, `utils2.py`).

---

## 2. Nguyên tắc bất biến dữ liệu (Data Immutability)

1. **`data/raw/` là BẤT BIẾN.** Không script nào — kể cả script "sửa lỗi" —
   được phép ghi đè, chỉnh sửa, hay xóa file trong `data/raw/`. Mọi file ở
   đây chỉ được **đọc**.
2. **Mọi kết quả xử lý phải ghi ra `data/processed/`.** Không có ngoại lệ.
   Nếu một script cần "sửa" dữ liệu (lọc outlier, nội suy NaN, đổi đơn vị),
   nó phải đọc từ `data/raw/` (hoặc từ một file khác trong `processed/`) và
   ghi kết quả MỚI ra `processed/`, giữ nguyên file đầu vào.
3. **Mỗi snapshot trong `data/raw/` phải được trích xuất CÙNG MỘT THỜI ĐIỂM**
   (xem `skill.md`, Tầng 1) để tránh lệch `OrderNo` giữa các file. Timestamp
   trích xuất bắt buộc phải ghi vào `MANIFEST.md`.
4. **Không tự tính lại business logic đã có sẵn trong output đã validate.**
   Nếu `cmt_oee_results.csv` đã có cột `OEE_Score`, không script nào được
   tự suy ra `OEE_Score` từ `RealQty/PlanQty` một lần nữa.

---

## 3. Quy định coding bắt buộc

### 3.1. Comment tiếng Việt chi tiết (BẮT BUỘC — không có ngoại lệ)

Mọi file `.py` phải có:
- **Docstring đầu file**: mục đích, thay đổi so với bản trước (nếu là bản sửa),
  input/output, trích dẫn khoa học liên quan (nếu có).
- **Comment tiếng Việt trước MỖI khối logic quan trọng** (không chỉ ở đầu
  hàm) — giải thích **tại sao** làm vậy, không chỉ mô tả lại code đang làm gì.
- **Comment tại mọi quyết định rẽ nhánh có ý nghĩa thống kê/nghiệp vụ**
  (ví dụ: vì sao chọn ngưỡng 0.05, vì sao dùng sMAPE thay vì MAPE).

### 3.2. Không hard-code số liệu kết quả

Mọi số liệu xuất hiện trong bảng so sánh, biểu đồ, hay bản thảo phải được
**tính trong chính script tạo ra nó**, trên cùng một tập dữ liệu/test set.
Baseline, benchmark, hay số liệu "tham chiếu" đều phải tính động.

### 3.3. Không giả định — luôn đọc từ kết quả Phase trước

Mọi tham số phụ thuộc vào kết quả thống kê (bậc tích hợp d(i), lag order p,
cointegration rank r) phải được **đọc từ file JSON của Phase tạo ra nó**
(`reports/phaseN_*.json`), không hard-code, không giả định giống nhau cho
mọi biến/mọi lần chạy.

### 3.4. Chia Train/Validation/Test

Luôn luôn **chronological** (theo thời gian), không random split. Scaler
(nếu có) chỉ `fit()` trên tập Train, `transform()` áp dụng cho Train và Test
bằng thống kê đã học từ Train.

### 3.5. Tái lập được (Reproducibility)

- Set `seed` cố định cho mọi thư viện có yếu tố ngẫu nhiên (`numpy`, `torch`).
- Mọi script chạy độc lập được (đọc input cố định, không phụ thuộc biến môi
  trường ẩn) và lưu output đủ để script sau đọc lại mà không cần chạy lại từ
  đầu.

---

## 4. Ranh giới kiến trúc cứng (Hard Boundaries)

- Phương án 3 chỉ tiêu thụ (consume) dữ liệu từ Phương án A qua **snapshot
  bất biến** trong `data/raw/` — không truy vấn SQL Server song song với
  Phương án A, không chỉnh sửa repo `qtdn_datamining`.
- Tầng 1 (`db_extractor.py`) là **điểm truy cập SQL Server DUY NHẤT** của
  Phương án 3. Không script nào khác ở Tầng 2–4 được phép mở kết nối SQL.

---

## 5. Chuẩn mực khoa học (Scientific Integrity)

- Trích dẫn APA 7th Edition; nguồn chưa xác minh gắn nhãn `[Cần bổ sung nguồn]`.
- Phân biệt rõ "Sự thật/Dữ liệu" (kết quả tính toán trực tiếp) và "Suy luận"
  (diễn giải, khuyến nghị) trong mọi báo cáo — kể cả trong log console.
- Một tuyên bố phương pháp luận trong bản thảo phải có script tương ứng
  trong `scripts/` — không tuyên bố phương pháp không có code hỗ trợ.
- "Null finding" (không có ý nghĩa thống kê) là kết quả khoa học hợp lệ —
  không được điều chỉnh tham số/dữ liệu chỉ để tạo ra kết quả có ý nghĩa
  (p-hacking).

---

## 6. Quy trình xác nhận (Confirmation-based workflow)

- Claude đề xuất/thiết kế/chạy thử trong sandbox; Anh Béo xác nhận và chạy
  chính thức trên máy local (`D:\CLAUDE COWORD\NCS_TIEN_SI_2026\Phuong_An_3`).
- Claude không tuyên bố "đã lưu vào máy anh" — luôn nói rõ vị trí file cần
  tải về và đặt vào đâu.
- 2 điểm dừng bắt buộc chờ xác nhận (theo `skill.md`): sau Tầng 2 (Phase 0 —
  xác nhận dataset tuần hợp lệ) và sau Tầng 3 (Phase 3 — xác nhận route
  VECM/VAR trước khi Tầng 4 dự báo).

---

## 7. Cơ chế Ghi Log (Logging) và Giám sát

### 7.1. Cấm `print()` cho tiến trình cốt lõi

Mọi script trong `scripts/` (Tầng 1–4, `main.py`) **bắt buộc dùng module
`logging` chuẩn của Python** để ghi nhận luồng thực thi — không dùng `print()`
thuần túy cho bất kỳ thông điệp nào liên quan đến tiến trình xử lý dữ liệu,
kết quả kiểm định, hay lỗi.

`print()` chỉ được chấp nhận trong 2 trường hợp hẹp: (1) script demo/thử
nghiệm ngoài `scripts/` (ví dụ trong `notebooks/` nếu có), hoặc (2) menu
tương tác dòng lệnh không thuộc luồng xử lý chính.

**Khởi tạo logger chuẩn (đặt trong `scripts/utils.py`, mọi script import dùng
chung — tránh mỗi file tự cấu hình một kiểu):**

```python
# scripts/utils.py
import logging
import os
from datetime import datetime

def get_logger(phase_name: str) -> logging.Logger:
    """
    Tạo logger dùng chung cho toàn pipeline.
    - phase_name: tên Phase gọi hàm này (vd: "phase0", "phase3b") — dùng để
      gắn nhãn logger, giúp phân biệt log của từng Phase khi đọc chung 1 file.
    - Ghi đồng thời ra 2 nơi: console (để theo dõi khi chạy tay) và file log
      tập trung trong reports/logs/ (để tra cứu lại sau, đúng mục 7.2).
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # Phuong_An_3/
    log_dir = os.path.join(base_dir, "reports", "logs")
    os.makedirs(log_dir, exist_ok=True)

    # Một file log CHUNG cho mỗi lần chạy pipeline (không phải mỗi Phase 1 file
    # riêng) — timestamp lấy tại thời điểm main.py (hoặc script) bắt đầu chạy,
    # để dễ tra cứu toàn bộ luồng của 1 lần chạy trong 1 file duy nhất.
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    log_path = os.path.join(log_dir, f"pipeline_{run_timestamp}.log")

    logger = logging.getLogger(phase_name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:  # tránh add handler trùng nếu get_logger gọi nhiều lần
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s"
        )
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger
```

### 7.2. Vị trí lưu trữ tập trung

- Mọi file log xuất ra `reports/logs/` — **không** ghi log rải rác trong
  `scripts/` hay `data/`.
- Tên file bắt buộc chứa timestamp theo định dạng `pipeline_YYYYMMDD_HHMM.log`
  (giờ bắt đầu chạy). Mỗi lần chạy `main.py` (hoặc chạy tay 1 Phase riêng lẻ)
  tạo 1 file log riêng — không ghi đè log của lần chạy trước, phục vụ truy vết
  (audit trail) khi so sánh kết quả giữa các lần chạy.
- `reports/logs/` được liệt kê trong `.gitignore` nếu dự án dùng Git (log có
  thể chứa dữ liệu số lượng lớn, không cần versioning), nhưng KHÔNG bị xóa tự
  động — giữ lại để đối chiếu khi cần.

### 7.3. Phân cấp Log Levels (nghiêm ngặt — không lẫn lộn giữa các cấp)

| Level | Bắt buộc ghi khi nào | Ví dụ trong pipeline này |
|---|---|---|
| **INFO** | Thời điểm bắt đầu/kết thúc mỗi Phase; thời gian tải dữ liệu; số dòng input/output của mỗi bước biến đổi dữ liệu | `"Phase 0 bắt đầu"`, `"Đã tải cmt_oee_results.csv: 3,350 dòng"`, `"Sau khi gộp OrderNo: 3,344 dòng"`, `"Phase 0 hoàn tất trong 4.2s"` |
| **WARNING** | Phát hiện bất thường về dữ liệu nhưng CHƯA làm crash hệ thống — **bắt buộc ghi rõ SỐ LƯỢNG dòng bị ảnh hưởng**, không chỉ nói "có vấn đề" | `"Phát hiện 12 giá trị NaN trong cột OEE_Score sau merge — đã loại bỏ"`; `"Tuần 2026-06-15 không có đơn hàng nào (rỗng)"`; `"Đã drop 6 dòng trùng lặp OrderNo trong cmt_delay_results.csv"`; `"Cột PlannedShipmentDate: 3 dòng bị ép kiểu datetime thất bại (NaT), đã loại khỏi tập tính toán"` |
| **ERROR / CRITICAL** | Lỗi khiến hàm/Phase NGỪNG hoạt động — bắt buộc `logger.exception(...)` hoặc `exc_info=True` để ghi **toàn bộ Traceback**, chỉ rõ tên file `.py` và số dòng sinh lỗi (formatter ở mục 7.1 đã tự động thêm `filename:lineno` vào mọi dòng log) | `"Phase 3 dừng: không tìm thấy reports/phase1_stationarity.json — cần chạy Phase 1 trước"` (ERROR, kèm traceback nếu là exception); `"Kết nối SQL Server thất bại sau 3 lần thử"` (CRITICAL) |

**Quy tắc viết message log:**
- Message log viết bằng **tiếng Việt**, nhất quán với quy định comment ở
  mục 3.1 — Anh Béo là người đọc log trực tiếp để giám sát, không phải máy.
- Không dùng WARNING cho lỗi thực sự nghiêm trọng (phải dùng ERROR/CRITICAL),
  và không dùng ERROR cho những bất thường dữ liệu vẫn xử lý tiếp được (phải
  dùng WARNING) — phân cấp sai sẽ làm nhiễu khi rà soát log về sau.
- Khi bắt exception, luôn dùng `logger.exception("...")` (tự động kèm traceback)
  thay vì `logger.error(str(e))` (chỉ có thông điệp lỗi, mất traceback).

---

## 8. Chiến lược xử lý khoảng trống thời gian (Gap Handling)

### 8.1. Forward-fill có giới hạn (Strategy A)

Khi gộp đơn hàng theo tuần (`orders_to_weekly_delay()`), chuỗi thời gian có
thể thiếu tuần (tuần không có đơn hàng nào). Chiến lược xử lý:

1. **Reindex** chuỗi tuần về lưới đều đặn (mỗi tuần 1 dòng, `freq='W-MON'`).
2. **Forward-fill** (`ffill`) tối đa **4 tuần liên tiếp** — giả định trạng
   thái không đổi trong ngắn hạn.
3. **Giữ NaN** cho khoảng trống > 4 tuần — đây là structural gap, không nên
   nội suy (sẽ bị drop trước khi phân tích).
4. **Đánh dấu** cột `is_filled` (`True` = dòng được forward-fill) để Phase 1
   sensitivity analysis đánh giá tác động.

### 8.2. Tại sao limit = 4 tuần

4 tuần ≈ 1 tháng — khoảng trống ngắn hơn 1 tháng thường do nghỉ lễ, bảo trì,
hoặc dao động tự nhiên trong sản xuất. Khoảng trống dài hơn có thể do ngừng
sản xuất, thay đổi cơ cấu — forward-fill sẽ gây bias.

---

## 9. Kiểm định Zivot-Andrews cho trường hợp ADF/KPSS mâu thuẫn

### 9.1. Quy trình

Khi ADF và KPSS cho kết quả **mâu thuẫn** (Case 3: ADF bác bỏ unit root NHƯNG
KPSS cũng bác bỏ stationarity), pipeline tự động chạy kiểm định
**Zivot-Andrews (1992)** làm tiebreaker:

- ZA cho phép **1 structural break nội sinh** — không cần biết trước vị trí break.
- Nếu ZA bác bỏ H0 (unit root) → chuỗi dừng quanh break → kết luận **stationary**.
- Nếu ZA không bác bỏ → giữ **contradictory**, tạm xử lý như dừng (bảo thủ).
- Nếu ZA thất bại (mẫu quá nhỏ) → fallback về contradictory.

### 9.2. Tham chiếu

Zivot, E. & Andrews, D. W. K. (1992). Further evidence on the Great Crash,
the oil-price shock, and the unit-root hypothesis. *Journal of Business &
Economic Statistics*, 10(3), 251–270.

---

## 10. Checkpoint & Resume (`--resume-from`)

### 10.1. Cách dùng

```bash
# Tiếp tục từ Phase 3 — bỏ qua Phase 0, 1, 2 nếu output đã có
python main_pipeline.py --resume-from phase3

# Kết hợp: chỉ chạy Phase 4
python main_pipeline.py --resume-from phase4 --stop-after phase4
```

### 10.2. Cơ chế

- Mỗi Phase có file output kỳ vọng (xem `PHASE_OUTPUT_FILES` trong
  `main_pipeline.py`).
- Khi `--resume-from` được truyền, các Phase **trước** điểm resume sẽ kiểm tra
  xem output đã tồn tại và không rỗng → nếu có, bỏ qua (status = `skipped (resume)`).
- Nếu output không tồn tại → Phase đó **vẫn chạy** (không crash).
- `log_phase_transition()` ghi nhật ký chuyển tiếp giữa các Phase vào
  `reports/logs/phase_transitions.jsonl` (định dạng JSONL, 1 dòng/transition).

### 10.3. Lưu ý

- `--resume-from` **không đảm bảo** kết quả Phase trước vẫn hợp lệ — nếu đã
  thay đổi dữ liệu đầu vào hoặc tham số, nên chạy lại từ đầu.
- Dùng chủ yếu để **debug** và **phát triển** — trong production nên chạy
  toàn bộ pipeline.
