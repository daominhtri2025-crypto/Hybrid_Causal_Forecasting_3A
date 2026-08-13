# DEMO_GUIDE.md — Kịch bản Hướng dẫn Demo

> Phiên bản: 1.0 | Cập nhật: 2026-08-09  
> Dự án: Hybrid Causal Forecasting — Phương án 3-A  
> Đối tượng: Người thuyết trình trước Hội đồng khoa học / Đối tác doanh nghiệp

---

## 1. Bối cảnh & Mục tiêu (Demo Context)

**Bài toán:** Doanh nghiệp may mặc xuất khẩu (CMT) cần dự báo hiệu suất sản
xuất (OEE), thời gian trễ đơn hàng (Delay), và doanh thu FOB trong 12 tuần tới
— nhưng dữ liệu thực tế chỉ có khoảng 10–15 tuần quan sát (mẫu cực nhỏ).

**Giải pháp:** Hệ thống Hybrid Causal Forecasting 4 tầng:
- Không phải "hộp đen" AI — mỗi bước đều có cơ sở toán học kiểm chứng được
- Mô hình VECM khai thác quan hệ **nhân quả** (không chỉ tương quan) giữa các biến
- Thiết kế cho mẫu nhỏ: chọn tham số tiết kiệm bậc tự do (DoF), CI trung thực

**Thông điệp chính cần truyền tải:**
> "Hệ thống này ưu tiên tính TRUNG THỰC khoa học hơn tính chính xác ảo —
> nó thà nói 'tôi không chắc' (CI rộng) còn hơn đưa ra con số đẹp nhưng sai."

---

## 2. Chuẩn bị trước buổi Demo (Pre-flight Check)

### 2.1. Kiểm tra môi trường

```bash
# Bật virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Xác nhận dependencies
python -c "import pandas, statsmodels, torch; print('OK')"
```

### 2.2. Chuẩn bị Mock Data (nếu không có SQL Server)

Trong trường hợp **không kết nối được SQL Server trực tiếp** tại phòng bảo vệ:

- Sử dụng snapshot mẫu 10 tuần đã có sẵn trong `data/raw/`
- Tầng 1 (`tang1_db_extractor.py`) sẽ được **bỏ qua** — chạy trực tiếp từ Tầng 2
- Đảm bảo thư mục `data/raw/` chứa đủ 3 file CSV:
  - `cmt_oee_results.csv`
  - `cmt_delay_results.csv`
  - `fob_revenue.csv`

### 2.3. Checklist trước khi bắt đầu

- [ ] Terminal mở sẵn, font size đủ lớn (≥14pt) để hội đồng đọc được
- [ ] File explorer/VS Code mở sẵn tại thư mục gốc dự án
- [ ] Slide giới thiệu tổng quan kiến trúc 4 tầng (nếu có) hiển thị sẵn
- [ ] Tắt notification máy tính, bật chế độ Do Not Disturb
- [ ] Thử chạy 1 lần toàn bộ pipeline trước buổi demo ít nhất 30 phút

---

## 3. Kịch bản Demo Chi tiết

### Bước 1: Show Dữ liệu thô (Tầng 1) — *"Thực tế lộn xộn"*

**Thời lượng:** 3–4 phút

**Thao tác:**

```bash
# Mở file dữ liệu thô để hội đồng thấy sự "lộn xộn"
head -20 data/raw/cmt_oee_results.csv
```

Hoặc mở bằng Excel/VS Code để visual hơn.

**Lời thoại gợi ý:**

> "Đây là dữ liệu thực tế từ hệ thống ERP của doanh nghiệp. Các anh/chị có thể
> thấy: có dòng bị NULL, có OrderNo xuất hiện ở file này nhưng không có ở file kia,
> có giá trị OEE vượt 100% (lỗi nhập liệu)...
>
> Hệ thống Tầng 1 của chúng tôi giải quyết bằng 2 cơ chế:
> 1. **Chốt mốc thời gian (Snapshot):** Trích xuất tất cả 3 bảng cùng 1 thời
>    điểm — tránh lệch dữ liệu giữa các bảng.
> 2. **Băm SHA-256:** Mỗi file được gắn mã hash để đảm bảo dữ liệu không bị
>    thay đổi sau khi trích xuất. Đây là tiêu chuẩn forensic data integrity."

