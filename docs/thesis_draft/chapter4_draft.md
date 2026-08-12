# Chương 4: Kết quả Thực nghiệm và Thảo luận

> **Phương pháp Hybrid Causal Forecasting — Phương án 3-A**
>
> Dữ liệu: 375 quan sát tuần (01/2018 – 01/2026), 3 biến nội sinh:
> Production Volume, Delay Rate, Order Demand.

---

## 4.1. Kiểm định tính dừng và bậc tích hợp (Phase 1)

### 4.1.0. Tiền xử lý chuỗi thời gian — Forward-fill có giới hạn

Trước khi kiểm định tính dừng, dữ liệu tuần từ Phase 0 được xử lý khoảng trống
thời gian (tuần không có đơn hàng nào hoàn thành) theo chiến lược forward-fill
có giới hạn (Strategy A). Chuỗi tuần được reindex về lưới đều đặn (`freq='W-MON'`),
sau đó áp dụng `ffill(limit=4)` — tối đa 4 tuần liên tiếp được lấp bằng giá trị
quan sát gần nhất. Khoảng trống vượt 4 tuần ($\approx$ 1 tháng) được giữ nguyên NaN
vì đây là structural gap có thể phản ánh ngừng sản xuất hoặc thay đổi cơ cấu —
forward-fill sẽ tạo bias.

Phương pháp forward-fill được ưu tiên so với nội suy tuyến tính (linear interpolation)
cho biến `DelayRate` vì ba lý do: (i) `DelayRate` là tỷ lệ rời rạc (binomial
proportion), nội suy tuyến tính giả định xu hướng chuyển tiếp mượt — giả định
không phù hợp cho đại lượng nhị thức; (ii) tuần trống phản ánh trạng thái sản
xuất không đổi, forward-fill bảo toàn ý nghĩa kinh tế này; (iii) nội suy tuyến
tính tạo xu hướng nhân tạo (spurious trend) giữa hai điểm xa nhau, có thể ảnh
hưởng đến kiểm định tính dừng. Mỗi giá trị forward-fill được đánh dấu bằng cờ
`is_filled = True` phục vụ phân tích độ nhạy ở các Phase tiếp theo (Enders, 2014).

### 4.1.1. Phương pháp kiểm định

Nghiên cứu áp dụng chiến lược xác nhận kép ADF + KPSS (Pfaff, 2008) để xác
định bậc tích hợp $d(i)$ của từng biến. Chiến lược này kết hợp hai kiểm định
có giả thuyết null đối lập — ADF kiểm định $H_0$: chuỗi có nghiệm đơn vị
(non-stationary) trong khi KPSS kiểm định $H_0$: chuỗi dừng (stationary) —
nhằm giảm thiểu sai lầm loại I/II khi chỉ dùng một kiểm định đơn lẻ.

- **ADF** (Augmented Dickey-Fuller): hồi quy với hằng số, không xu hướng (`regression='c'`), độ trễ chọn tự động theo AIC.
- **KPSS** (Kwiatkowski-Phillips-Schmidt-Shin): kiểm định dừng mức (`regression='c'`).

Trong trường hợp hai kiểm định cho kết quả **mâu thuẫn** (Case 3: ADF bác bỏ
$H_0$ nhưng KPSS cũng bác bỏ $H_0$), nghiên cứu áp dụng kiểm định
**Zivot-Andrews** (Zivot & Andrews, 1992) làm tiebreaker. Kiểm định ZA mở rộng
ADF bằng cách cho phép **một structural break nội sinh** (endogenous) trong mô
hình hồi quy:

$$y_t = \hat{\mu} + \hat{\theta} \cdot DU_t(\hat{T}_B) + \hat{\beta} \cdot t + \hat{\alpha} \cdot y_{t-1} + \sum_{j=1}^{k} \hat{c}_j \, \Delta y_{t-j} + \hat{e}_t$$

trong đó $DU_t(T_B) = \mathbb{1}[t > T_B]$ là biến giả cho structural break tại
thời điểm $T_B$, và $T_B$ được xác định nội sinh bằng cách tối thiểu hóa
$t(\hat{\alpha})$ trên toàn bộ vị trí khả thi. Nếu ZA bác bỏ $H_0$ (unit root)
tại mức ý nghĩa 5%, chuỗi được kết luận **dừng quanh structural break**
(break-stationary); ngược lại, kết luận giữ trạng thái contradictory và tạm xử
lý như dừng (bảo thủ) nhằm tránh over-differencing.

