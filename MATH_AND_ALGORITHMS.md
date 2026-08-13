# MATH_AND_ALGORITHMS.md — Chi tiết Toán học & Thuật toán

> Tài liệu kỹ thuật chuyên sâu trình bày **tất cả công thức toán học** được sử dụng
> trong pipeline dự báo nhân quả hỗn hợp 4 tầng (Hybrid Causal Forecasting — Phương án 3-A).
>
> **Hệ thống 3 biến:** ProductionVolume, DelayRate, OrderDemand.
> **Chuỗi nhân quả:** OrderDemand (áp lực cầu) → ProductionVolume (sản lượng) → DelayRate (tỷ lệ trễ giao hàng).
>
> Mọi công thức đều được trích xuất trực tiếp từ mã nguồn đã chạy, không có giá trị
> nào bị hallucinate hay hard-code ngoài kết quả thực tế.

---

## 1. Tầng 1 — Raw Data Extraction (Khai thác Dữ liệu Gốc)

### 1.1. Jaccard Index — Đo lường Độ trùng lặp OrderNo

Khi trích xuất dữ liệu từ nhiều bảng SQL Server trong cùng một snapshot, cần đảm bảo
tính **nhất quán đồng thời** (temporal consistency). Pipeline sử dụng **Jaccard Index**
(Jaccard, 1901) để đo tỉ lệ khớp `OrderNo` giữa các file (áp dụng cho các file có
cột `OrderNo` chung):

$$
J(A, B, C) = \frac{|A \cap B \cap C|}{|A \cup B \cup C|}
$$

Trong đó:
- $A, B, C$: tập hợp `OrderNo` riêng biệt (distinct) từ mỗi file CSV.
- $|A \cap B \cap C|$: số `OrderNo` xuất hiện trong **cả 3** file (giao).
- $|A \cup B \cup C|$: tổng số `OrderNo` phân biệt trên **bất kỳ** file nào (hợp).

**Ngưỡng cảnh báo:** Nếu $J < 0.95$ (tỉ lệ khớp dưới 95%), Tầng 1 ghi `WARNING` —
dấu hiệu snapshot không đồng thời hoặc dữ liệu bất thường.

Trường hợp tổng quát (chỉ 2 file có cột `OrderNo`):

$$
J(A, B) = \frac{|A \cap B|}{|A \cup B|}
$$

> **Tính chất:** $J \in [0, 1]$; $J = 1$ khi 3 tập hoàn toàn trùng khớp;
> $J = 0$ khi không có phần tử chung nào.

### 1.2. ProductionVolume — Sản lượng Sản xuất Thực tế

**ProductionVolume** đo tổng sản lượng sản xuất thực tế (valued quantity) theo tuần,
phản ánh **throughput** (năng lực xử lý) của hệ thống sản xuất. Đây là biến trung
gian trong chuỗi nhân quả: OrderDemand → **ProductionVolume** → DelayRate.

**Công thức tổng hợp:**

$$
\text{ProductionVolume}_{\text{week}} = \sum_{i \in \mathcal{W}} \text{ValuedQty}_i
$$

Trong đó:
- $\mathcal{W}$: tập các bút toán giá trị (Value Entry) thuộc tuần đang xét.
- $\text{ValuedQty}_i$: trường `[Valued Quantity]` của bút toán thứ $i$ — số lượng
  sản phẩm đã được định giá (phản ánh sản lượng thực tế đã hoàn thành và ghi nhận
  vào sổ kế toán).

**Nguồn dữ liệu SQL (Dynamics NAV — CSDL QTDN):**
- `[Value Entry]` (NAV Table 5802): bảng bút toán giá trị, ghi nhận mọi giao dịch
  ảnh hưởng đến giá trị hàng tồn kho.
- Filter: `[Source Type] IN (3, 4)` — chỉ lấy bút toán có nguồn từ:
  - `3` = Work Center (Trung tâm gia công)
  - `4` = Machine Center (Trung tâm máy)
  Hai loại này đảm bảo chỉ tính sản lượng từ hoạt động sản xuất, loại trừ các
  bút toán mua hàng, bán hàng, hay điều chỉnh tồn kho.
- Nhóm theo: `[Posting Date]` → chuyển đổi sang tuần (Monday-based, xem mục 2.5).

**Miền giá trị:** $\text{ProductionVolume} \geq 0$ (tổng sản lượng, đơn vị: sản phẩm).
Tuần không có hoạt động sản xuất → $\text{ProductionVolume} = 0$.

> **So sánh với OEE (phiên bản trước):** Phiên bản trước sử dụng chỉ số OEE
> (Overall Equipment Effectiveness, Nakajima, 1988) với phân rã A x P x Q.
> Tuy nhiên, bảng NAV không ghi trực tiếp `ActualWorkingMinutes` và
> `PlannedOperatingMinutes`, dẫn đến OEE chỉ tính được dạng rút gọn P x Q.
> ProductionVolume (từ Value Entry) phản ánh trực tiếp sản lượng thực tế —
> đơn giản hơn, chính xác hơn, và không phụ thuộc vào các trường dữ liệu
> bị thiếu trong cấu hình NAV của doanh nghiệp.

### 1.3. OrderDemand — Nhu cầu Đặt hàng

**OrderDemand** đo tổng số lượng sản phẩm được đặt hàng theo tuần, phản ánh
**áp lực cầu** (demand pressure) từ khách hàng lên hệ thống sản xuất. Đây là
biến đầu vào (exogenous driver) trong chuỗi nhân quả: **OrderDemand** →
ProductionVolume → DelayRate.

**Công thức tổng hợp:**

$$
\text{OrderDemand}_{\text{week}} = \sum_{j \in \mathcal{W}} \text{Quantity}_j
$$

Trong đó:
- $\mathcal{W}$: tập các dòng đơn hàng bán (Sales Order Line) có ngày giao hàng
  dự kiến thuộc tuần đang xét.
- $\text{Quantity}_j$: trường `[Quantity]` của dòng đơn hàng thứ $j$ — số lượng
  sản phẩm được đặt.

**Nguồn dữ liệu SQL (Dynamics NAV — CSDL QTDN):**
- `[Sales Order Line]` JOIN `[Sales Order Header]` trên `[Document No_]` = `[No_]`.
- `[Sales Order Line]`: cung cấp `[Quantity]` (số lượng đặt hàng) và
  `[Shipment Date]` (ngày giao hàng dự kiến).