**Điểm nhấn kỹ thuật (nếu hội đồng hỏi sâu):**

```bash
# Show MANIFEST với checksum
cat data/raw/MANIFEST.md
```

> "Jaccard Index giữa các bảng đạt 0.95+ — nghĩa là hơn 95% OrderNo khớp nhau
> giữa 3 nguồn dữ liệu. Nếu chỉ số này thấp, hệ thống sẽ cảnh báo."

---

### Bước 2: Phép màu Làm sạch (Tầng 2) — *"Hệ thống tự xử lý"*

**Thời lượng:** 4–5 phút

**Thao tác:**

```bash
python -m scripts.phase0_data_reengineering
```

**Trong khi script chạy — CHỈ vào màn hình terminal:**

**Lời thoại gợi ý:**

> "Các anh/chị hãy quan sát dòng log trên terminal.
>
> *(chỉ vào dòng WARNING)*
>
> Đây — hệ thống tự phát hiện 'Phát hiện 3 giá trị NaN trong cột OEE_Score
> sau merge — đã loại bỏ'. Nó không âm thầm bỏ qua — nó GHI LẠI từng bất
> thường để kiểm toán sau này.
>
> Và đây — khi gặp tuần thiếu dữ liệu, hệ thống nội suy tuyến tính với
> `limit=2` — tức là chỉ lấp tối đa 2 tuần liên tiếp. Nếu thiếu 3 tuần
> trở lên, nó TỪ CHỐI nội suy và giữ nguyên NaN. Đây là kiểm soát chất lượng,
> không phải 'bịa' dữ liệu."

**Sau khi script chạy xong — mở file output:**

```bash
# Show cột is_interpolated (cờ minh bạch)
python -c "
import pandas as pd
df = pd.read_csv('data/processed/causal_weekly_dataset.csv')
print(df[['Year_Week', 'OEE_Score', 'is_interpolated_OEE_Score']].head(15))
print(f'\nSố tuần bị nội suy: {df[\"is_interpolated_OEE_Score\"].sum()}')
"
```

**Lời thoại gợi ý:**

> "Mỗi giá trị được nội suy đều có cờ `is_interpolated = True`. Khi viết báo
> cáo, chúng tôi có thể nói chính xác: bao nhiêu % dữ liệu là thực, bao nhiêu
> % là ước lượng. Không hệ thống 'hộp đen' nào cho anh/chị thông tin này."

---

### Bước 3: Sự minh bạch của Toán học (Tầng 3) — *"Hệ thống tự chốt luật chơi"*

**Thời lượng:** 5–6 phút

**Thao tác:**

```bash
# Chạy tuần tự 4 Phase
python -m scripts.phase1_stationarity
python -m scripts.phase2_granger_causality
python -m scripts.phase3_cointegration
python -m scripts.phase3b_toda_yamamoto
```

**Lời thoại trong khi Phase 1 chạy:**

> "Phase 1 kiểm định tính dừng bằng 2 test ĐỐI NGHỊCH nhau: ADF (H₀: có đơn
> vị gốc) và KPSS (H₀: chuỗi dừng). Chỉ khi CẢ HAI đồng thuận, hệ thống mới
> xác nhận. Đây gọi là Dual Confirmation — tránh kết luận sai do 1 test đơn lẻ."

**Khi Phase 3 chạy xong — chỉ vào terminal:**

> "Quan sát dòng này: 'Johansen Trace test: rank = 2 tại mức ý nghĩa 5%'.
>
> Hệ thống tự động phát hiện có 2 mối quan hệ cân bằng dài hạn giữa các biến.
> Đây là cơ sở toán học để chọn mô hình VECM thay vì VAR thuần túy.
>
> Và Phase 2 — Granger Causality — lưu ý là hệ thống cũng TỪ CHỐI những cặp
> biến không đạt ngưỡng ý nghĩa. Ví dụ nếu OEE không Granger-cause Delay ở
> mức p < 0.05, nó ghi rõ 'Không có ý nghĩa thống kê'. Đây là tính TRUNG THỰC
> — không phải mọi mối quan hệ đều tồn tại, và mô hình thừa nhận điều đó."