### 4.1.2. Kết quả kiểm định

**Bảng 4.1: Tổng hợp kết quả kiểm định tính dừng (ADF + KPSS)**

| Biến | ADF (level) | KPSS (level) | Kết luận level | ADF (1st diff) | KPSS (1st diff) | $d(i)$ |
|------|:-----------:|:------------:|:--------------:|:--------------:|:---------------:|:------:|
| ProductionVolume | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] |
| DelayRate | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] |
| OrderDemand | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] |

*Ghi chú: Giá trị tới hạn ADF 5% ≈ −2.870; KPSS 5% = 0.463. \*, \*\*, \*\*\* tương ứng mức ý nghĩa 10%, 5%, 1%.*

### 4.1.3. Nhận xét

[Chạy lại pipeline để cập nhật] — Kết quả kiểm định tính dừng cho 3 biến
ProductionVolume, DelayRate, và OrderDemand sẽ xác định bậc tích hợp $d(i)$
và bậc tích hợp tối đa $d_{max}$.

Nếu tồn tại ít nhất 2 biến I(1) trong hệ thống, kiểm định đồng tích hợp
Johansen sẽ được thực hiện — nếu tồn tại quan hệ cân bằng dài hạn giữa các
biến I(1), mô hình VECM sẽ là lựa chọn phù hợp hơn VAR thuần túy.

---

## 4.2. Kiểm định đồng tích hợp Johansen (Phase 3)

### 4.2.1. Thiết lập kiểm định

Kiểm định đồng tích hợp Johansen (Johansen, 1995) được thực hiện trên hệ thống
3 biến ở mức gốc (levels) với các tham số:

- **Deterministic trend**: Unrestricted constant (`det_order=1`) — cho phép hằng số
  nằm ngoài quan hệ đồng tích hợp (Lütkepohl, 2005, Chương 6).
- **VAR lag order**: $p = 1$ (chọn bằng AIC/BIC; $p = 1$ tương đương $k_{ar\_diff} = 0$
  trong VECM).

### 4.2.2. Kết quả kiểm định Trace và Max-Eigenvalue

**Bảng 4.2: Kiểm định Johansen — Trace test**

| Giả thuyết $H_0$ | Trace statistic | Giá trị tới hạn 5% | Bác bỏ? |
|:-----------------:|:---------------:|:-------------------:|:-------:|
| $r \leq 0$ | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] |
| $r \leq 1$ | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] |

**Bảng 4.3: Kiểm định Johansen — Max-Eigenvalue test**

| Giả thuyết $H_0$ | Max-Eigen statistic | Giá trị tới hạn 5% | Bác bỏ? |
|:-----------------:|:-------------------:|:-------------------:|:-------:|
| $r = 0$ | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] |
| $r = 1$ | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] |

**Eigenvalues**: [Chạy lại pipeline để cập nhật] ($n = 3$ biến, tối đa 3 eigenvalues).

### 4.2.3. Xác định hạng đồng tích hợp

[Chạy lại pipeline để cập nhật] — Kết quả Trace test và Max-Eigenvalue test
sẽ xác định hạng đồng tích hợp $r$ cho hệ thống 3 biến.

Kết quả $0 < r < n = 3$ sẽ xác nhận:
- Tồn tại $r$ vector đồng tích hợp ($r$ quan hệ cân bằng dài hạn) giữa các biến.
- **Route phân tích: VECM** (Vector Error Correction Model) với $r$ error
  correction terms.
- Hệ thống có $n - r$ common stochastic trends (xu hướng ngẫu nhiên chung).

---

## 4.3. Phương trình cân bằng dài hạn — Ma trận $\beta$ (Phase 4)

### 4.3.1. Mô hình VECM và tham số ước lượng

Mô hình VECM được ước lượng với tham số khóa cứng từ Phase 3:

$$\Delta y_t = \alpha \cdot \beta' y_{t-1} + \mu + u_t$$

trong đó:
- $y_t = (\text{ProductionVolume}_t, \text{DelayRate}_t, \text{OrderDemand}_t)'$
- $\alpha$ ($3 \times r$): ma trận tốc độ điều chỉnh (loading matrix)
- $\beta$ ($3 \times r$): ma trận đồng tích hợp (cointegrating vectors)
- $\mu$: hằng số không hạn chế (unrestricted constant)
- $u_t \sim N(0, \Sigma_u)$: nhiễu trắng
- $k_{ar\_diff}$: [Chạy lại pipeline để cập nhật]