- Nhóm theo: `[Shipment Date]` → chuyển đổi sang tuần (Monday-based, xem mục 2.5).

**Lý do dùng Shipment Date (không phải Order Date):**
Ngày giao hàng dự kiến phản ánh thời điểm hệ thống sản xuất phải **đáp ứng** nhu
cầu — tức áp lực thực tế lên năng lực sản xuất. Order Date (ngày đặt hàng) có thể
xa thời điểm sản xuất, không phản ánh đúng áp lực tức thời.

**Miền giá trị:** $\text{OrderDemand} \geq 0$ (tổng số lượng đặt, đơn vị: sản phẩm).
Tuần không có đơn hàng nào cần giao → $\text{OrderDemand} = 0$.

> **So sánh với Revenue (phiên bản trước):** Phiên bản trước sử dụng Revenue
> (doanh thu từ `[Cust_ Ledger Entry].[Sales (LCY)]`). Revenue phản ánh kết quả
> tài chính sau khi giao hàng và xuất hóa đơn — có **độ trễ** so với thời điểm
> sản xuất. OrderDemand (từ Sales Order) phản ánh nhu cầu **trước** khi sản xuất —
> đúng vai trò biến nguyên nhân (cause) trong chuỗi nhân quả.

### 1.4. SHA-256 — Chốt tính Toàn vẹn Dữ liệu

Mỗi file CSV sau khi ghi ra đĩa được tính **checksum SHA-256** (NIST FIPS 180-4)
và ghi vào `MANIFEST.md`. Mục đích: phát hiện **bất kỳ thay đổi nào** (dù chỉ 1 bit)
trong file dữ liệu thô sau thời điểm trích xuất.

**Cơ chế hàm băm cryptographic SHA-256:**

$$
H = \text{SHA-256}(M) \in \{0, 1\}^{256}
$$

- **Input** $M$: chuỗi byte (nội dung file CSV).
- **Output** $H$: digest 256-bit (64 ký tự hex).

**Tính chất bảo mật:**
1. **Tính một chiều** (preimage resistance): cho $H$, không thể tìm ngược $M$ sao cho $\text{SHA-256}(M) = H$ trong thời gian khả thi.
2. **Kháng va chạm** (collision resistance): xác suất tìm được 2 input khác nhau $M_1 \neq M_2$ mà $H(M_1) = H(M_2)$ là $\approx 2^{-128}$ (birthday bound).
3. **Hiệu ứng thác** (avalanche effect): thay đổi 1 bit trong $M$ → thay đổi $\approx 50\%$ bit trong $H$.

**Ý nghĩa thực tiễn:** Nếu checksum SHA-256 của một file tại thời điểm $t_2$ khác với
giá trị đã ghi tại $t_1$, file CHẮC CHẮN đã bị sửa đổi giữa $t_1$ và $t_2$.

---

## 2. Tầng 2 — Data Re-engineering (Phase 0)

### 2.1. Tổng hợp ProductionVolume và OrderDemand theo Tuần

ProductionVolume và OrderDemand đều sử dụng phép **cộng đơn giản** (SUM) khi gộp
theo tuần:

$$
\text{ProductionVolume}_{\text{week}} = \sum_{i \in \mathcal{W}} \text{ValuedQty}_i
$$

$$
\text{OrderDemand}_{\text{week}} = \sum_{j \in \mathcal{W}} \text{Quantity}_j
$$

**Lý do không cần weighted average:** Cả hai biến đều là **đại lượng tích lũy**
(cumulative quantity), không phải tỷ lệ hay chỉ số hiệu suất. Tổng sản lượng
hoặc tổng nhu cầu trong tuần chính là thước đo tự nhiên — không có vấn đề
"đơn hàng lớn vs nhỏ" cần cân nhắc trọng số.

**Miền giá trị:** Cả hai biến $\geq 0$. Tuần không có hoạt động → giá trị = 0
(thông tin kinh tế hợp lệ, xem mục 2.3).

### 2.2. Tỷ lệ Trễ (DelayRate) — Tỷ lệ đơn hàng bị trễ trong tuần

$$
\text{DelayRate}_{\text{week}} = \frac{\sum_{i=1}^{n} \mathbb{1}[\text{IsDelayed}_i = 1]}{n}
$$

Trong đó $\mathbb{1}[\cdot]$ là hàm chỉ thị (indicator function), $n$ là tổng số đơn hàng
hoàn thành trong tuần. DelayRate $\in [0, 1]$ — **KHÔNG áp dụng trọng số** vì mỗi đơn hàng
đều quan trọng như nhau về mặt cam kết giao hàng, bất kể quy mô sản xuất.

### 2.3. Xử lý Giá trị Thiếu (Gap Filling) — Phân biệt theo Bản chất Biến

Pipeline áp dụng **chiến lược khác nhau** cho từng loại biến, dựa trên bản chất
kinh tế của giá trị thiếu:

#### A. DelayRate — Forward-fill có giới hạn (Strategy A, CLAUDE.md mục 8)

$$
\hat{y}_t^{\text{delay}} = \begin{cases}
y_{t^*} & \text{nếu } t - t^* \leq 4 \cdot \Delta_w \\
\text{NaN} & \text{nếu } t - t^* > 4 \cdot \Delta_w
\end{cases}
$$

- $y_{t^*}$: giá trị DelayRate quan sát gần nhất trước $t$.
- Forward-fill tối đa **4 tuần liên tiếp** (limit=4).
- Khoảng trống > 4 tuần giữ NaN — structural gap, không nên nội suy.
- Cột `is_filled_delay` (boolean) đánh dấu dòng được forward-fill.

**Lý do dùng forward-fill cho DelayRate:** xem mục 2.4 bên dưới (giữ nguyên
phân tích chi tiết).

#### B. ProductionVolume và OrderDemand — fillna(0)

$$
\hat{y}_t^{\text{prod}} = \begin{cases}
y_t & \text{nếu } y_t \neq \text{NaN} \\
0 & \text{nếu } y_t = \text{NaN}
\end{cases}
\qquad
\hat{y}_t^{\text{demand}} = \begin{cases}
y_t & \text{nếu } y_t \neq \text{NaN} \\
0 & \text{nếu } y_t = \text{NaN}
\end{cases}
$$

