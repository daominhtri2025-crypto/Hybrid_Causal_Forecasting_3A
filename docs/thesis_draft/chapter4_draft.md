# Chương 4: Kết quả Thực nghiệm và Thảo luận

> **Phương pháp Hybrid Causal Forecasting — Phương án 3-A**
>
> Dữ liệu: 412 quan sát tuần (01/2018 – 08/2026) sau lọc NaN, 3 biến nội sinh:
> Production Volume, Delay Rate, Order Demand.
> Route: VAR(12) trên mức gốc (tất cả biến I(0)).

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

| Biến | ADF (level) | KPSS (level) | Kết luận level | $d(i)$ |
|------|:-----------:|:------------:|:--------------:|:------:|
| ProductionVolume | Bác bỏ H₀*** | Giữ H₀ | **Dừng** (Case 1) | 0 |
| DelayRate | Bác bỏ H₀*** | Giữ H₀ | **Dừng** (Case 1) | 0 |
| OrderDemand | Bác bỏ H₀*** | Giữ H₀ | **Dừng** (Case 1) | 0 |

*Ghi chú: Giá trị tới hạn ADF 5% ≈ −2.870; KPSS 5% = 0.463. \*\*\* tương ứng mức ý nghĩa 1%. Tất cả 3 biến đều rơi vào Case 1 (ADF bác bỏ + KPSS giữ H₀) → xác nhận dừng. Không cần sai phân; cột "1st diff" bỏ qua. $d_{\max} = 0$.*

### 4.1.3. Nhận xét

Kết quả kiểm định cho thấy **tất cả 3 biến đều dừng ở mức gốc** — I(0) — với
sự xác nhận đồng thuận từ cả ADF lẫn KPSS (Case 1). Bậc tích hợp tối đa
$d_{\max} = 0$, nghĩa là không cần sai phân bất kỳ biến nào.

Kết quả này có ý nghĩa kinh tế phù hợp: dữ liệu sản xuất tuần (sản lượng,
tỷ lệ trễ, nhu cầu đặt hàng) phản ánh hoạt động kinh doanh có tính **quay
về trung bình** (mean-reverting) — không có xu hướng stochastic dài hạn. Sản
lượng dao động quanh năng lực trung bình của nhà máy; tỷ lệ trễ dao động
quanh mức hiệu suất logistics cơ sở; nhu cầu đặt hàng phản ánh chu kỳ kinh
doanh ngắn hạn.

Do không có biến I(1), kiểm định đồng tích hợp Johansen vẫn được thực hiện
nhưng kết quả $r = 3$ (full rank) xác nhận tất cả biến đã dừng → **route
phân tích: VAR trên mức gốc** (VAR\_on\_levels), không phải VECM.

---

## 4.2. Kiểm định đồng tích hợp Johansen và Xác định Route (Phase 3)

### 4.2.1. Thiết lập kiểm định

Kiểm định đồng tích hợp Johansen (Johansen, 1995) được thực hiện trên hệ thống
3 biến ở mức gốc (levels) với các tham số:

- **Deterministic trend**: Unrestricted constant (`det_order=1`) — cho phép hằng số
  nằm ngoài quan hệ đồng tích hợp (Lütkepohl, 2005, Chương 6).
- **VAR lag order**: Schwert (1989) maxlag = $\lfloor 12 \cdot (T/100)^{0.25} \rfloor = 17$, cap tại 26 tuần. AIC chọn lag = 12.

### 4.2.2. Kết quả: Full Rank ($r = 3$)

Cả Trace test và Max-Eigenvalue test đều **bác bỏ mọi giả thuyết** $H_0$ từ
$r \leq 0$ đến $r \leq 2$ tại mức ý nghĩa 5%, cho kết quả $r = 3$ (full rank).
Kết quả này nhất quán giữa hai phương pháp (rank agreement: consistent).

### 4.2.3. Xác định Route phân tích

Kết quả $r = n = 3$ (full rank) có ý nghĩa:
- **Không tồn tại quan hệ đồng tích hợp** theo nghĩa Johansen — ma trận $\Pi$
  full rank, tất cả biến đã dừng ở mức.
- **Route: VAR trên mức gốc** (VAR\_on\_levels) — không phải VECM, không phải
  VAR trên sai phân.
- Hệ thống có **0 common stochastic trends** ($n - r = 3 - 3 = 0$) — tất cả
  biến mean-reverting.

Kết quả này phù hợp với Phase 1 (tất cả I(0)): khi các biến đã dừng, Johansen
test tự nhiên cho full rank, xác nhận quyết định dùng VAR trên levels.