### 4.3.2. Ma trận đồng tích hợp $\beta$

**Bảng 4.4: Ma trận $\beta$ (Cointegrating Vectors) — chuẩn hóa Johansen**

| Biến | $\beta_1$ (CE₁) | $\beta_2$ (CE₂) |
|------|:----------------:|:----------------:|
| ProductionVolume | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] |
| DelayRate | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] |
| OrderDemand | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] |

*Ghi chú: Số cột CE phụ thuộc vào hạng đồng tích hợp $r$ xác định từ Phase 3. Bảng trên giả định $r = 2$; nếu $r = 1$ thì chỉ có 1 cột CE.*

### 4.3.3. Phương trình cân bằng dài hạn

[Chạy lại pipeline để cập nhật] — Các error correction terms (ECT) sẽ được
biểu diễn dựa trên hệ 3 biến mới. Dạng kỳ vọng (phụ thuộc vào kết quả
ước lượng thực tế):

$$ECT_1 = f(\text{ProductionVolume}_t, \text{DelayRate}_t, \text{OrderDemand}_t) \approx 0 \tag{4.1}$$

$$ECT_2 = g(\text{ProductionVolume}_t, \text{DelayRate}_t, \text{OrderDemand}_t) \approx 0 \tag{4.2}$$

*Ghi chú: Số phương trình CE phụ thuộc vào hạng đồng tích hợp $r$.*

### 4.3.4. Diễn giải kinh tế

Chuỗi nhân quả kỳ vọng trong hệ 3 biến mới:

$$\text{OrderDemand} \xrightarrow{\text{áp lực cầu}} \text{ProductionVolume} \xrightarrow{\text{quá tải}} \text{DelayRate}$$

**Hiệu ứng áp lực cầu lên sản lượng (Demand-Production Effect):**
Trong dài hạn, khi áp lực đơn hàng (OrderDemand — tổng Quantity từ Sales Order)
tăng, sản lượng thực tế (ProductionVolume — tổng ValuedQty từ NAV Value Entry)
phải tăng theo để đáp ứng cầu. Quan hệ này phản ánh cơ chế truyền dẫn: cầu thị
trường là tín hiệu ngoại sinh kích hoạt quyết định sản xuất.

**Hiệu ứng quá tải giao hàng (Production-Delivery Overload Effect):**
Khi ProductionVolume tăng cao (nhà máy hoạt động gần ngưỡng công suất), tỷ lệ
giao hàng trễ (DelayRate) tăng do tắc nghẽn logistics, thời gian chuyển đổi
(changeover) dài hơn, và lịch giao hàng bị dồn nén. Đây là hiệu ứng quá tải
tương tự như trong hệ thống cũ (OEE → Delay ở phiên bản 4 biến), nhưng giờ
được đo lường trực tiếp qua sản lượng thay vì hiệu suất thiết bị.

[Chạy lại pipeline để cập nhật] — Hệ số $\beta$ cụ thể và mức ý nghĩa thống
kê sẽ được xác định sau khi chạy lại pipeline với dữ liệu 3 biến mới.

---

## 4.4. Tốc độ hiệu chỉnh — Ma trận $\alpha$ (Phase 4)

### 4.4.1. Ước lượng ma trận $\alpha$

**Bảng 4.5: Ma trận $\alpha$ (Speed of Adjustment) với z-statistics và p-values**

| Biến | $\alpha_1$ (← ECT₁) | z-stat | p-value | $\alpha_2$ (← ECT₂) | z-stat | p-value |
|------|:--------------------:|:------:|:-------:|:--------------------:|:------:|:-------:|
| ProductionVolume | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] |
| DelayRate | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] |
| OrderDemand | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] |

*Ghi chú: Số cột $\alpha$ phụ thuộc vào hạng đồng tích hợp $r$. Bảng trên giả định $r = 2$; nếu $r = 1$ thì chỉ có cột $\alpha_1$.*

### 4.4.2. Phương trình hệ thống VECM hoàn chỉnh

Hệ thống VECM 3 phương trình — [Chạy lại pipeline để cập nhật]:

$$\Delta \text{ProductionVolume}_t = \alpha_{11} \cdot ECT_{1,t-1} + [\alpha_{12} \cdot ECT_{2,t-1}] + \mu_1 + u_{1t} \tag{4.3a}$$