"Không có hoạt động sản xuất" ($\text{ProductionVolume} = 0$) và "không có đơn
hàng cần giao" ($\text{OrderDemand} = 0$) là **thông tin kinh tế hợp lệ** — giá
trị 0 có ý nghĩa thực (zero activity), không phải dữ liệu bị thiếu.

> **Lưu ý:** Cột `is_filled_delay` chỉ áp dụng cho DelayRate. ProductionVolume
> và OrderDemand không cần cờ đánh dấu vì `fillna(0)` là phép gán xác định —
> không có giả định nào về xu hướng hay trạng thái trước đó.

### 2.4. Forward-fill Khoảng trống Thời gian (Gap Handling — Strategy A)

Khi gộp đơn hàng theo tuần, chuỗi thời gian có thể **thiếu tuần** (tuần không
có đơn hàng nào hoàn thành). Chiến lược Forward-fill có giới hạn (Strategy A)
xử lý khoảng trống này mà không tạo thêm bias:

#### Bước 1: Reindex về lưới thời gian đều đặn

$$
\mathcal{T}_{\text{full}} = \{t_0, t_0 + 7\text{d}, t_0 + 14\text{d}, \ldots, t_N\}
\quad \text{với } t_0 = \min(\text{week\_start}), \ t_N = \max(\text{week\_start})
$$

Tạo lưới tuần đều đặn (`freq='W-MON'`) bao phủ toàn bộ khoảng thời gian quan sát.
Tuần nào không có dữ liệu gốc sẽ nhận giá trị NaN.

#### Bước 2: Forward-fill có giới hạn

$$
\hat{y}_t = \begin{cases}
y_{t^*} & \text{nếu } t - t^* \leq L \cdot \Delta_w \\
\text{NaN} & \text{nếu } t - t^* > L \cdot \Delta_w
\end{cases}
$$

Trong đó:
- $y_{t^*}$: giá trị quan sát gần nhất **trước** $t$ (last observed value).
- $L = 4$ (tuần): giới hạn forward-fill tối đa.
- $\Delta_w = 7$ ngày: bước thời gian 1 tuần.
- Khoảng trống $> L$ tuần được giữ nguyên NaN — là **structural gap**, không nên
  nội suy.

#### Tại sao Forward-fill thay vì Linear Interpolation cho DelayRate?

Forward-fill phù hợp hơn nội suy tuyến tính cho `DelayRate` vì 3 lý do:

1. **Bản chất tỷ lệ rời rạc:** `DelayRate` = số đơn hàng trễ / tổng đơn hàng
   trong tuần — đây là tỷ lệ rời rạc, không phải đại lượng liên tục. Nội suy
   tuyến tính giả định xu hướng chuyển tiếp mượt giữa 2 điểm — giả định không
   hợp lệ cho tỷ lệ nhị thức (binomial proportion).

2. **Ý nghĩa kinh tế của "tuần trống":** Khi tuần $t$ không có đơn hàng hoàn
   thành, trạng thái hệ thống sản xuất không thay đổi — `DelayRate` tại $t$
   phản ánh trạng thái cuối cùng được quan sát ($t^*$), không phải giá trị
   nội suy giữa hai điểm xa nhau.

3. **Tránh giả xu hướng (spurious trend):** Nội suy tuyến tính tạo xu hướng
   nhân tạo giữa 2 điểm — nếu tuần $t_1$ có `DelayRate = 0.3` và tuần $t_3$
   có `DelayRate = 0.1`, nội suy gán $t_2 = 0.2$ — giá trị này KHÔNG phản ánh
   bất kỳ quan sát thực nào mà tạo ấn tượng giả về xu hướng giảm đều.

#### Bước 3: Đánh dấu minh bạch

Cột `is_filled_delay` (boolean) ghi nhận mọi dòng DelayRate được forward-fill:

$$
\text{is\_filled\_delay}_t = \begin{cases}
\text{True} & \text{nếu } \text{DelayRate}_t \text{ gốc là NaN AND } \hat{y}_t \neq \text{NaN} \\
\text{False} & \text{ngược lại}
\end{cases}
$$

Tầng 3 (Phase 1 trở đi) sử dụng cờ này cho phân tích độ nhạy: chạy lại kiểm
định trên tập dữ liệu loại tuần `is_filled_delay = True` để đánh giá tác động
forward-fill lên kết luận thống kê.

> **Tham chiếu:** Chiến lược forward-fill có giới hạn phù hợp với khuyến nghị
> của Enders (2014) về xử lý missing observations trong chuỗi thời gian ngắn:
> ưu tiên phương pháp bảo toàn phân phối gốc (distribution-preserving) thay vì
> phương pháp tạo giá trị mới (value-generating) như nội suy.

### 2.5. Chuyển đổi Ngày → Tuần ISO (Week Start — Monday)

$$
\text{week\_start}(d) = d - \text{weekday}(d) \cdot \Delta_{\text{day}}
$$

Trong đó $\text{weekday}(d) \in \{0, 1, ..., 6\}$ (Monday = 0, Sunday = 6). Kết quả là
ngày thứ Hai (Monday) của tuần chứa $d$ — dùng làm trục thời gian chung khi merge các nguồn dữ liệu (ProductionVolume, DelayRate, OrderDemand).

---

## 3. Tầng 3 — Time-Series Econometrics (Kinh tế lượng Chuỗi thời gian)

### 3.1. Kiểm định ADF — Augmented Dickey-Fuller (Phase 1)

**Giả thuyết:** $H_0$: chuỗi có nghiệm đơn vị (unit root) → KHÔNG dừng.

**Phương trình hồi quy ADF:**

$$
\Delta y_t = \mu + \gamma \, y_{t-1} + \sum_{j=1}^{p} \delta_j \, \Delta y_{t-j} + \varepsilon_t
$$