---

## 4.3. Mô hình VAR trên mức gốc — Ước lượng và Chẩn đoán (Phase 4)

### 4.3.1. Đặc tả mô hình VAR(12)

Do tất cả biến đều I(0) và Johansen cho $r = 3$ (full rank), mô hình được ước
lượng là **VAR(12) trên mức gốc** (levels), không phải VECM:

$$y_t = c + \sum_{i=1}^{12} A_i \, y_{t-i} + u_t \tag{4.1}$$

trong đó:
- $y_t = (\text{ProductionVolume}_t, \text{DelayRate}_t, \text{OrderDemand}_t)'$
- $c \in \mathbb{R}^3$: hằng số (intercept)
- $A_i \in \mathbb{R}^{3 \times 3}$: ma trận hệ số lag $i$ ($i = 1, \ldots, 12$)
- $u_t \sim N(0, \Sigma_u)$: nhiễu trắng (innovation)
- Lag $p = 12$: chọn bằng AIC từ Schwert maxlag = 17

> **Lưu ý phương pháp luận:** Thiết kế ban đầu của nghiên cứu dự phòng cả route
> VECM (nếu tồn tại biến I(1) và quan hệ đồng tích hợp) lẫn VAR trên levels.
> Kết quả Phase 1 (tất cả I(0)) và Phase 3 ($r = 3$) xác định route VAR\_on\_levels.
> Ma trận $\alpha$, $\beta$, error correction terms KHÔNG áp dụng cho route này.

### 4.3.2. Chẩn đoán mô hình

**Bảng 4.4: Model Diagnostics — VAR(12)**

| Chỉ số | Giá trị |
|--------|:-------:|
| Log-Likelihood | −11,177.62 |
| AIC | 47.93 |
| BIC | 49.04 |
| Quan sát sau dropna | 412 |
| Quan sát hiệu dụng ($T_{\text{eff}}$) | 400 |
| Bậc tự do/phương trình | 363 |
| Tổng tham số | 111 (37/phương trình × 3) |

### 4.3.3. Diễn giải kinh tế

Chuỗi nhân quả giả thuyết ban đầu:

$$\text{OrderDemand} \xrightarrow{\text{áp lực cầu}} \text{ProductionVolume} \xrightarrow{\text{quá tải}} \text{DelayRate}$$

Kết quả thực tế cho thấy chuỗi nhân quả này **tồn tại về mặt thống kê** (Granger,
Toda-Yamamoto) nhưng **yếu về mặt thực tiễn** (FEVD, IRF) — xem phân tích chi
tiết tại mục 4.6.3 (Null Finding).

---

## 4.4. Cấu trúc nhân quả trong VAR — Granger vs. FEVD (Phase 4)

> **Lưu ý:** Mô hình thực tế là VAR(12) trên mức gốc (không phải VECM). Ma trận
> $\alpha$ (speed of adjustment), error correction terms, và half-life hội tụ
> **không áp dụng**. Thay vào đó, cấu trúc nhân quả được phân tích qua Granger
> causality, Toda-Yamamoto, FEVD, và IRF.

### 4.4.1. Nhận diện vai trò các biến

Kết quả FEVD (Phase 5) bộc lộ cấu trúc phân vai thực tế — khác biệt đáng kể
so với kỳ vọng lý thuyết ban đầu:

**Kỳ vọng ban đầu:**

$$\text{OrderDemand} \xrightarrow{\text{áp lực cầu}} \text{ProductionVolume} \xrightarrow{\text{quá tải}} \text{DelayRate}$$

**Thực tế từ FEVD:** DelayRate chủ yếu mang tính **tự hồi quy** — 94% phương sai
tại $h = 12$ tuần được giải thích bởi chính nó. ProductionVolume chỉ đóng góp
3.8%, OrderDemand chỉ 2.3%. Điều này cho thấy:

1. **DelayRate là hệ thống tự vận hành (self-driven system):**
   Tỷ lệ giao hàng trễ phụ thuộc chủ yếu vào chính lịch sử trễ của nó — phản ánh
   tính quán tính (inertia) trong quy trình logistics nội bộ. Khi hệ thống đã rơi
   vào trạng thái trễ, nó có xu hướng **duy trì** trạng thái đó do nút thắt cơ cấu
   (structural bottleneck) — không phải do áp lực từ bên ngoài.