**Show kết quả JSON (tùy chọn nếu hội đồng muốn xem chi tiết):**

```bash
python -c "
import json
with open('reports/phase3_cointegration.json') as f:
    r = json.load(f)
print(f'Cointegration Rank: r = {r[\"coint_rank\"]}')
print(f'Model Route: {r[\"model_route\"]}')
print(f'k_ar_diff: {r[\"k_ar_diff\"]}')
"
```

---

### Bước 4: Kết quả Dự báo (Tầng 4) — *"Con số cuối cùng — và giới hạn của nó"*

**Thời lượng:** 5–6 phút

**Thao tác:**

```bash
python -m scripts.tang4_vecm_forecasting
```

**Sau khi chạy xong — mở kết quả:**

```bash
# Show bảng dự báo 12 tuần
python -c "
import pandas as pd
df = pd.read_csv('data/processed/vecm_forecast_results.csv')
print(df[['Week', 'OEE_Forecast', 'OEE_CI_Lower', 'OEE_CI_Upper']].to_string(index=False))
"
```

**Lời thoại gợi ý:**

> "Đây là kết quả dự báo 12 tuần cho chỉ số OEE.
>
> Cột `Point Forecast` là dự báo trung tâm. Nhưng quan trọng hơn — hãy nhìn
> 2 cột `CI_Lower` và `CI_Upper`. Đây là khoảng tin cậy 95%.
>
> *(chỉ vào tuần 8–12)*
>
> Các anh/chị thấy khoảng tin cậy **doãng rộng dần** ở các tuần xa. Đây KHÔNG
> phải lỗi — đây là TRUNG THỰC. Với mẫu nhỏ N ≈ 10 tuần, mô hình thẳng thắn
> nói: 'Càng dự báo xa, tôi càng không chắc chắn.'
>
> Công thức CI dùng phương pháp IRF/MA (Impulse Response Function):
> $$\text{Var}(e_{T+h}) = \sum_{i=0}^{h-1} \Psi_i \cdot \Sigma_u \cdot \Psi_i'$$
>
> Khi $h$ tăng, tổng tích lũy sai số tăng → CI rộng. Đây là kết quả toán học
> tất yếu, không phải giới hạn của mô hình riêng chúng tôi."

**Mở biểu đồ (nếu có):**

```bash
# Mở biểu đồ dự báo (nếu đang dùng GUI)
# Windows:
start data/processed/figures/vecm_forecast.png
# macOS:
open data/processed/figures/vecm_forecast.png
```

> "Biểu đồ này trực quan hóa: đường liền là Point Forecast, vùng tô mờ là CI 95%.
> Vùng tô mờ rộng dần — đó là tín hiệu trung thực cho người ra quyết định:
> 'Hãy thận trọng với dự báo sau tuần thứ 6.'"

---

### Bước 5: Khả năng Chịu lỗi & Quản lý Trạng thái — *"Hệ thống tự nhớ tiến trình"*

**Thời lượng:** 3–4 phút

**Thao tác:**

```bash
# Bước 1: Chạy pipeline nhưng DỪNG sau Phase 1
python -m main_pipeline --stop-after phase1
```

**Lời thoại gợi ý:**

> "Trong thực tế vận hành, pipeline có thể bị gián đoạn — do mất điện, lỗi
> mạng, hoặc đơn giản là muốn kiểm tra kết quả trung gian trước khi tiếp tục.
>
> Tôi vừa chạy pipeline với `--stop-after phase1` — hệ thống xử lý xong Phase 0
> và Phase 1 rồi dừng có kiểm soát."

```bash
# Bước 2: Xác nhận output trung gian đã tồn tại
ls reports/phase1_stationarity.json

# Bước 3: Tiếp tục pipeline từ Phase 3 — bỏ qua Phase 0 và 1
python -m main_pipeline --resume-from phase3
```

