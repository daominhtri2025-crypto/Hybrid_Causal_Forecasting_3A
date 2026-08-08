# skill.md — Phân vai trò xử lý & Hợp đồng Input/Output (Phương án 3-A Rebuild)

> Mục đích: đảm bảo mỗi "luồng xử lý" (có thể là 1 agent Claude Code riêng,
> hoặc 1 người/1 phiên làm việc riêng) chỉ đọc/ghi đúng phạm vi của mình,
> không chồng chéo, không ghi đè dữ liệu của luồng khác. Đây là hợp đồng bắt
> buộc — mọi thay đổi format input/output phải cập nhật file này trước.

---

## 1. Ba luồng xử lý chính (Roles)

### 🔵 Role A — Data Engineering (Tầng 1 + Tầng 2)
**Sở hữu:** `scripts/tang1_db_extractor.py`, `scripts/phase0_data_reengineering.py`
**Trách nhiệm:**
- Kết nối SQL Server, snapshot dữ liệu thô đồng thời (cùng thời điểm).
- Đồng bộ trục thời gian (PlannedShipmentDate / ActualEndDate / ShipmentDate)
  về CÙNG một hệ quy chiếu — triệt tiêu look-ahead bias.
- Gộp dữ liệu theo tuần, xử lý trọng số (weighting theo `PlanQty`), xử lý NaN
  bằng nội suy thay vì gán 0 vô điều kiện.
**KHÔNG được làm:** chạy bất kỳ kiểm định thống kê nào (ADF, Granger, Johansen),
không train mô hình.

### 🟢 Role B — Econometrics & Causality Analysis (Tầng 3)
**Sở hữu:** `scripts/phase1_stationarity.py`, `phase2_granger_causality.py`,
`phase3_cointegration.py`, `phase3b_toda_yamamoto.py`
**Trách nhiệm:**
- Kiểm định tính dừng, xác định d(i) riêng từng biến.
- Granger causality (chuỗi đã sai phân) + Toda-Yamamoto (chuỗi mức) — đối
  chiếu chéo bắt buộc.
- Johansen cointegration — xác định rank theo đúng thủ tục tuần tự.
**KHÔNG được làm:** không đọc `data/raw/` trực tiếp (chỉ đọc
`data/processed/causal_weekly_dataset.csv` do Role A tạo ra), không train
mô hình Deep Learning.

### 🟠 Role C — Deep Learning Modeler (Tầng 4, nhánh LSTM)
**Sở hữu:** `scripts/phase4_lstm.py`
**Trách nhiệm:**
- Xây dựng, huấn luyện, lưu trọng số LSTM (PyTorch) dự báo Revenue.
- Baseline Holt-Winters (tính động, cùng script hoặc script phụ trợ).
**KHÔNG được làm:** không tự đọc/diễn giải kết quả Johansen/Granger (chỉ cần
biết bộ đặc trưng đầu vào, không cần biết rank/d(i)).

### 🟣 Role D — Model Routing & Ensemble (Tầng 4, nhánh Econometric Forecast + Tổng hợp)
**Sở hữu:** `scripts/phase5_vecm_var.py`, `scripts/phase6_ensemble.py`, `main.py`
**Trách nhiệm:**
- Đọc rank từ Phase 3 → tự động route VECM hay VAR (Phase 5).
- Tổng hợp kết quả Phase 4 (LSTM) + Phase 5 (VECM/VAR) + Holt-Winters →
  bảng so sánh cuối cùng (Phase 6), không hard-code bất kỳ số nào.
- `main.py` điều phối toàn bộ chuỗi Tầng 1 → Tầng 4, dừng đúng 2 điểm xác
  nhận đã quy định trong `CLAUDE.md` mục 6.

---

## 2. Hợp đồng Input/Output từng Phase (bắt buộc tuân thủ)

| Phase | Script | Input (đọc) | Output (ghi) | Sở hữu |
|---|---|---|---|---|
| Tầng 1 | `tang1_db_extractor.py` | SQL Server (`qtdn_datamining`) | `data/raw/snapshot_YYYYMMDD_HHMM/*.csv` + `data/raw/MANIFEST.md` | Role A |
| Phase 0 | `phase0_data_reengineering.py` | `data/raw/snapshot_.../cmt_oee_results.csv`, `cmt_delay_results.csv`, `fob_revenue.csv` | `data/processed/causal_weekly_dataset.csv` | Role A |
| Phase 1 | `phase1_stationarity.py` | `data/processed/causal_weekly_dataset.csv` | `reports/phase1_stationarity.json` | Role B |
| Phase 2 | `phase2_granger_causality.py` | `data/processed/causal_weekly_dataset.csv` + `reports/phase1_stationarity.json` | `reports/phase2_granger_causality.json` | Role B |
| Phase 3 | `phase3_cointegration.py` | `data/processed/causal_weekly_dataset.csv` + `reports/phase1_stationarity.json` | `reports/phase3_cointegration.json` | Role B |
| Phase 3b | `phase3b_toda_yamamoto.py` | `data/processed/causal_weekly_dataset.csv` + `reports/phase1_stationarity.json` + `reports/phase2_granger_causality.json` (để đối chiếu) | `reports/phase3b_toda_yamamoto.json` | Role B |
| Phase 4 | `phase4_lstm.py` | `data/processed/causal_weekly_dataset.csv` | `models/lstm_*.pt`, `data/processed/lstm_predictions.csv`, `reports/phase4_metrics.json` | Role C |
| Phase 5 | `phase5_vecm_var.py` | `data/processed/causal_weekly_dataset.csv` + `reports/phase3_cointegration.json` + `reports/phase1_stationarity.json` | `data/processed/figures/vecm_forecast.png`, `reports/phase5_vecm_var.json` | Role D |
| Phase 6 | `phase6_ensemble.py` | `reports/phase4_metrics.json` + `reports/phase5_vecm_var.json` | `reports/phase6_ensemble_comparison.json`, `data/processed/figures/ensemble_forecast.png` | Role D |
| Orchestration | `main.py` | Toàn bộ trên, theo thứ tự | log chạy + điểm dừng xác nhận | Role D |

**Quy tắc cứng:** một script chỉ được ghi vào các file nằm trong cột
"Output" của chính nó. Nếu Phase X cần dữ liệu Phase Y chưa tạo ra, Phase X
phải dừng và báo lỗi rõ ràng (`FileNotFoundError` kèm hướng dẫn chạy Phase Y
trước) — không được tự tính lại thay cho Phase Y.

---

## 3. Hai điểm dừng xác nhận bắt buộc (Human-in-the-loop)

1. **Sau Phase 0** — `main.py` dừng, in tóm tắt dataset tuần (số tuần, số
   tuần NaN/nội suy, khoảng thời gian) — chờ Anh Béo xác nhận trước khi chạy
   Tầng 3.
2. **Sau Phase 3** — `main.py` dừng, in kết luận rank + route đề xuất
   (VECM/VAR) — chờ Anh Béo xác nhận trước khi Tầng 4 huấn luyện mô hình
   (huấn luyện LSTM tốn thời gian, không nên chạy nếu route/dataset còn nghi vấn).

---

## 4. Nguyên tắc chung cho mọi Role

- Đọc `CLAUDE.md` trước khi viết bất kỳ dòng code nào (cấu trúc thư mục,
  quy định comment tiếng Việt, nguyên tắc bất biến dữ liệu).
- Không role nào được sửa file thuộc sở hữu của role khác.
- Mọi thay đổi format input/output phải cập nhật bảng ở mục 2 TRƯỚC khi
  sửa code.