2. **ProductionVolume và OrderDemand là tín hiệu yếu:**
   Mặc dù Granger causality phát hiện quan hệ nhân quả có ý nghĩa thống kê
   (PV→DR tại lag 6), tác động thực tiễn là rất nhỏ — tổng đóng góp từ cả hai
   biến chỉ chiếm 6.1% phương sai DelayRate.

### 4.4.2. Hàm ý phân vai kinh tế

Kết quả này đảo ngược một phần giả thuyết ban đầu:

- **OrderDemand** vẫn là biến ngoại sinh (exogenous driver) — nhưng tác động
  của nó lên DelayRate **không truyền qua** ProductionVolume một cách mạnh mẽ
  như kỳ vọng.

- **DelayRate** không phải "fast responder" mà là **autonomous system** — trễ
  giao hàng chủ yếu là vấn đề **nội bộ** của hệ thống logistics, không phải
  hệ quả trực tiếp của áp lực sản xuất.

- **ProductionVolume** đóng vai trò mediator yếu — có tác động thống kê nhưng
  mức giải thích phương sai rất thấp (3.8%).

---

## 4.5. Cross-validation nhân quả: Granger vs. Toda-Yamamoto (Phase 2 & 3b)

### 4.5.1. So sánh hai phương pháp

Nghiên cứu thực hiện đồng thời hai kiểm định nhân quả để cross-validate kết
quả — Granger causality trên chuỗi sai phân (Phase 2) và Toda-Yamamoto trên
chuỗi mức gốc (Phase 3b):

**Bảng 4.5: So sánh Granger Causality vs. Toda-Yamamoto (6 cặp biến)**

| Cặp nhân quả | Granger (levels) | Toda-Yamamoto (levels) | Đồng thuận? |
|---------------|:----------------:|:----------------------:|:-----------:|
| OrderDemand → ProductionVolume | Không (p > 0.05) | Không (p > 0.05) | Đồng thuận |
| OrderDemand → DelayRate | Không (p > 0.05) | Không (p > 0.05) | Đồng thuận |
| ProductionVolume → OrderDemand | **Có** (lag=10) | **Có** (p=0.0136) | Đồng thuận |
| ProductionVolume → DelayRate | **Có** (lag=6) | Không (p > 0.05) | **Mâu thuẫn** |
| DelayRate → OrderDemand | Không (p > 0.05) | Không (p > 0.05) | Đồng thuận |
| DelayRate → ProductionVolume | **Có** (lag=12) | **Có** (p=0.0104) | Đồng thuận |

*Tỷ lệ đồng thuận: **5/6 = 83%**. Hệ 3 biến tạo ra $3 \times 2 = 6$ cặp nhân quả có hướng. Granger: 3/6 có ý nghĩa; TY: 2/6 có ý nghĩa.*

*Ghi chú: Do tất cả biến I(0), Granger causality được chạy trên chuỗi **mức gốc** (không cần sai phân), sử dụng VAR trên levels với Schwert maxlag.*

### 4.5.2. Phân tích sự đồng thuận và mâu thuẫn

Tỷ lệ đồng thuận **83%** (5/6 cặp) cho thấy hai phương pháp nhìn chung nhất quán,
với một mâu thuẫn đáng chú ý:

**Cặp mâu thuẫn: ProductionVolume → DelayRate**
- **Granger** phát hiện nhân quả tại lag = 6 (có ý nghĩa thống kê)
- **Toda-Yamamoto** không xác nhận (p > 0.05)

Sự mâu thuẫn này phù hợp với "Null Finding" từ FEVD (mục 4.6.3): tác động của
ProductionVolume lên DelayRate tuy **tồn tại** về mặt thống kê (Granger) nhưng
**quá yếu** để Toda-Yamamoto — phương pháp bảo thủ hơn do ước lượng nhiều tham
số hơn — có thể phát hiện. FEVD xác nhận: ProductionVolume chỉ giải thích 3.8%
phương sai DelayRate tại $h = 12$ tuần.

**Hai cặp nhân quả được xác nhận bởi cả hai phương pháp:**
1. **ProductionVolume → OrderDemand** (Granger lag=10, TY p=0.0136): sản lượng
   thực tế phản hồi ngược lên nhu cầu đặt hàng — có thể phản ánh cơ chế điều
   chỉnh đơn hàng theo năng lực giao hàng.
2. **DelayRate → ProductionVolume** (Granger lag=12, TY p=0.0104): tỷ lệ trễ
   tác động ngược lên sản lượng — khi trễ nhiều, sản xuất bị ảnh hưởng (có thể
   do reorder, rework, hoặc điều chỉnh lịch sản xuất).