Trong đó:
- $\Delta y_t = y_t - y_{t-1}$: sai phân bậc 1.
- $\mu$: hằng số (constant) — pipeline dùng regression `'c'` (có constant, không trend).
- $\gamma$: hệ số cần kiểm định. Nếu $\gamma = 0$ → nghiệm đơn vị (không dừng).
- $p$: số lag phụ (augmented lags) — chọn tự động bằng AIC (`autolag='AIC'`).
- $\delta_j$: hệ số lag phụ — loại bỏ tự tương quan trong phần dư.
- $\varepsilon_t$: nhiễu trắng (white noise).

**Thống kê kiểm định:**

$$
\tau_{\text{ADF}} = \frac{\hat{\gamma}}{\text{SE}(\hat{\gamma})}
$$

Bác bỏ $H_0$ khi $\tau_{\text{ADF}} < \tau_{\text{critical}}(\alpha)$ (phân phối phi chuẩn — bảng Dickey-Fuller).

**Quy tắc quyết định** (pipeline dùng p-value): Bác bỏ $H_0$ khi $p < 0.05$ → kết luận chuỗi **DỪNG**.

### 3.2. Kiểm định KPSS — Kwiatkowski-Phillips-Schmidt-Shin (Phase 1)

**Giả thuyết:** $H_0$: chuỗi **DỪNG** (stationary) — ngược hoàn toàn với ADF.

**Mô hình phân tách:**

$$
y_t = \xi \cdot t + r_t + \varepsilon_t
$$

$$
r_t = r_{t-1} + u_t, \quad u_t \sim \text{iid}(0, \sigma_u^2)
$$

Trong đó $r_t$ là random walk component. Kiểm định $H_0: \sigma_u^2 = 0$ (random walk không tồn tại → chuỗi dừng).

**Thống kê KPSS (level stationarity, regression `'c'`):**

$$
\eta_\mu = \frac{1}{T^2} \sum_{t=1}^{T} \frac{S_t^2}{\hat{\sigma}_\infty^2}
$$

Trong đó:
- $S_t = \sum_{i=1}^{t} e_i$: tổng tích lũy (partial sum) phần dư $e_i$ từ hồi quy $y_t$ lên hằng số.
- $\hat{\sigma}_\infty^2$: ước lượng phương sai dài hạn (long-run variance), dùng Bartlett kernel với bandwidth = `nlags`.
- $T$: số quan sát.

**Quy tắc:** Bác bỏ $H_0$ khi $\eta_\mu > \eta_{\text{critical}}(\alpha)$ → kết luận chuỗi **KHÔNG DỪNG**.

### 3.3. Ma trận Quyết định Kép (Dual Confirmation — ADF + KPSS)

| | KPSS giữ $H_0$ (dừng) | KPSS bác bỏ $H_0$ (không dừng) |
|---|---|---|
| **ADF bác bỏ $H_0$ (dừng)** | ✅ Xác nhận **DỪNG** | ⚠ Mâu thuẫn (có thể trend-stationary) |
| **ADF giữ $H_0$ (không dừng)** | ❓ Không kết luận (power thấp) | ✅ Xác nhận **KHÔNG DỪNG** |

#### Xử lý Case 3 (Mâu thuẫn): Kiểm định Zivot-Andrews (1992) làm Tiebreaker

Khi ADF và KPSS cho kết quả **mâu thuẫn** (Case 3: ADF bác bỏ unit root NHƯNG
KPSS cũng bác bỏ stationarity), pipeline tự động chạy kiểm định
**Zivot-Andrews** làm tiebreaker. Trường hợp này thường xảy ra khi chuỗi dừng
quanh một **structural break** — ADF phát hiện mean-reversion nhưng KPSS phát
hiện sự thay đổi mức.

**Mô hình Zivot-Andrews (Model A — intercept break):**

$$
y_t = \hat{\mu} + \hat{\theta} \cdot DU_t(\hat{T}_B) + \hat{\beta} \cdot t + \hat{\alpha} \cdot y_{t-1} + \sum_{j=1}^{k} \hat{c}_j \, \Delta y_{t-j} + \hat{e}_t
$$

Trong đó:
- $DU_t(T_B) = \mathbb{1}[t > T_B]$: biến giả (dummy) cho structural break
  tại thời điểm $T_B$.
- $T_B$: **break point nội sinh** — ZA tìm $T_B$ tối ưu bằng cách chạy hồi
  quy cho MỌI vị trí $T_B$ khả thi (loại 15% đầu/cuối chuỗi) và chọn $T_B$
  cho thống kê $t(\hat{\alpha})$ nhỏ nhất (most negative).
- $\hat{\alpha}$: hệ số cần kiểm định. $H_0: \alpha = 1$ (unit root).

**Thống kê kiểm định:**

$$
t_{ZA} = \min_{T_B} \frac{\hat{\alpha}(T_B) - 1}{\text{SE}(\hat{\alpha}(T_B))}
$$

**Quy tắc quyết định trong pipeline:**

$$
\text{Case 3 resolution} = \begin{cases}
\text{stationary (break-adjusted)} & \text{nếu } p_{ZA} < 0.05 \\
\text{contradictory (conservative)} & \text{nếu } p_{ZA} \geq 0.05 \\
\text{contradictory (fallback)} & \text{nếu ZA thất bại (mẫu quá nhỏ)}
\end{cases}
$$

Khi ZA bác bỏ $H_0$ → chuỗi dừng quanh break → kết luận **stationary** (chuỗi
dừng có structural break). Khi ZA không bác bỏ → giữ **contradictory**, tạm xử
lý như dừng (bảo thủ) — tránh over-differencing.

> **Tham chiếu:** Zivot, E. & Andrews, D. W. K. (1992). Further evidence on the
> Great Crash, the oil-price shock, and the unit-root hypothesis. *Journal of
> Business & Economic Statistics*, 10(3), 251–270.

**Bậc tích hợp $d(i)$:** Sai phân tuần tự cho đến khi chuỗi dừng. Ký hiệu: chuỗi $y_t \sim I(d)$ nếu $\Delta^d y_t$ dừng và $\Delta^{d-1} y_t$ không dừng.

**Kết quả thực tế của dự án:**

| Biến | $d(i)$ | Phân loại |
|------|---------|-----------|
| ProductionVolume | 0 | I(0) — dừng ở mức gốc (ADF bác bỏ, KPSS giữ H₀) |
| DelayRate | 0 | I(0) — dừng ở mức gốc (ADF bác bỏ, KPSS giữ H₀) |
| OrderDemand | 0 | I(0) — dừng ở mức gốc (ADF bác bỏ, KPSS giữ H₀) |