$$\Delta \text{DelayRate}_t = \alpha_{21} \cdot ECT_{1,t-1} + [\alpha_{22} \cdot ECT_{2,t-1}] + \mu_2 + u_{2t} \tag{4.3b}$$

$$\Delta \text{OrderDemand}_t = \alpha_{31} \cdot ECT_{1,t-1} + [\alpha_{32} \cdot ECT_{2,t-1}] + \mu_3 + u_{3t} \tag{4.3c}$$

*Ghi chú: Các hệ số $\alpha_{ij}$ và $\mu_i$ sẽ được cập nhật sau khi chạy pipeline. Số lượng ECT phụ thuộc vào $r$.*

### 4.4.3. Phân tích tốc độ hội tụ

**Bảng 4.6: Half-life hội tụ về cân bằng (tuần)**

| Biến ← ECT | Half-life | Ý nghĩa kinh tế |
|-------------|:---------:|------------------|
| ProductionVolume ← ECT₁ | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] |
| DelayRate ← ECT₁ | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] |
| OrderDemand ← ECT₁ | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] |

*Ghi chú: Half-life = $\ln(0.5) / \ln(1 + \alpha_i)$. Công thức áp dụng cho $\alpha_i < 0$ (error-correcting). Số dòng có thể tăng nếu $r > 1$.*

### 4.4.4. Diễn giải kinh tế

**Bất đối xứng tốc độ điều chỉnh ($\alpha$ asymmetry):** [Chạy lại pipeline để
cập nhật] — Kết quả kỳ vọng sẽ bộc lộ cấu trúc phân vai trong hệ thống quản
trị sản xuất theo chuỗi nhân quả OrderDemand → ProductionVolume → DelayRate:

1. **OrderDemand là biến ngoại sinh (exogenous driver):**
   Trong chuỗi nhân quả mới, áp lực cầu từ đơn hàng (OrderDemand) đóng vai trò
   tín hiệu ngoại sinh kích hoạt toàn bộ hệ thống. Nếu $|\alpha|$ của OrderDemand
   nhỏ (half-life dài), điều này xác nhận vai trò weakly exogenous — OrderDemand
   tác động lên các biến khác nhưng bản thân ít bị ảnh hưởng bởi cân bằng nội bộ
   hệ thống sản xuất.

2. **DelayRate là fast responder:**
   Kỳ vọng DelayRate vẫn giữ vai trò biến phản ứng nhanh nhất — khi hệ thống
   lệch khỏi cân bằng (ví dụ ProductionVolume tăng vọt do OrderDemand cao),
   tỷ lệ giao hàng trễ phản ứng gần như tức thời. Delay là triệu chứng (symptom)
   xuất hiện ngay khi hệ thống quá tải.

3. **ProductionVolume là biến trung gian (mediator):**
   ProductionVolume (tổng ValuedQty từ NAV Value Entry) thay thế vai trò của OEE
   trong hệ thống cũ, nhưng với ý nghĩa khác: thay vì đo hiệu suất thiết bị,
   ProductionVolume đo lường sản lượng thực tế — là kết quả trực tiếp của áp lực
   cầu (OrderDemand) và đồng thời là nguyên nhân trực tiếp gây quá tải giao hàng
   (DelayRate).

---

## 4.5. Cross-validation nhân quả: Granger vs. Toda-Yamamoto (Phase 2 & 3b)

### 4.5.1. So sánh hai phương pháp

Nghiên cứu thực hiện đồng thời hai kiểm định nhân quả để cross-validate kết
quả — Granger causality trên chuỗi sai phân (Phase 2) và Toda-Yamamoto trên
chuỗi mức gốc (Phase 3b):

**Bảng 4.7: So sánh Granger Causality vs. Toda-Yamamoto (6 cặp biến)**

| Cặp nhân quả | Granger (sai phân) | Toda-Yamamoto (levels) | Đồng thuận? |
|---------------|:------------------:|:----------------------:|:-----------:|
| OrderDemand → ProductionVolume | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] |
| OrderDemand → DelayRate | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] |
| ProductionVolume → OrderDemand | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] |
| ProductionVolume → DelayRate | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] |
| DelayRate → OrderDemand | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] |
| DelayRate → ProductionVolume | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] |

*Tỷ lệ đồng thuận: [Chạy lại pipeline để cập nhật]. Hệ 3 biến tạo ra $3 \times 2 = 6$ cặp nhân quả có hướng.*

### 4.5.2. Giải thích sự khác biệt