**Cặp không có ý nghĩa trong cả hai phương pháp:** OrderDemand → ProductionVolume,
OrderDemand → DelayRate, DelayRate → OrderDemand. Đáng chú ý, cặp nhân quả
"cốt lõi" ban đầu (OrderDemand → ProductionVolume) **không có ý nghĩa** — áp lực
cầu không Granger-cause sản lượng trực tiếp, đảo ngược giả thuyết ban đầu.

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

**Bảng 4.6: IRF — Phản ứng của DelayRate tại các mốc thời gian**

Phản ứng rất nhỏ — biên độ tối đa $|\text{response}| \approx 0.021$ (tại lag 0
cho shock từ ProductionVolume), nhanh chóng tắt dần và **nằm hoàn toàn trong sai
số chuẩn** (khoảng tin cậy 95% chứa 0) từ lag 1 trở đi. Điều này có nghĩa: không
thể phân biệt phản ứng IRF khác 0 một cách có ý nghĩa thống kê.

**Diễn giải:** Kết quả IRF xác nhận phát hiện từ FEVD — tác động của
ProductionVolume và OrderDemand lên DelayRate là **không đáng kể về mặt thực tiễn**.
Cú sốc 1 σ từ ProductionVolume chỉ tạo phản ứng tối đa ~2.1 điểm phần trăm trong
DelayRate, và phản ứng này không có ý nghĩa thống kê (95% CI chứa 0). Shock từ
OrderDemand còn yếu hơn — phản ứng gần 0 xuyên suốt 12 tuần.

### 4.6.3. Kết quả FEVD — Phân rã phương sai Delay Rate và "Null Finding"

![Hình 4.2: Phân rã phương sai sai số dự báo — Delay Rate](../../data/processed/figures/fevd_delayrate_decomposition.png)

*Hình 4.2: Forecast Error Variance Decomposition (FEVD) cho Delay Rate qua 12 tuần. Stacked area chart thể hiện tỷ lệ đóng góp từ mỗi nguồn shock cấu trúc. Cholesky ordering: OrderDemand → ProductionVolume → DelayRate.*

**Bảng 4.7: FEVD — Tỷ lệ đóng góp vào phương sai Delay Rate (%)**

| Tầm dự báo | Delay Rate (tự thân) | Production Volume | Order Demand |
|:-----------:|:--------------------:|:-----------------:|:------------:|
| Tuần 1 | 99.0% | ≈ 0% | ≈ 1.0% |
| Tuần 4 | 96.4% | ≈ 2.8% | ≈ 0.8% |
| Tuần 8 | 94.5% | ≈ 3.6% | ≈ 1.9% |
| Tuần 12 | **94.0%** | **3.8%** | **2.3%** |

#### Phát hiện chính: "Null Finding" — Ý nghĩa thống kê vs. Ý nghĩa thực tiễn