$d_{\max} = \max\{d(i)\} = 0$ — tất cả biến đều I(0), không cần sai phân. Toda-Yamamoto sử dụng $d_{\max} = 0$, do đó VAR mở rộng có tổng lag = $k + 0 = k$.

### 3.4. Kiểm định Đồng tích hợp Johansen (Phase 3)

**Mục đích:** Xác định số lượng quan hệ cân bằng dài hạn (cointegrating rank $r$)
giữa $n$ biến $I(1)$ (hoặc mixed order).

#### 3.4.1. Trace Statistic

Kiểm định: $H_0: \text{rank}(\Pi) \leq r$ vs $H_1: \text{rank}(\Pi) > r$

$$
\lambda_{\text{trace}}(r) = -T \sum_{i=r+1}^{n} \ln(1 - \hat{\lambda}_i)
$$

Trong đó:
- $T$: số quan sát hiệu dụng.
- $\hat{\lambda}_i$: eigenvalue thứ $i$ (sắp xếp giảm dần: $\hat{\lambda}_1 \geq \hat{\lambda}_2 \geq ... \geq \hat{\lambda}_n$).
- $n$: số biến trong hệ thống (= 3 trong dự án này).

**Ý nghĩa:** Trace statistic kiểm tra xem có **nhiều hơn** $r$ vector đồng tích hợp hay không — tổng hợp bằng chứng từ tất cả eigenvalue còn lại $(\hat{\lambda}_{r+1}, ..., \hat{\lambda}_n)$.

#### 3.4.2. Max-Eigenvalue Statistic

Kiểm định: $H_0: \text{rank}(\Pi) = r$ vs $H_1: \text{rank}(\Pi) = r + 1$

$$
\lambda_{\max}(r, r+1) = -T \cdot \ln(1 - \hat{\lambda}_{r+1})
$$

**Ý nghĩa:** Chỉ dùng eigenvalue kế tiếp $\hat{\lambda}_{r+1}$ — kiểm tra xem **đúng** $r+1$ vector hay chỉ $r$.

#### 3.4.3. Thủ tục Tuần tự (Sequential Testing)

1. Bắt đầu $r = 0$: nếu bác bỏ (stat > critical value tại 5%) → tiếp tục.
2. $r = 1$: nếu bác bỏ → tiếp tục.
3. Dừng khi **không bác bỏ** → $r^* = $ giá trị đó.

Khi Trace và Max-Eigenvalue cho rank khác nhau, ưu tiên **Trace** (Johansen & Juselius, 1990 — Trace ổn định hơn trong mẫu hữu hạn).

#### 3.4.4. Quyết định Rank $r$ của Dự án

Với $n = 3$ biến (ProductionVolume, DelayRate, OrderDemand), kết quả Johansen test:

**Kết quả thực tế:** Tất cả 3 biến đều I(0) (dừng ở mức gốc). Johansen test trên hệ
3 biến I(0) cho $r = 3$ (full rank) — Trace test và Max-Eigenvalue test đều bác bỏ
mọi giả thuyết $H_0$ từ $r \leq 0$ đến $r \leq 2$. Kết quả $r = n = 3$ xác nhận
**tất cả biến đã dừng** — ma trận $\Pi$ full rank, không có common stochastic trend.

**Route: VAR trên mức gốc (VAR\_on\_levels)**

Khi $r = n = 3$ (full rank), hệ thống không có quan hệ đồng tích hợp theo nghĩa
Johansen — tất cả biến đã dừng ở mức. Mô hình phù hợp là **VAR trên chuỗi mức**
(levels), không phải VECM. Điều này có ý nghĩa kinh tế: ProductionVolume, DelayRate,
và OrderDemand đều mean-reverting — không có xu hướng stochastic dài hạn, phù hợp
với dữ liệu sản xuất tuần có tính mùa vụ và quay về trung bình.

### 3.5. Kiểm định Nhân quả Toda-Yamamoto (Phase 3b)

**Mục đích:** Kiểm tra nhân quả Granger **trên chuỗi mức** (levels) — KHÔNG cần
sai phân, KHÔNG cần pre-testing đồng tích hợp.

#### 3.5.1. Phương trình VAR mở rộng

Ước lượng $\text{VAR}(k + d_{\max})$ trên chuỗi mức:

$$
y_t = c + \underbrace{\sum_{j=1}^{k} A_j \, y_{t-j}}_{\text{k lag kiểm định}} + \underbrace{\sum_{j=k+1}^{k+d_{\max}} A_j \, y_{t-j}}_{\text{d\_max lag "đệm"}} + u_t
$$

Trong đó:
- $y_t \in \mathbb{R}^n$: vector biến nội sinh (3 biến).
- $k = 12$: lag tối ưu chọn trên chuỗi mức bằng AIC (Schwert maxlag = 17, AIC chọn lag = 12).
- $d_{\max} = 0$: bậc tích hợp lớn nhất (từ Phase 1 — tất cả biến I(0)).
- $A_j \in \mathbb{R}^{n \times n}$: ma trận hệ số lag $j$.
- Tổng lag mô hình: $k + d_{\max} = 12 + 0 = 12$. Vì $d_{\max} = 0$, kiểm định Wald của Toda-Yamamoto tương đương Granger causality trên levels.

#### 3.5.2. Kiểm định Wald

Để kiểm tra $X$ có Granger-cause $Y$ (theo Toda-Yamamoto) hay không:

$$
H_0: A_1^{(X \to Y)} = A_2^{(X \to Y)} = ... = A_k^{(X \to Y)} = 0
$$

Chỉ kiểm định **$k$ lag đầu tiên** (bỏ qua $d_{\max}$ lag cuối):

$$
W = \hat{\beta}_{(1:k)}' \left[ \hat{V}(\hat{\beta}_{(1:k)}) \right]^{-1} \hat{\beta}_{(1:k)} \sim \chi^2(k) \quad \text{dưới } H_0
$$

Trong đó:
- $\hat{\beta}_{(1:k)}$: vector chứa $k$ hệ số của biến nguyên nhân $X$ trong phương trình $Y$ (lag 1 đến $k$).
- $\hat{V}(\hat{\beta}_{(1:k)})$: ma trận hiệp phương sai của các hệ số ước lượng.