[Chạy lại pipeline để cập nhật] — Phân tích sự đồng thuận/bất đồng giữa hai
phương pháp sẽ được cập nhật dựa trên kết quả 6 cặp biến mới.

- **Granger trên sai phân** chỉ nắm bắt nhân quả **ngắn hạn** (short-run dynamics)
  vì sai phân loại bỏ thông tin dài hạn.

- **Toda-Yamamoto trên levels** bảo toàn thông tin dài hạn, có khả năng phát hiện
  quan hệ nhân quả mà Granger trên sai phân bỏ sót.

- **Cặp nhân quả cốt lõi kỳ vọng:** OrderDemand → ProductionVolume và
  ProductionVolume → DelayRate — đây là hai mắt xích chính trong chuỗi nhân quả
  của phương pháp Hybrid Causal Forecasting. Nếu Toda-Yamamoto xác nhận hai cặp
  này có ý nghĩa thống kê trên levels trong khi Granger trên sai phân yếu hơn,
  điều đó cho thấy tác động nhân quả chủ yếu hoạt động qua **kênh dài hạn**
  (error correction mechanism) — chính xác là cơ chế mà VECM mô hình hóa.

---

## 4.6. Hàm phản ứng xung và Phân rã phương sai (Phase 5)

### 4.6.1. Thiết lập phân tích

Hàm phản ứng xung trực giao hóa (Orthogonalized Impulse Response Function) và
Phân rã phương sai sai số dự báo (Forecast Error Variance Decomposition) được
tính toán dựa trên phân rã Cholesky của ma trận hiệp phương sai innovation $\Sigma_u$
(Lütkepohl, 2005, Mục 2.3.2–2.3.3).

**Cholesky ordering** (ngoại sinh → nội sinh):

$$\text{OrderDemand} \rightarrow \text{ProductionVolume} \rightarrow \text{DelayRate}$$

Thứ tự này phản ánh chuỗi nhân quả kinh tế: OrderDemand (áp lực cầu từ đơn hàng)
là biến ngoại sinh nhất — quyết định bởi thị trường, ít bị ảnh hưởng bởi nội bộ
sản xuất. ProductionVolume (sản lượng thực tế) phản ứng theo cầu nhưng đồng thời
là nguyên nhân gây quá tải. DelayRate (tỷ lệ giao trễ) là biến nội sinh nhất —
triệu chứng cuối cùng của chuỗi truyền dẫn. Khoảng mô phỏng: 12 tuần.

### 4.6.2. Kết quả IRF — Phản ứng của DelayRate

![Hình 4.1: Hàm phản ứng xung — Phản ứng của DelayRate đối với shock từ ProductionVolume và OrderDemand](../../data/processed/figures/irf_delayrate_response.png)

*Hình 4.1: Orthogonalized IRF — phản ứng của DelayRate khi có cú sốc 1 độ lệch chuẩn từ ProductionVolume (trái) và OrderDemand (phải). Vùng tô: khoảng tin cậy 95% (asymptotic SE). Cholesky ordering: OrderDemand → ProductionVolume → DelayRate.*

**Bảng 4.8: IRF — Phản ứng của DelayRate tại các mốc thời gian**

| Tuần | ProductionVolume shock → DelayRate | SE | OrderDemand shock → DelayRate | SE |
|:----:|:---------------------------------:|:--:|:----------------------------:|:--:|
| 0 | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] |
| 1 | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] |
| 4 | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] |
| 8 | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] |
| 12 | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] | [Chạy lại pipeline để cập nhật] |

**Diễn giải:** [Chạy lại pipeline để cập nhật] — Kỳ vọng: khi ProductionVolume
chịu cú sốc cấu trúc dương 1 độ lệch chuẩn (tương đương tăng sản lượng thực tế),
DelayRate sẽ tăng do hiệu ứng quá tải — sản lượng cao dẫn đến tắc nghẽn logistics
và tăng tỷ lệ giao trễ. Hình dạng phản ứng kỳ vọng — shock mạnh ban đầu rồi
phẳng dần — phản ánh cơ chế hiệu chỉnh sai số (error correction). Đối với shock
từ OrderDemand, tác động lên DelayRate có thể gián tiếp qua kênh ProductionVolume
hoặc trực tiếp (nếu áp lực cầu cao vượt năng lực giao hàng ngay cả khi sản lượng
chưa kịp tăng).

### 4.6.3. Kết quả FEVD — Phân rã phương sai Delay Rate