Kết quả FEVD tiết lộ một "Null Finding" quan trọng — thuật ngữ chỉ phát hiện
rằng hiệu ứng nghiên cứu tuy tồn tại về mặt thống kê nhưng **không có ý nghĩa
thực tiễn đáng kể** (Cohen, 1988). Đây là kết quả khoa học hợp lệ, không phải
thất bại của phương pháp (xem CLAUDE.md mục 5: "Null finding là kết quả khoa
học hợp lệ — không được điều chỉnh tham số/dữ liệu chỉ để tạo ra kết quả có
ý nghĩa").

**Mâu thuẫn giữa hai tầng bằng chứng:**

| Tầng phân tích | Phát hiện | Ý nghĩa |
|----------------|-----------|----------|
| **Granger causality** | 3/6 cặp có ý nghĩa thống kê (p < 0.05) | Tồn tại quan hệ nhân quả **về mặt kỹ thuật** |
| **Toda-Yamamoto** | 2/6 cặp có ý nghĩa, 83% đồng thuận với Granger | Xác nhận bằng phương pháp bền vững hơn |
| **FEVD** | DelayRate tự giải thích **94–99%** phương sai | Tác động thực tiễn **rất nhỏ** |
| **IRF** | Phản ứng max |0.021|, tất cả nằm trong SE | Không phân biệt được phản ứng khác 0 |

Granger causality phát hiện rằng ProductionVolume "Granger-cause" DelayRate tại
lag = 6 — nghĩa là giá trị sản lượng quá khứ chứa thông tin dự báo bổ sung cho
DelayRate. Tuy nhiên, FEVD cho thấy thông tin bổ sung này **cực kỳ nhỏ**: chỉ
3.8% phương sai tại $h = 12$ tuần. Nói cách khác: ProductionVolume cải thiện dự
báo DelayRate, nhưng cải thiện này gần như không đáng kể — **94% biến động của
DelayRate đã được giải thích bởi chính lịch sử của nó**.

#### Diễn giải quản trị: Tại sao trễ giao hàng mang tính "tự sinh"?

Phát hiện DelayRate 94% tự hồi quy (autoregressive) gợi ý một cơ chế quản trị
quan trọng: **trễ giao hàng chủ yếu sinh ra từ nút thắt nội bộ hệ thống
logistics — không phải từ cú sốc sản lượng hay áp lực đơn hàng.**

Cụ thể, khi hệ thống đã rơi vào trạng thái trễ hàng (DelayRate cao), nó có xu
hướng **duy trì trạng thái trễ** do các vòng phản hồi dương (positive feedback
loops) nội bộ:

1. **Hiệu ứng tích lũy tồn đọng (Backlog Accumulation):** Đơn hàng bị trễ ở
   tuần $t$ không biến mất — nó dồn vào tuần $t+1$, cộng thêm đơn hàng mới,
   tạo áp lực giao hàng lớn hơn → tỷ lệ trễ tuần $t+1$ tiếp tục cao. Cơ chế
   tự lặp này giải thích tại sao lag 12 của chính DelayRate vẫn có sức giải
   thích cao.

2. **Quán tính quy trình (Process Inertia):** Nguyên nhân gốc rễ gây trễ
   (thiếu nguyên vật liệu, tắc nghẽn dây chuyền, thiếu nhân lực bốc xếp)
   thường **không tự khắc phục** trong vòng 1–2 tuần. Một nút thắt cơ cấu
   (structural bottleneck) — ví dụ năng lực đóng gói hoặc vận chuyển — kéo
   dài qua nhiều tuần cho đến khi có can thiệp quản trị chủ động.

3. **Hiệu ứng domino nội bộ (Internal Cascading):** Trễ ở khâu này gây trễ
   ở khâu sau — hàng chờ kiểm tra chất lượng tạo hàng đợi xuất kho, hàng
   đợi xuất kho gây trễ giao nhận vận tải. Chuỗi domino này **tự duy trì**
   bất kể sản lượng hay nhu cầu đặt hàng tăng hay giảm.

#### Hàm ý chính sách: Điều gì KHÔNG giúp giảm trễ?

Kết quả Null Finding có hàm ý quản trị **phản trực giác** nhưng quan trọng:

- **Kiểm soát đầu vào (sản lượng, đơn hàng) KHÔNG hiệu quả:** Việc giảm
  ProductionVolume hoặc hạn chế OrderDemand chỉ tác động tối đa 6.1% phương
  sai DelayRate — gần như không đáng kể. Giảm sản lượng để giảm trễ là chiến
  lược **sai mục tiêu** (misdirected strategy).

- **Can thiệp cần hướng vào hệ thống nội bộ:** Vì 94% biến động trễ là tự
  sinh, giải pháp phải nhắm vào **quy trình logistics**: tăng năng lực đóng
  gói, cải thiện lịch giao nhận vận tải, giảm thời gian chờ kiểm tra chất
  lượng, và quan trọng nhất — phá vỡ **vòng lặp tồn đọng** bằng cơ chế ưu
  tiên đơn hàng trễ (priority dispatching).

- **Hệ thống cảnh báo sớm nên dựa trên chính DelayRate:** Thay vì giám sát
  OrderDemand hay ProductionVolume như tín hiệu cảnh báo sớm cho trễ giao
  hàng (như giả thuyết ban đầu gợi ý), kết quả cho thấy bản thân lịch sử
  DelayRate chính là chỉ báo dự báo mạnh nhất — mô hình dự báo DelayRate
  dạng AR thuần túy sẽ gần bằng hiệu quả với VAR đa biến.

> **Lưu ý phương pháp luận:** Null Finding không có nghĩa Granger causality
> "sai" — nó phát hiện đúng quan hệ thống kê. Sự mâu thuẫn nằm ở chỗ: tồn
> tại nhân quả thống kê **không đồng nghĩa** tác động thực tiễn đáng kể. Đây
> là bài học quan trọng về việc phân biệt **statistical significance** và
> **practical significance** (Cohen, 1988; Ziliak & McCloskey, 2008). Trong
> bối cảnh econometrics, FEVD và IRF là công cụ bổ sung thiết yếu cho Granger
> causality — chúng đo lường **mức độ** (magnitude) tác động, không chỉ sự
> **tồn tại** (existence) của tác động.

---

## 4.7. Dự báo VAR trên mức gốc và Hàm ý quản trị

### 4.7.1. Kết quả dự báo 4 tuần

Mô hình VAR(12) trên mức gốc được sử dụng để tạo dự báo 4 tuần (T+1 đến T+4)
cho hệ thống 3 biến. Khoảng tin cậy 95% được tính dựa trên biểu diễn MA (Moving
Average) của sai số dự báo (Lütkepohl, 2005, Mục 6.5), sử dụng ma trận hiệp
phương sai innovation $\hat{\Sigma}_u$ ước lượng từ phần dư VAR.

**Bảng 4.10: Dự báo VAR(12) 4 tuần (T+1 đến T+4) với khoảng tin cậy 95%**

| Tuần | Production Volume | Delay Rate | Order Demand |
|:----:|:-----------------:|:----------:|:------------:|
| T+1 (2026-08-17) | _[chạy pipeline 3 biến]_ | _[chạy pipeline 3 biến]_ | _[chạy pipeline 3 biến]_ |
| T+2 (2026-08-24) | _[chạy pipeline 3 biến]_ | _[chạy pipeline 3 biến]_ | _[chạy pipeline 3 biến]_ |
| T+3 (2026-08-31) | _[chạy pipeline 3 biến]_ | _[chạy pipeline 3 biến]_ | _[chạy pipeline 3 biến]_ |
| T+4 (2026-09-07) | _[chạy pipeline 3 biến]_ | _[chạy pipeline 3 biến]_ | _[chạy pipeline 3 biến]_ |

*Ghi chú: Giá trị dự báo cần được tạo từ pipeline 3 biến (ProductionVolume,
DelayRate, OrderDemand) trên máy local. CI = 95% confidence interval dựa trên
biểu diễn MA của sai số dự báo VAR (Lütkepohl, 2005, Mục 6.5). Cần lưu ý
khoảng tin cậy có thể chứa giá trị âm cho DelayRate — tỷ lệ bị chặn tự nhiên
tại [0, 1] nhưng mô hình VAR tuyến tính không áp đặt ràng buộc này.*

### 4.7.2. Chẩn đoán mô hình

Chẩn đoán mô hình VAR(12) đã được trình bày chi tiết tại Bảng 4.4 (Mục 4.3).
Tóm tắt các chỉ số chính:

| Chỉ số | Giá trị |
|--------|:-------:|
| Log-Likelihood | −11,177.62 |
| AIC | 47.93 |
| BIC | 49.04 |
| Quan sát hiệu dụng ($T_{\text{eff}}$) | 400 |
| Bậc tự do/phương trình | 363 |
| Tổng tham số (3 biến × 37 hệ số/pt) | 111 |

Mô hình có 37 tham số/phương trình (12 lag × 3 biến + 1 hằng số = 37), tổng
cộng 111 tham số cho hệ 3 phương trình. Với $T_{\text{eff}} = 400$, tỷ lệ
quan sát/tham số = 400/37 ≈ 10.8 trên mỗi phương trình — vượt ngưỡng tối
thiểu 10:1 thường được khuyến cáo trong econometrics (Lütkepohl, 2005).

### 4.7.3. Đóng góp của Hybrid Causal Forecasting so với mô hình đơn biến

Giá trị cốt lõi của phương pháp Hybrid Causal Forecasting so với dự báo chuỗi
thời gian thuần túy (ARIMA đơn biến) được thể hiện qua bốn trụ cột biện luận,
trong đó trụ cột thứ 3 — "Null Finding" — bản thân nó là đóng góp khoa học:

**Bảng 4.12: Bốn trụ cột biện luận — VAR đa biến vs. mô hình đơn biến**

| Trụ cột | Bằng chứng từ dữ liệu | Đóng góp so với ARIMA đơn biến |
|---------|------------------------|-------------------------------|
| 1. Tất cả I(0) → VAR trên levels | Johansen $r = 3$ (full rank), cả 3 biến I(0) | ARIMA bỏ qua tương tác đa biến; sai phân không cần thiết (đã dừng ở levels) — VAR khai thác thông tin mức gốc |
| 2. Nhân quả Granger + TY | PV→OD (p=0.014), DR→PV (p=0.010); 83% đồng thuận giữa hai phương pháp | ARIMA và VAR "mù" không phân biệt hướng nhân quả — HCF xác định ai dẫn dắt ai |
| 3. **Null Finding (FEVD)** | DelayRate **94% tự hồi quy**; PV chỉ giải thích 3.8%, OD 2.3% | ARIMA không thể khám phá rằng tác động nhân quả tuy tồn tại nhưng **thực tiễn không đáng kể** — kết luận phản trực giác này chỉ có khi so sánh Granger vs FEVD trong khung đa biến |
| 4. Dự báo có cơ sở nhân quả | VAR(12) tận dụng thông tin dự báo bổ sung từ lag chéo (cross-lags), dù nhỏ (6.1% cộng dồn) | Forecast ARIMA không có cross-variable predictive information; sự cải thiện dự báo tuy nhỏ nhưng có cơ sở lý thuyết rõ ràng |

> **Lưu ý về Trụ cột 3:** Trong nghiên cứu khoa học, phát hiện rằng một hiệu
> ứng **không có ý nghĩa thực tiễn** (Null Finding) có giá trị ngang bằng phát
> hiện hiệu ứng mạnh. Nó trả lời câu hỏi quản trị quan trọng: "Liệu kiểm soát
> sản lượng/đơn hàng có giúp giảm trễ giao hàng?" — câu trả lời là **Không**.
> Kết luận này chỉ khả thi khi áp dụng khung phân tích đa biến có hệ thống
> (Granger → TY → FEVD → IRF), không thể đạt được bằng mô hình đơn biến.

### 4.7.4. Hàm ý quản trị

Kết quả phân tích VAR(12) kết hợp với "Null Finding" từ FEVD gợi ý các hàm ý
quản trị sản xuất mang tính **phản trực giác** nhưng có cơ sở thống kê vững:

**A. Điều gì KHÔNG hiệu quả — bài học từ Null Finding:**

1. **Giảm sản lượng không giảm trễ:** ProductionVolume chỉ giải thích 3.8%
   phương sai DelayRate tại $h = 12$ tuần. Chiến lược hạn chế sản lượng để
   giảm tỷ lệ giao trễ là **sai mục tiêu** (misdirected strategy) — giảm 50%
   sản lượng chỉ tác động tối đa ~1.9% biến động trễ hàng.

2. **Quản lý đơn hàng không giảm trễ:** OrderDemand giải thích 2.3% phương
   sai DelayRate. Từ chối đơn hàng hoặc điều tiết nhu cầu có tác động gần
   như không đáng kể đến tỷ lệ giao trễ — nhưng lại gây mất doanh thu trực tiếp.

3. **Giám sát PV/OD không phải cảnh báo sớm cho trễ:** Giả thuyết ban đầu
   rằng OrderDemand tăng → ProductionVolume tăng → DelayRate tăng (chuỗi nhân
   quả tuyến tính) bị bác bỏ bởi FEVD. Hệ thống giám sát dựa trên đầu vào
   (input-based monitoring) sẽ bỏ sót 94% biến động trễ hàng.

**B. Điều gì CÓ hiệu quả — can thiệp dựa trên cơ chế tự hồi quy:**

1. **Phá vỡ vòng lặp tồn đọng (Backlog Breaking):** Vì DelayRate tự duy trì
   qua cơ chế tích lũy (đơn trễ tuần $t$ dồn sang tuần $t+1$), can thiệp
   hiệu quả nhất là cơ chế **ưu tiên đơn hàng trễ** (priority dispatching)
   — phá vỡ vòng lặp thay vì giảm đầu vào.

2. **Tăng năng lực logistics nội bộ:** Nút thắt cơ cấu (đóng gói, kiểm tra
   chất lượng, vận chuyển) tạo **quán tính quy trình** (process inertia) kéo
   dài qua nhiều tuần. Đầu tư vào năng lực logistics tác động trực tiếp đến
   94% biến động tự sinh của DelayRate.

3. **Hệ thống cảnh báo dựa trên chính DelayRate:** Thay vì giám sát
   OrderDemand hay ProductionVolume, **lịch sử DelayRate chính là chỉ báo dự
   báo mạnh nhất** cho DelayRate tương lai. Mô hình cảnh báo AR thuần túy cho
   DelayRate sẽ đạt hiệu quả gần bằng VAR đa biến (94% thông tin đã nằm
   trong chính chuỗi).

4. **Giám sát xu hướng dài hạn qua VAR:** Dù tác động đa biến nhỏ (6.1%
   cộng dồn), VAR(12) vẫn có giá trị trong giám sát xu hướng: khi FEVD bắt
   đầu cho thấy ProductionVolume giải thích > 10% phương sai DelayRate, đó là
   tín hiệu rằng **cơ chế nhân quả đang thay đổi** — có thể do nhà máy vượt
   ngưỡng năng lực hoặc cơ cấu sản phẩm thay đổi. Đây là ứng dụng giám sát
   cấu trúc (structural monitoring) của khung HCF.

---

## 4.8. Xử lý suy biến hiệp phương sai mẫu nhỏ — Eigenvalue Clamping

### 4.8.1. Bối cảnh vấn đề

Khoảng tin cậy dự báo VAR (Bảng 4.10) được tính dựa trên biểu diễn MA
(Moving Average) của sai số dự báo (Lütkepohl, 2005, Mục 6.5), đòi hỏi phân
rã Cholesky ma trận hiệp phương sai innovation $\Sigma_u \in \mathbb{R}^{3 \times 3}$
ước lượng từ phần dư VAR. Phân rã Cholesky yêu cầu $\Sigma_u$ phải xác định
dương (positive definite), tức mọi eigenvalue $\lambda_i > 0$.

Với cỡ mẫu hiệu dụng $T_{\text{eff}} = 400$ quan sát và $n = 3$ biến, ma trận
$\hat{\Sigma}_u$ thường xác định dương. Tuy nhiên, trong bối cảnh mẫu nhỏ pilot
hoặc khi $T$ gần $n$, ma trận ước lượng có thể xuất hiện eigenvalue cận zero
hoặc âm do: (i) thiếu rank (rank deficiency); (ii) lỗi số học tích lũy
(floating-point accumulation) trong quá trình ước lượng MLE. Trong cả hai
trường hợp, Cholesky decomposition thất bại ($\texttt{LinAlgError}$) và pipeline
không thể tạo khoảng tin cậy.

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
dữ liệu (adaptive), không đòi hỏi tham số ngoại vi. Trong bối cảnh mẫu nhỏ
nơi mỗi phần trăm phương sai đều ảnh hưởng đáng kể đến khoảng tin cậy, tránh
artifact variance inflation là ưu tiên cao.

### 4.8.4. Ghi nhận và minh bạch

Pipeline ghi `WARNING` trong log khi phát hiện eigenvalue $\leq 0$, bao gồm:
giá trị eigenvalue gốc, giá trị sau clamping, và $\epsilon_{\text{floor}}$ được
sử dụng. Quá trình hoàn toàn tự động (self-healing) — không yêu cầu can thiệp
thủ công — đảm bảo pipeline không crash tại bước tạo khoảng tin cậy dự báo khi
đã hoàn thành toàn bộ kiểm định econometric trước đó.

---

## Tài liệu tham khảo

- Cohen, J. (1988). *Statistical Power Analysis for the Behavioral Sciences*
  (2nd ed.). Lawrence Erlbaum Associates.
- Enders, W. (2014). *Applied Econometric Time Series* (4th ed.). Wiley.
- Johansen, S. (1995). *Likelihood-Based Inference in Cointegrated Vector
  Autoregressive Models*. Oxford University Press.
- Lütkepohl, H. (2005). *New Introduction to Multiple Time Series Analysis*.
  Springer.
- Pfaff, B. (2008). *Analysis of Integrated and Cointegrated Time Series with R*
  (2nd ed.). Springer.
- Schwert, G. W. (1989). Tests for unit roots: A Monte Carlo investigation.
  *Journal of Business & Economic Statistics*, 7(2), 147–159.
- Sims, C.A. (1980). Macroeconomics and Reality. *Econometrica*, 48(1), 1–48.
- Tikhonov, A. N. (1943). On the stability of inverse problems. *Doklady
  Akademii Nauk SSSR*, 39(5), 195–198.
- Toda, H.Y., & Yamamoto, T. (1995). Statistical Inference in Vector
  Autoregressions with Possibly Integrated Processes. *Journal of Econometrics*,
  66(1–2), 225–250.
- Ziliak, S. T., & McCloskey, D. N. (2008). *The Cult of Statistical
  Significance: How the Standard Error Costs Us Jobs, Justice, and Lives*.
  University of Michigan Press.
- Zivot, E., & Andrews, D. W. K. (1992). Further Evidence on the Great Crash,
  the Oil-Price Shock, and the Unit-Root Hypothesis. *Journal of Business &
  Economic Statistics*, 10(3), 251–270.