**Lý do $d_{\max}$ lag cuối chỉ là "đệm":** Toda & Yamamoto (1995) chứng minh rằng khi mô hình được ước lượng với $k + d_{\max}$ lag, thống kê Wald trên $k$ lag đầu có phân phối tiệm cận $\chi^2(k)$ **bất kể** các chuỗi có $I(0)$, $I(1)$, hay đồng tích hợp. Các lag phụ "hấp thụ" tác động của nghiệm đơn vị.

---

## 4. Tầng 4 — VECM Forecasting (Dự báo)

### 4.1. Hệ phương trình Ma trận VECM (Vector Error Correction Model)

**Dạng tổng quát:**

$$
\Delta y_t = \underbrace{\alpha \cdot \beta' y_{t-1}}_{\text{Error Correction Term}} + \sum_{i=1}^{k} \Gamma_i \, \Delta y_{t-i} + c + u_t
$$

Trong đó:
- $y_t \in \mathbb{R}^n$: vector $n$ biến nội sinh tại thời điểm $t$ ($n = 3$: ProductionVolume, DelayRate, OrderDemand).
- $\Delta y_t = y_t - y_{t-1}$: sai phân bậc 1.
- $\beta \in \mathbb{R}^{n \times r}$: ma trận vector đồng tích hợp ($r$ xác định từ Johansen test).
- $\alpha \in \mathbb{R}^{n \times r}$: ma trận tốc độ điều chỉnh (loading coefficients).
- $\Gamma_i \in \mathbb{R}^{n \times n}$: hệ số ngắn hạn (short-run dynamics) cho lag $i$.
- $k$: số lag sai phân (lagged differences).
- $c \in \mathbb{R}^n$: hằng số không hạn chế (unrestricted constant).
- $u_t \sim N(0, \Sigma_u)$: vector nhiễu trắng (innovation).

> **Kết quả thực tế của dự án:** Do tất cả 3 biến đều I(0), route là **VAR trên
> mức gốc** (VAR\_on\_levels), KHÔNG phải VECM. Mô hình VECM ở trên được trình bày
> như **phương pháp luận dự phòng** — nếu có biến I(1) và tồn tại đồng tích hợp, VECM
> sẽ là lựa chọn phù hợp. Trong thực tế, pipeline tự động chọn VAR(12) trên levels
> dựa trên kết quả Phase 1 (tất cả I(0)) và Phase 3 ($r = 3$, full rank).

**Dạng thực tế của dự án — VAR(12) trên mức gốc:**

$$
\boxed{y_t = c + \sum_{i=1}^{12} A_i \, y_{t-i} + u_t}
$$

Mô hình VAR(12) trực tiếp trên chuỗi mức — AIC chọn $p = 12$ lag từ Schwert maxlag = 17. Với $T = 412$ quan sát (sau dropna), $T_{\text{eff}} = 400$ quan sát hiệu dụng.

### 4.2. Ma trận Impact $\Pi = \alpha \cdot \beta'$ (Phân rã Rank)

$$
\Pi = \alpha \cdot \beta' \in \mathbb{R}^{n \times n}, \quad \text{rank}(\Pi) = r
$$

Ma trận $\Pi$ nắm bắt **toàn bộ thông tin dài hạn** của hệ thống. Phân rã thành $\alpha \cdot \beta'$ tách biệt:
- $\beta$: **hướng** cân bằng (equilibrium relationships).
- $\alpha$: **tốc độ** hội tụ về cân bằng (speed of adjustment).

### 4.3. Quan hệ Dài hạn trong Mô hình VAR trên Mức

> **Lưu ý:** Mục này thay thế phần "Phương trình đồng tích hợp" trong thiết kế
> ban đầu. Kết quả Phase 1 cho thấy tất cả biến I(0) → $r = 3$ (full rank) →
> **không tồn tại quan hệ đồng tích hợp** theo nghĩa Johansen. Ma trận $\beta$
> và phương trình CE không áp dụng.

Trong mô hình VAR(12) trên mức, quan hệ dài hạn giữa các biến được nắm bắt **gián
tiếp** qua hệ số VAR tích lũy (cumulative VAR coefficients) thay vì qua ma trận
$\beta$ đồng tích hợp. Chuỗi nhân quả kinh tế vẫn được kiểm chứng qua:

1. **Granger causality** (Phase 2): 3/6 cặp có ý nghĩa thống kê.
2. **Toda-Yamamoto** (Phase 3b): 2/6 cặp có ý nghĩa, tỷ lệ đồng thuận 83%.
3. **FEVD** (Phase 5): phân rã phương sai cho thấy cấu trúc nhân quả thực tế.
4. **IRF** (Phase 5): phản ứng xung xác nhận mức độ tác động.

### 4.4. Cấu trúc Nhân quả — Kết quả VAR trên Mức

> **Lưu ý:** Ma trận $\alpha$ (speed of adjustment) và half-life hội tụ chỉ áp dụng
> cho VECM. Với route VAR\_on\_levels, phần này trình bày kết quả **Granger causality**
> và **FEVD** thay cho $\alpha$.

**Kết quả Granger causality (Phase 2) — 3/6 cặp có ý nghĩa:**

| Cặp nhân quả | Lag tối ưu | Kết luận |
|---------------|:----------:|----------|
| ProductionVolume → DelayRate | 6 | Có ý nghĩa — sản lượng tác động lên tỷ lệ trễ |
| ProductionVolume → OrderDemand | 10 | Có ý nghĩa — sản lượng tác động lên nhu cầu |
| DelayRate → ProductionVolume | 12 | Có ý nghĩa — trễ phản hồi lên sản lượng |

**FEVD tại $h = 12$ tuần — Phát hiện chính (Null Finding):**

| Nguồn shock | Đóng góp vào phương sai DelayRate |
|-------------|:---------------------------------:|
| DelayRate (tự thân) | 94.0% |
| ProductionVolume | 3.8% |
| OrderDemand | 2.3% |

DelayRate chủ yếu mang tính **tự hồi quy** (autoregressive) — 94% phương sai được
giải thích bởi chính nó. Dù Granger causality phát hiện quan hệ có ý nghĩa thống kê,
FEVD cho thấy tác động **thực tiễn** từ ProductionVolume và OrderDemand là rất nhỏ.

### 4.5. Khoảng tin cậy Dự báo — Phương pháp IRF/MA (Lütkepohl, 2005)

#### 4.5.1. Biểu diễn MA (Moving Average) của Forecast Error

Sai số dự báo tại tầm $h$ bước:

$$
e_{T+h|T} = y_{T+h} - \hat{y}_{T+h|T} = \sum_{i=0}^{h-1} \Psi_i \cdot u_{T+h-i}
$$

Trong đó $\Psi_i$ là ma trận hệ số MA bậc $i$ (= Impulse Response Function tại bước $i$), với $\Psi_0 = I_n$ (identity matrix).

#### 4.5.2. Phương sai Sai số Dự báo

$$
\text{Var}(e_{T+h|T}) = \sum_{i=0}^{h-1} \Psi_i \cdot \Sigma_u \cdot \Psi_i'
$$

Trong đó:
- $\Sigma_u = E[u_t u_t']$: ma trận hiệp phương sai innovation (ước lượng từ phần dư VECM fit).
- $\Psi_i$: thu được từ IRF (Impulse Response Function) của process levels.

#### 4.5.3. Khoảng tin cậy 95%

$$
\text{CI}_{95\%}(y_{T+h}) = \hat{y}_{T+h|T} \pm z_{0.025} \cdot \sqrt{\text{diag}\left(\text{Var}(e_{T+h|T})\right)}
$$

Với $z_{0.025} = 1.96$ (phân phối chuẩn, hai phía):

$$
\boxed{\hat{y}_{T+h|T} \pm 1.96 \times \text{SE}_h}
$$

Trong đó:

$$
\text{SE}_h^{(k)} = \sqrt{\left[\sum_{i=0}^{h-1} \Psi_i \cdot \Sigma_u \cdot \Psi_i'\right]_{kk}}
$$

là sai số chuẩn dự báo cho biến thứ $k$ tại tầm $h$.

#### 4.5.4. Tính chất theo Tầm dự báo

- Tại $h = 1$: $\text{Var}(e_{T+1|T}) = \Psi_0 \Sigma_u \Psi_0' = \Sigma_u$ (chỉ innovation).
- Khi $h \to \infty$: CI mở rộng monotonically — uncertainty tích lũy.
- Tốc độ mở rộng: phụ thuộc eigenvalues của VAR companion matrix.

#### 4.5.5. Phương pháp Fallback: Xấp xỉ $\sqrt{h}$

Khi IRF không khả dụng (lỗi số học do mẫu cực nhỏ):

$$
\text{SE}_h^{\text{approx}} = \sqrt{h} \cdot \text{SE}_1 = \sqrt{h} \cdot \sqrt{\text{diag}(\Sigma_u)}
$$

Xấp xỉ này hợp lệ khi quá trình LEVELS xấp xỉ random walk ($\Psi_i \approx I$ cho mọi $i$), nhưng **đánh giá thấp** uncertainty khi có dynamic interactions mạnh giữa các biến.

### 4.6. Tiêu chí Thông tin (Information Criteria)

$$
\text{AIC} = -2 \cdot \mathcal{L} + 2k
$$

$$
\text{BIC} = -2 \cdot \mathcal{L} + \ln(T) \cdot k
$$

Trong đó:
- $\mathcal{L} = -11{,}177.62$: log-likelihood của VAR(12) trên levels.
- $k$: tổng số tham số. Với VAR(12), 3 biến: mỗi phương trình có $12 \times 3 + 1 = 37$
  tham số (12 lag × 3 biến + intercept), tổng = $37 \times 3 = 111$ tham số.
- $T = 400$: số quan sát hiệu dụng (412 dòng − 12 lag ban đầu).

**Kết quả:**
- **AIC** = 47.93
- **BIC** = 49.04
- **Bậc tự do/phương trình** = 363 ($T_{\text{eff}} - k_{\text{per\_eq}} = 400 - 37$)

---

## 5. Eigenvalue Clamping — Xử lý Ma trận Hiệp phương sai Suy biến

### 5.1. Vấn đề: $\Sigma_u$ Không Xác định Dương (Non-Positive Definite)

Khi tính khoảng tin cậy dự báo (mục 4.5), pipeline cần thực hiện **phân rã
Cholesky** trên ma trận hiệp phương sai innovation $\Sigma_u$:

$$
\Sigma_u = L \cdot L'
$$

Phân rã Cholesky yêu cầu $\Sigma_u$ phải **xác định dương** (positive definite),
tức mọi eigenvalue $\lambda_i > 0$. Tuy nhiên, với mẫu cực nhỏ ($N = 10$), ma
trận $\Sigma_u$ ước lượng từ phần dư VECM có thể:

1. **Gần suy biến** (near-singular): một hoặc nhiều $\lambda_i \approx 0$ do
   rank thiếu (rank deficiency) — xảy ra khi số quan sát gần bằng số biến.
2. **Suy biến thực sự**: $\lambda_i \leq 0$ do lỗi số học (numerical error)
   trong quá trình ước lượng OLS/MLE.

Khi $\Sigma_u$ không xác định dương → `np.linalg.cholesky()` raise
`LinAlgError` → pipeline crash trước khi tạo được khoảng tin cậy.

### 5.2. Phương pháp: Phân rã Spectral + Kẹp Eigenvalue (Eigenvalue Clamping)

#### Bước 1: Phân rã Spectral (Eigendecomposition)

$$
\Sigma_u = V \cdot \Lambda \cdot V^T
$$

Trong đó:
- $V \in \mathbb{R}^{n \times n}$: ma trận trực giao chứa các eigenvector.
- $\Lambda = \text{diag}(\lambda_1, \lambda_2, \ldots, \lambda_n)$: ma trận
  đường chéo chứa các eigenvalue.

Pipeline dùng `numpy.linalg.eigh()` (cho ma trận đối xứng) — thuật toán ổn
định hơn `numpy.linalg.eig()` cho ma trận hiệp phương sai.

#### Bước 2: Kẹp (Clamping) eigenvalue không hợp lệ

$$
\tilde{\lambda}_i = \max(\lambda_i, \, \epsilon_{\text{floor}})
$$

Trong đó:

$$
\epsilon_{\text{floor}} = \max(|\lambda_1|, |\lambda_2|, \ldots, |\lambda_n|) \times 10^{-8}
$$

Mọi eigenvalue $\leq 0$ hoặc quá nhỏ được nâng lên $\epsilon_{\text{floor}}$
— một giá trị **tương đối** so với eigenvalue lớn nhất, đảm bảo tỉ lệ điều
kiện (condition number) không vượt $10^8$.

#### Bước 3: Tái tạo ma trận xác định dương

$$
\tilde{\Sigma}_u = V \cdot \tilde{\Lambda} \cdot V^T
$$

Với $\tilde{\Lambda} = \text{diag}(\tilde{\lambda}_1, \ldots, \tilde{\lambda}_n)$.
Ma trận $\tilde{\Sigma}_u$ đảm bảo:
- **Xác định dương**: mọi $\tilde{\lambda}_i > 0$.
- **Đối xứng**: bảo toàn từ phân rã spectral.
- **Gần $\Sigma_u$ gốc**: chỉ điều chỉnh eigenvalue vi phạm, giữ nguyên
  eigenvector (cấu trúc tương quan giữa các biến).

#### Bước 4: Phân rã Cholesky thành công

$$
\tilde{\Sigma}_u = \tilde{L} \cdot \tilde{L}'
$$

Cholesky bây giờ **luôn thành công** trên $\tilde{\Sigma}_u$.

### 5.3. So sánh với Ridge Regularization (Tikhonov — $\Sigma_u + \varepsilon I$)

Phương pháp Ridge (còn gọi là Tikhonov regularization) thêm $\varepsilon I$
vào toàn bộ đường chéo:

$$
\Sigma_u^{\text{Ridge}} = \Sigma_u + \varepsilon \cdot I_n
$$

**Bảng so sánh:**

| Tiêu chí | Ridge ($+\varepsilon I$) | Eigenvalue Clamping ($V\tilde{\Lambda}V^T$) |
|---|---|---|
| **Tác động lên eigenvalue hợp lệ** | Dịch chuyển TẤT CẢ $\lambda_i$ lên $\varepsilon$ — phóng đại phương sai ngay cả cho chiều không suy biến | Chỉ sửa $\lambda_i$ vi phạm — eigenvalue hợp lệ KHÔNG bị ảnh hưởng |
| **Ảnh hưởng CI** | Khoảng tin cậy rộng hơn cần thiết cho MỌI biến | CI chỉ rộng hơn cho chiều suy biến |
| **Chọn $\varepsilon$** | Phải chọn trước (arbitrary) hoặc cross-validate | Tự động từ dữ liệu: $\epsilon_{\text{floor}} = \max|\lambda| \times 10^{-8}$ |
| **Bảo toàn cấu trúc tương quan** | Sai lệch: $\varepsilon I$ thay đổi tỉ lệ eigenvalue → correlation structure bị nhiễu | Bảo toàn eigenvector → cấu trúc tương quan giữ nguyên |
| **Ổn định số học** | Tốt | Tốt — $\epsilon_{\text{floor}}$ đảm bảo condition number $\leq 10^8$ |

**Kết luận:** Eigenvalue Clamping là phương pháp **tối thiểu can thiệp**
(minimal intervention) — chỉ sửa chính xác chiều suy biến mà không gây tác
dụng phụ lên các chiều khỏe mạnh. Trong bối cảnh mẫu nhỏ ($N = 10$) nơi mỗi
phần trăm phương sai đều quan trọng cho khoảng tin cậy, việc tránh phóng đại
phương sai giả (artifact variance inflation) là ưu tiên cao.

> **Ghi chú tự phục hồi (Self-healing):** Pipeline ghi `WARNING` khi phát hiện
> eigenvalue $\leq 0$ và thực hiện clamping — log message bao gồm eigenvalue gốc
> và giá trị sau clamping để kiểm toán. Quá trình hoàn toàn tự động, không cần
> can thiệp thủ công.

---

## 6. Tham khảo (References)

1. Dickey, D. A., & Fuller, W. A. (1979). Distribution of the Estimators for Autoregressive Time Series with a Unit Root. *JASA*, 74(366), 427–431.
2. Enders, W. (2014). *Applied Econometric Time Series* (4th ed.). Wiley.
3. Engle, R. F., & Granger, C. W. J. (1987). Co-Integration and Error Correction: Representation, Estimation, and Testing. *Econometrica*, 55(2), 251–276.
4. Granger, C. W. J. (1969). Investigating Causal Relations by Econometric Models and Cross-spectral Methods. *Econometrica*, 37(3), 424–438.
5. Jaccard, P. (1901). Distribution de la flore alpine dans le bassin des Dranses. *Bulletin de la Société Vaudoise des Sciences Naturelles*, 37, 241–272.
6. Johansen, S. (1991). Estimation and Hypothesis Testing of Cointegration Vectors in Gaussian Vector Autoregressive Models. *Econometrica*, 59(6), 1551–1580.
7. Johansen, S. (1995). *Likelihood-Based Inference in Cointegrated Vector Autoregressive Models*. Oxford University Press.
8. Kwiatkowski, D., Phillips, P. C. B., Schmidt, P., & Shin, Y. (1992). Testing the Null Hypothesis of Stationarity against the Alternative of a Unit Root. *Journal of Econometrics*, 54(1–3), 159–178.
9. Lütkepohl, H. (2005). *New Introduction to Multiple Time Series Analysis*. Springer.
10. NIST (2015). *Secure Hash Standard (SHS)*. FIPS PUB 180-4.
11. Pfaff, B. (2008). *Analysis of Integrated and Cointegrated Time Series with R* (2nd ed.). Springer.
12. Toda, H. Y., & Yamamoto, T. (1995). Statistical Inference in Vector Autoregressions with Possibly Integrated Processes. *Journal of Econometrics*, 66(1–2), 225–250.
13. Zivot, E., & Andrews, D. W. K. (1992). Further Evidence on the Great Crash, the Oil-Price Shock, and the Unit-Root Hypothesis. *Journal of Business & Economic Statistics*, 10(3), 251–270.