![Hình 4.2: Phân rã phương sai sai số dự báo — Delay Rate](../../data/processed/figures/fevd_delayrate_decomposition.png)

*Hình 4.2: Forecast Error Variance Decomposition (FEVD) cho Delay Rate qua 12 tuần. Stacked area chart thể hiện tỷ lệ đóng góp từ mỗi nguồn shock cấu trúc. Cholesky ordering: OrderDemand → ProductionVolume → DelayRate.*

**Bảng 4.9: FEVD — Tỷ lệ đóng góp vào phương sai Delay Rate (%)**

| Tầm dự báo | Delay Rate | Production Volume | Order Demand |
|:-----------:|:----------:|:-----------------:|:------------:|
| Tuần 1 | _[chạy lại]_ | _[chạy lại]_ | _[chạy lại]_ |
| Tuần 4 | _[chạy lại]_ | _[chạy lại]_ | _[chạy lại]_ |
| Tuần 8 | _[chạy lại]_ | _[chạy lại]_ | _[chạy lại]_ |
| Tuần 12 | _[chạy lại]_ | _[chạy lại]_ | _[chạy lại]_ |

**Diễn giải:** _[Chạy lại pipeline để cập nhật]_ — Kỳ vọng: kết quả FEVD sẽ
cho thấy vai trò nhân quả của ProductionVolume và OrderDemand trong việc giải
thích phương sai sai số dự báo của Delay Rate. Tại tầm dự báo ngắn, phần lớn
phương sai được giải thích bởi chính Delay Rate (inertia ngắn hạn). Khi mở rộng
tầm dự báo, kỳ vọng tỷ phần đóng góp của ProductionVolume và OrderDemand tăng
dần — chứng minh rằng sản lượng và nhu cầu đặt hàng chứa thông tin dự báo bổ
sung (incremental predictive information) mà mô hình đơn biến ARIMA không thể
khai thác.

---

## 4.7. Dự báo VECM và Hàm ý quản trị

### 4.7.1. Kết quả dự báo 4 tuần

**Bảng 4.10: Dự báo VECM 4 tuần (T+1 đến T+4) với khoảng tin cậy 95%**

| Tuần | Production Volume | Delay Rate | Order Demand |
|:----:|:-----------------:|:----------:|:------------:|
| T+1 | _[chạy lại pipeline]_ | _[chạy lại pipeline]_ | _[chạy lại pipeline]_ |
| T+2 | _[chạy lại pipeline]_ | _[chạy lại pipeline]_ | _[chạy lại pipeline]_ |
| T+3 | _[chạy lại pipeline]_ | _[chạy lại pipeline]_ | _[chạy lại pipeline]_ |
| T+4 | _[chạy lại pipeline]_ | _[chạy lại pipeline]_ | _[chạy lại pipeline]_ |

*Ghi chú: CI = 95% confidence interval dựa trên IRF/MA representation (Lütkepohl, 2005, Mục 6.5).*

### 4.7.2. Chẩn đoán mô hình

**Bảng 4.11: Model Diagnostics**

| Chỉ số | Giá trị |
|--------|:-------:|
| Log-Likelihood | _[chạy lại pipeline]_ |
| AIC | _[chạy lại pipeline]_ |
| BIC | _[chạy lại pipeline]_ |
| Quan sát hiệu dụng | _[chạy lại pipeline]_ |
| Bậc tự do/phương trình | _[chạy lại pipeline]_ |
| Tổng tham số | _[chạy lại pipeline — 3 biến]_ |

### 4.7.3. So sánh VECM với mô hình đơn biến

Giá trị cốt lõi của phương pháp Hybrid Causal Forecasting so với dự báo chuỗi
thời gian thuần túy (ARIMA, VAR) được thể hiện qua bốn trụ cột biện luận:

**Bảng 4.12: Bốn trụ cột biện luận — VECM vs. mô hình thuần thống kê**