> "Bây giờ tôi chạy tiếp bằng `--resume-from phase3`. Hệ thống kiểm tra file
> JSON output của Phase 0, 1 — thấy đã tồn tại và không rỗng → tự động BỎ QUA
> hai Phase này, chỉ chạy từ Phase 3 trở đi.
>
> *(chỉ vào dòng log 'skipped (resume)')*
>
> Đây là cơ chế **JSON Contract**: mỗi Phase ghi kết quả vào file JSON —
> Phase sau đọc JSON đó làm input. File JSON vừa là output, vừa là 'chứng chỉ
> hoàn thành' (proof of completion). Không có JSON → Phase chưa chạy → pipeline
> TỰ ĐỘNG chạy lại Phase đó thay vì crash.
>
> Nhật ký chuyển tiếp giữa các Phase được ghi vào
> `reports/logs/phase_transitions.jsonl` — mỗi dòng là 1 sự kiện chuyển Phase,
> dùng để truy vết lịch sử chạy pipeline."

---

### Bước 6: Tự phục hồi — Eigenvalue Clamping — *"Hệ thống tự sửa lỗi toán học"*

**Thời lượng:** 2–3 phút

**Thao tác:**

```bash
# Xem log pipeline gần nhất — tìm dòng WARNING về eigenvalue
# (nếu mẫu nhỏ, WARNING này sẽ xuất hiện)
grep -i "eigenvalue" reports/logs/pipeline_*.log
```

Nếu có dòng WARNING, chỉ vào và giải thích:

**Lời thoại gợi ý:**

> "Khi mẫu chỉ có 10 tuần, ma trận hiệp phương sai phần dư $\Sigma_u$
> (4×4 ma trận, ước lượng từ 10 quan sát) có thể bị **suy biến** — một số
> eigenvalue gần bằng 0 hoặc âm, khiến phân rã Cholesky thất bại.
>
> Hệ thống truyền thống sẽ **CRASH** tại bước này và yêu cầu can thiệp thủ công.
>
> Pipeline của chúng tôi tự phát hiện vấn đề và áp dụng **Eigenvalue Clamping**:
> - Phân rã spectral: $\Sigma_u = V \Lambda V^T$
> - Kẹp eigenvalue $\leq 0$ lên ngưỡng tối thiểu: $\max(|\lambda|) \times 10^{-8}$
> - Tái tạo ma trận xác định dương: $\tilde{\Sigma}_u = V \tilde{\Lambda} V^T$
>
> Đây KHÔNG phải 'hack' — đây là kỹ thuật đại số tuyến tính chuẩn, tương tự
> Ridge Regularization nhưng **chính xác hơn**: Ridge thêm nhiễu vào TẤT CẢ
> chiều ($+\varepsilon I$), trong khi Eigenvalue Clamping chỉ sửa chiều bị lỗi,
> giữ nguyên chiều khỏe mạnh.
>
> Kết quả: khoảng tin cậy vẫn trung thực — không bị phóng đại giả."

---

## 4. Xử lý câu hỏi khó (Q&A Preparation)

### Câu hỏi 1: "Tại sao không dùng AI/Deep Learning (LSTM, Transformer) mà lại dùng VECM?"

**Gợi ý trả lời:**

> "Câu hỏi rất hay. Có 3 lý do chính:
>
> **Thứ nhất — Kích thước mẫu:** LSTM cần tối thiểu hàng trăm điểm dữ liệu
> để hội tụ. Với N = 10 tuần (30 quan sát cho 3 biến), Deep Learning sẽ
> overfit ngay lập tức. VECM với k_ar_diff = 0 chỉ cần ước lượng 6 tham số
> mỗi phương trình — phù hợp với mẫu nhỏ.
>
> **Thứ hai — Khả năng diễn giải:** VECM cho biết CƠ CHẾ nhân quả: OEE tác động
> lên Delay theo hệ số α bao nhiêu, tốc độ hồi quy về cân bằng là gì. Deep
> Learning chỉ cho 1 con số dự báo mà không giải thích được TẠI SAO.
>
> **Thứ ba — Đồng tích hợp:** Các biến của chúng tôi có quan hệ cân bằng dài
> hạn (cointegration rank = 2). VECM khai thác trực tiếp thông tin này. LSTM
> không có cơ chế tương đương — nó phải 'học lại' từ dữ liệu, nhưng mẫu quá
> nhỏ để học."