| Trụ cột | Bằng chứng từ dữ liệu | Mô hình thuần thống kê thiếu gì? |
|---------|------------------------|----------------------------------|
| 1. Đồng tích hợp | $r$ = _[chạy lại pipeline]_ | ARIMA bỏ qua quan hệ dài hạn giữa các biến; VAR trên sai phân mất thông tin levels |
| 2. Nhân quả Toda-Yamamoto | _[chạy lại — kỳ vọng: OrderDemand → ProductionVolume → Delay]_ | VAR không phân biệt hướng nhân quả — coi mọi biến như đối xứng |
| 3. Bất đối xứng $\alpha$ | _[chạy lại — kỳ vọng: bất đối xứng driver vs. responder]_ | ARIMA không có error correction mechanism — không mô hình hóa tốc độ hội tụ |
| 4. FEVD | _[chạy lại — kỳ vọng: ProductionVolume giải thích phần variance DelayRate]_ | Forecast ARIMA không tận dụng incremental predictive information từ biến nhân quả |

### 4.7.4. Hàm ý quản trị

Kết quả phân tích VECM gợi ý các hàm ý quản trị sản xuất sau:

1. **OrderDemand là tín hiệu ngoại sinh:** Nhu cầu đặt hàng (từ Sales Order) là
   biến ngoại sinh nhất trong chuỗi — phản ánh áp lực thị trường mà nhà máy phải
   đáp ứng. Giám sát xu hướng OrderDemand cho phép dự báo sớm áp lực lên sản xuất
   và logistics.

2. **Delay Rate là chỉ báo sớm:** Với tốc độ phản ứng nhanh, sự gia tăng đột ngột
   của Delay Rate là tín hiệu cảnh báo sớm rằng hệ thống đang lệch khỏi cân bằng
   — có thể do sản lượng vượt ngưỡng năng lực hoặc áp lực cầu tăng đột biến.

3. **Ngưỡng sản lượng tối ưu:** Phương trình đồng tích hợp cho phép ước lượng
   ngưỡng ProductionVolume mà tại đó DelayRate bắt đầu tăng đáng kể. Doanh nghiệp
   có thể sử dụng ngưỡng này để cân nhắc giữa việc nhận thêm đơn hàng và duy trì
   chất lượng giao hàng. _[Hệ số cụ thể: chạy lại pipeline]_

4. **Hệ thống cảnh báo dựa trên ECT:** Error correction terms (ECT₁, ECT₂) có
   thể được giám sát theo thời gian thực. Khi $|ECT| > \theta$ (ngưỡng cảnh báo),
   hệ thống đang lệch xa cân bằng dài hạn — cần can thiệp quản trị trước khi
   Delay Rate tự điều chỉnh (vì sự tự điều chỉnh của Delay Rate đồng nghĩa với
   việc khách hàng đã chịu ảnh hưởng giao trễ).

---

## 4.8. Xử lý suy biến hiệp phương sai mẫu nhỏ — Eigenvalue Clamping

### 4.8.1. Bối cảnh vấn đề

Khoảng tin cậy dự báo VECM (Bảng 4.10) được tính dựa trên biểu diễn MA
(Moving Average) của sai số dự báo (Lütkepohl, 2005, Mục 6.5), đòi hỏi phân
rã Cholesky ma trận hiệp phương sai innovation $\Sigma_u \in \mathbb{R}^{3 \times 3}$
ước lượng từ phần dư VECM. Phân rã Cholesky yêu cầu $\Sigma_u$ phải xác định
dương (positive definite), tức mọi eigenvalue $\lambda_i > 0$.

Với cỡ mẫu hiệu dụng $T = 374$ quan sát (hoặc $T \approx 10$ trong bối cảnh
mẫu nhỏ pilot), ma trận $\hat{\Sigma}_u$ ước lượng có thể xuất hiện eigenvalue
cận zero hoặc âm do: (i) thiếu rank (rank deficiency) khi $T$ gần $n$; (ii) lỗi
số học tích lũy (floating-point accumulation) trong quá trình ước lượng MLE.
Trong cả hai trường hợp, Cholesky decomposition thất bại ($\texttt{LinAlgError}$)
và pipeline không thể tạo khoảng tin cậy.

### 4.8.2. Phương pháp Eigenvalue Clamping

Nghiên cứu áp dụng phương pháp **spectral correction** (hiệu chỉnh spectral)
thay vì Ridge regularization ($\Sigma_u + \varepsilon I$) phổ biến trong tài
liệu (Tikhonov, 1943). Quy trình gồm 4 bước:

**Bước 1 — Phân rã spectral:**

$$\hat{\Sigma}_u = V \Lambda V^T, \quad \Lambda = \text{diag}(\lambda_1, \ldots, \lambda_n)$$

sử dụng `numpy.linalg.eigh()` cho ma trận đối xứng — đảm bảo ổn định số học
tốt hơn `numpy.linalg.eig()`.