---

### Câu hỏi 2: "Dữ liệu chỉ 10 tuần — mô hình có đáng tin không?"

**Gợi ý trả lời:**

> "Đây chính xác là lý do chúng tôi thiết kế hệ thống theo cách này:
>
> 1. **k_ar_diff = 0** (không thêm lag khác biệt): Mỗi phương trình VECM chỉ
>    cần 6 bậc tự do thay vì 11. Với 10 quan sát, tỷ lệ DoF/parameter ≈ 1.7 —
>    thấp nhưng vẫn khả thi. Nếu dùng k_ar_diff = 1, tỷ lệ giảm xuống 0.9
>    (underdetermined) → hệ thống TỰ ĐỘNG chọn mô hình tiết kiệm nhất.
>
> 2. **Khoảng tin cậy rộng là TRUNG THỰC:** Chúng tôi không giấu sự không
>    chắc chắn. CI rộng nghĩa là: 'Dự báo có thể đúng, nhưng hãy dùng nó
>    như xu hướng, không phải con số tuyệt đối.'
>
> 3. **Toda-Yamamoto cross-check:** Ngay cả quan hệ nhân quả cũng được kiểm
>    chứng bằng 2 phương pháp độc lập. Nếu kết quả khớp nhau (agreement rate
>    cao), đó là tín hiệu robust dù mẫu nhỏ."

---

### Câu hỏi 3: "Làm sao đảm bảo không có data leakage (rò rỉ thông tin tương lai)?"

**Gợi ý trả lời:**

> "Hệ thống có 3 lớp bảo vệ chống look-ahead bias:
>
> 1. **Zero Look-ahead Bias ở Tầng 2:** Chúng tôi dùng `ActualEndDate` (ngày
>    hoàn thành thực tế) thay vì `PlannedShipmentDate` (ngày kế hoạch). Ngày
>    kế hoạch có thể bị điều chỉnh ngược — dùng nó là rò rỉ thông tin tương lai.
>
> 2. **Chronological split ở Tầng 4:** Train/Test luôn chia theo thời gian, không
>    random. Scaler chỉ fit() trên Train, không nhìn thấy Test.
>
> 3. **Kiến trúc 4 tầng cách ly:** Mỗi tầng chỉ đọc output của tầng trước qua
>    file JSON/CSV — không có biến global hay shared state nào có thể vô tình
>    truyền thông tin ngược."

---

## 5. Kết thúc Demo — Tổng kết

**Lời thoại kết:**

> "Tóm lại, hệ thống Hybrid Causal Forecasting 4 tầng mà chúng tôi xây dựng:
>
> - **Minh bạch:** Mọi bước đều có log, có cờ, có JSON kiểm chứng
> - **Trung thực:** Từ chối kết quả không có ý nghĩa thống kê, CI rộng khi
>   không chắc chắn
> - **Tái lập được:** Bất kỳ ai chạy lại cùng dữ liệu đều ra cùng kết quả
>   (seed cố định, pipeline deterministic)
> - **Thích ứng mẫu nhỏ:** Thiết kế tiết kiệm DoF, không ép mô hình phức tạp
>   vào dữ liệu ít
>
> Cảm ơn hội đồng/đối tác đã lắng nghe. Tôi sẵn sàng nhận câu hỏi."

---

## 6. Timeline tham khảo

| Phần | Thời lượng | Tổng cộng |
|---|---|---|
| Bước 1: Dữ liệu thô | 3–4 phút | 4 phút |
| Bước 2: Làm sạch | 4–5 phút | 9 phút |
| Bước 3: Kiểm định | 5–6 phút | 15 phút |
| Bước 4: Dự báo | 5–6 phút | 21 phút |
| Bước 5: Chịu lỗi & Resume | 3–4 phút | 25 phút |
| Bước 6: Tự phục hồi (Eigenvalue) | 2–3 phút | 28 phút |
| Q&A | 5–10 phút | 38 phút |

> **Tổng thời lượng khuyến nghị:** 30–38 phút (bao gồm Q&A)
> Nếu giới hạn thời gian 25 phút, có thể bỏ Bước 5–6 và chỉ nhắc trong Q&A.