**Bước 2 — Kẹp eigenvalue (clamping):**

$$\tilde{\lambda}_i = \max\left(\lambda_i, \, \epsilon_{\text{floor}}\right), \quad \epsilon_{\text{floor}} = \max_j |\lambda_j| \times 10^{-8}$$

Mọi eigenvalue $\leq 0$ hoặc quá nhỏ được nâng lên $\epsilon_{\text{floor}}$
— một ngưỡng **tương đối** (relative threshold) so với eigenvalue lớn nhất,
đảm bảo condition number $\kappa(\tilde{\Sigma}_u) \leq 10^8$.

**Bước 3 — Tái tạo:**

$$\tilde{\Sigma}_u = V \cdot \tilde{\Lambda} \cdot V^T$$

Ma trận $\tilde{\Sigma}_u$ đảm bảo xác định dương, đối xứng, và bảo toàn
eigenvector gốc (cấu trúc tương quan giữa các biến).

**Bước 4 — Cholesky:** $\tilde{\Sigma}_u = \tilde{L} \cdot \tilde{L}'$ luôn
thành công.

### 4.8.3. So sánh với Ridge Regularization (Tikhonov)

Phương pháp Ridge ($\hat{\Sigma}_u^{\text{Ridge}} = \hat{\Sigma}_u + \varepsilon I_n$)
được sử dụng rộng rãi nhưng có hai hạn chế trong bối cảnh mẫu nhỏ:

(i) **Tác động toàn cục:** Ridge dịch chuyển toàn bộ spectrum $\lambda_i \to \lambda_i + \varepsilon$, bao gồm cả chiều không suy biến — phóng đại phương sai cho mọi biến, dẫn đến khoảng tin cậy rộng hơn cần thiết.

(ii) **Chọn $\varepsilon$ tùy ý:** Giá trị $\varepsilon$ thường được chọn ad-hoc (thường $10^{-6}$ hoặc $10^{-10}$) mà không phản ánh cấu trúc dữ liệu — quá nhỏ thì không giải quyết được suy biến, quá lớn thì bóp méo $\Sigma_u$.

Eigenvalue Clamping khắc phục cả hai vấn đề: (i) chỉ can thiệp vào chiều vi
phạm, giữ nguyên chiều khỏe mạnh — **tối thiểu can thiệp** (minimal
intervention); (ii) ngưỡng $\epsilon_{\text{floor}}$ được xác định tự động từ
dữ liệu (adaptive), không đòi hỏi tham số ngoại vi. Trong bối cảnh $N = 10$
nơi mỗi phần trăm phương sai đều ảnh hưởng đáng kể đến khoảng tin cậy, tránh
artifact variance inflation là ưu tiên cao.

### 4.8.4. Ghi nhận và minh bạch

Pipeline ghi `WARNING` trong log khi phát hiện eigenvalue $\leq 0$, bao gồm:
giá trị eigenvalue gốc, giá trị sau clamping, và $\epsilon_{\text{floor}}$ được
sử dụng. Quá trình hoàn toàn tự động (self-healing) — không yêu cầu can thiệp
thủ công — đảm bảo pipeline không crash tại bước cuối cùng khi đã hoàn thành
toàn bộ kiểm định econometric trước đó.

---

## Tài liệu tham khảo

- Enders, W. (2014). *Applied Econometric Time Series* (4th ed.). Wiley.
- Johansen, S. (1995). *Likelihood-Based Inference in Cointegrated Vector
  Autoregressive Models*. Oxford University Press.
- Lütkepohl, H. (2005). *New Introduction to Multiple Time Series Analysis*.
  Springer.
- Pfaff, B. (2008). *Analysis of Integrated and Cointegrated Time Series with R*
  (2nd ed.). Springer.
- Sims, C.A. (1980). Macroeconomics and Reality. *Econometrica*, 48(1), 1–48.
- Tikhonov, A. N. (1943). On the stability of inverse problems. *Doklady
  Akademii Nauk SSSR*, 39(5), 195–198.
- Toda, H.Y., & Yamamoto, T. (1995). Statistical Inference in Vector
  Autoregressions with Possibly Integrated Processes. *Journal of Econometrics*,
  66(1–2), 225–250.
- Zivot, E., & Andrews, D. W. K. (1992). Further Evidence on the Great Crash,
  the Oil-Price Shock, and the Unit-Root Hypothesis. *Journal of Business &
  Economic Statistics*, 10(3), 251–270.
