# MATH_AND_ALGORITHMS.md — Chi tiết Toán học & Thuật toán

> Tài liệu kỹ thuật chuyên sâu trình bày **tất cả công thức toán học** được sử dụng
> trong pipeline dự báo nhân quả hỗn hợp 4 tầng (Hybrid Causal Forecasting — Phương án 3-A).
>
> Mọi công thức đều được trích xuất trực tiếp từ mã nguồn đã chạy, không có giá trị
> nào bị hallucinate hay hard-code ngoài kết quả thực tế.

---

## 1. Tầng 1 — Raw Data Extraction (Khai thác Dữ liệu Gốc)

### 1.1. Jaccard Index — Đo lường Độ trùng lặp OrderNo

Khi trích xuất 3 bảng dữ liệu (`cmt_oee_results`, `cmt_delay_results`, `fob_revenue`)
từ SQL Server trong cùng một snapshot, cần đảm bảo tính **nhất quán đồng thời**
(temporal consistency). Pipeline sử dụng **Jaccard Index** (Jaccard, 1901) để đo tỉ lệ
khớp `OrderNo` giữa các file:

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

### 1.2. OEE — Phân rã Hiệu suất Thiết bị Tổng thể (A × P × Q)

Chỉ số OEE (Overall Equipment Effectiveness) được tính theo phương pháp phân rã
3 thành phần chuẩn quốc tế (Nakajima, 1988):

$$
\text{OEE} = A \times P \times Q
$$

Trong đó:

**Availability (Khả dụng máy)** — tỉ lệ thời gian máy vận hành thực tế so với
kế hoạch, phản ánh tổn thất do dừng máy ngoài kế hoạch (downtime):

$$
A = \frac{\text{ActualWorkingMinutes}}{\text{PlannedOperatingMinutes}}
$$

**Performance (Hiệu năng)** — tỉ lệ năng suất thực tế so với năng suất lý thuyết,
phản ánh tổn thất do chạy chậm (speed loss):

$$
P = \frac{\text{TotalQty} \times \text{StandardCycleTime}}{\text{ActualWorkingMinutes}}
$$

- $\text{TotalQty}$: tổng số sản phẩm sản xuất (bao gồm cả phế phẩm).
- $\text{StandardCycleTime}$: thời gian chu kỳ chuẩn (phút/sản phẩm) theo thiết kế máy.
- Tử số = thời gian lý thuyết cần để sản xuất $\text{TotalQty}$ sản phẩm ở tốc độ chuẩn.

**Quality (Chất lượng)** — tỉ lệ sản phẩm đạt chất lượng, phản ánh tổn thất do
phế phẩm (defect loss):

$$
Q = \frac{\text{GoodQty}}{\text{TotalQty}}
$$

**Kết hợp đầy đủ — dạng khai triển:**

$$
\text{OEE} = \frac{\text{ActualWorkingMinutes}}{\text{PlannedOperatingMinutes}}
\times \frac{\text{TotalQty} \times \text{StandardCycleTime}}{\text{ActualWorkingMinutes}}
\times \frac{\text{GoodQty}}{\text{TotalQty}}
$$

**Giản ước (simplification):**

$$
\text{OEE} = \frac{\text{GoodQty} \times \text{StandardCycleTime}}{\text{PlannedOperatingMinutes}}
$$

> **Lưu ý thực thi:** Trong SQL query (`SQL_OEE` ở `tang1_db_extractor.py`),
> chúng tôi giữ NGUYÊN dạng 3 thành phần $A \times P \times Q$ — không dùng
> dạng giản ước — để:
> 1. Ghi nhận từng thành phần riêng biệt (cột `Availability`, `Performance`,
>    `Quality`) phục vụ phân tích nguyên nhân suy giảm OEE.
> 2. Mỗi phép chia đều có `NULLIF(..., 0)` — nếu mẫu số = 0 thì thành phần
>    đó trả về `NULL`, OEE_Score tổng cũng `NULL` (ghi `WARNING` trong log).

**Miền giá trị:**
- $A, P, Q \in [0, 1]$ trong điều kiện lý tưởng (có thể > 1 nếu máy chạy
  nhanh hơn thiết kế hoặc vận hành ngoài giờ).
- $\text{OEE} \in [0, 1]$ thường thấy; OEE > 0.85 là "world-class" theo tiêu
  chuẩn TPM (Total Productive Maintenance).

**Nguồn dữ liệu SQL (Dynamics NAV — CSDL QTDN):**
- `[Production Order Header]`: cung cấp `No_` (mã LSX), `Starting Date`, `Ending Date`.
  Lưu ý: CSDL còn có `[Production Order Header Posted]` cho LSX đã đăng (posted) —
  các hàm KPI hiện tại (KPI_2_64, KPI_2_67) dùng bảng Posted. Pipeline dùng Header
  (chưa post) vì cần `[Ending Date]` và cột thống kê trên `[Production Order Line]`.
- `[Production Order Line]`: cung cấp `Quantity` (PlanQty), `Finished Quantity` (RealQty),
  `Scrap %` — JOIN với Header qua `[Prod_Order No_]` = Header.`[No_]`.

**Thích ứng NAV:** Do bảng NAV chuẩn không ghi trực tiếp `ActualWorkingMinutes`
và `PlannedOperatingMinutes` (cần bổ sung `[Capacity Ledger Entry]` hoặc
`[Production Order Routing Finished]` cho `Run Time`, `Setup Time`), pipeline hiện
tại tính OEE theo dạng rút gọn **P × Q**:

$$
\text{OEE}_{\text{NAV}} = \underbrace{\frac{\text{Finished Quantity}}{\text{Quantity}}}_{P}
\times \underbrace{\left(1 - \frac{\text{Scrap \%}}{100}\right)}_{Q}
$$

Khi doanh nghiệp bổ sung dữ liệu thời gian máy thực tế, sẽ nâng cấp lên A × P × Q đầy đủ.

**Nguồn dữ liệu Revenue (Doanh thu):**
- `[Cust_ Ledger Entry]`: Sổ cái khách hàng (NAV Table ID 21), cột `[Sales (LCY)]`
  chứa doanh thu bằng nội tệ (VND). Đây là bảng mà toàn bộ hàm KPI trong CSDL QTDN
  thực sự sử dụng để tính doanh thu (xác nhận qua QTDN.sql: KPI_0_91, KPI_0_93,
  KPI_2_51). Filter `[Document Type] = 2` (Invoice) để chỉ lấy hóa đơn bán hàng.
- Lưu ý lịch sử: phiên bản trước dùng `[Import and Export Revenue Line].[Amount]` —
  bảng này tồn tại trong CSDL nhưng không được tham chiếu bởi bất kỳ hàm KPI nào,
  có thể chỉ phản ánh doanh thu XNK (một phần, không đầy đủ).

### 1.3. SHA-256 — Chốt tính Toàn vẹn Dữ liệu

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

### 2.1. Trung bình có Trọng số (Weighted Average) — OEE_Score tuần

Khi gộp nhiều đơn hàng trong cùng 1 tuần thành 1 giá trị OEE đại diện, pipeline
sử dụng **trung bình có trọng số** theo sản lượng thực tế `RealQty`:

$$
\overline{\text{OEE}}_{\text{week}} = \frac{\sum_{i=1}^{n} w_i \cdot \text{OEE}_i}{\sum_{i=1}^{n} w_i}
$$

Trong đó:
- $n$: số đơn hàng hoàn thành trong tuần đó.
- $\text{OEE}_i$: chỉ số hiệu suất thiết bị tổng thể của đơn hàng thứ $i$ (đã có sẵn trong `cmt_oee_results.csv`).
- $w_i = \text{RealQty}_i$: trọng số = sản lượng sản xuất thực tế của đơn hàng $i$.

**Lý do dùng trọng số:** Đơn hàng sản xuất 10,000 sản phẩm phải có ảnh hưởng lớn hơn
đơn hàng 100 sản phẩm khi tính OEE trung bình tuần — phản ánh đúng khối lượng công
việc thực tế trong tuần.

**Phương trình fallback** khi mẫu số $\sum w_i = 0$ (tất cả đơn hàng có `RealQty = 0`):

$$
\overline{\text{OEE}}_{\text{week}} = \frac{1}{n} \sum_{i=1}^{n} \text{OEE}_i \quad \text{(trung bình cộng đơn giản)}
$$

> Script ghi `WARNING` khi fallback xảy ra — đây là bất thường dữ liệu (tuần có đơn hàng
> nhưng sản lượng = 0 cho tất cả).

### 2.2. Tỷ lệ Trễ (DelayRate) — Tỷ lệ đơn hàng bị trễ trong tuần

$$
\text{DelayRate}_{\text{week}} = \frac{\sum_{i=1}^{n} \mathbb{1}[\text{IsDelayed}_i = 1]}{n}
$$

Trong đó $\mathbb{1}[\cdot]$ là hàm chỉ thị (indicator function), $n$ là tổng số đơn hàng
hoàn thành trong tuần. DelayRate $\in [0, 1]$ — **KHÔNG áp dụng trọng số** vì mỗi đơn hàng
đều quan trọng như nhau về mặt cam kết giao hàng, bất kể quy mô sản xuất.

### 2.3. Nội suy Tuyến tính (Linear Interpolation) với Giới hạn $\text{limit} = 2$

Đối với các biến là tỷ lệ (OEE_Score, DelayRate), NaN được lấp bằng nội suy tuyến tính
giữa 2 điểm dữ liệu lân cận:

$$
\hat{y}_t = y_{t_1} + \frac{y_{t_2} - y_{t_1}}{t_2 - t_1} \cdot (t - t_1)
$$

Trong đó:
- $y_{t_1}$: giá trị quan sát gần nhất **trước** vị trí cần nội suy.
- $y_{t_2}$: giá trị quan sát gần nhất **sau** vị trí cần nội suy.
- $t$: vị trí thời gian cần lấp (chỉ số tuần).
- $t_1 < t < t_2$: hai vị trí lân cận có dữ liệu thực.

**Giới hạn $\text{limit} = 2$:** Nội suy tuyến tính chỉ áp dụng cho **tối đa 2 tuần liên tiếp** bị thiếu. Nếu khoảng trống $> 2$ tuần → giữ nguyên NaN (không nội suy) vì:
- Chuỗi thời gian ngắn (vài chục tuần): nội suy không giới hạn tạo giá trị vô nghĩa.
- Khoảng trống dài ở đầu/cuối chuỗi: ngoại suy (extrapolation) nguy hiểm hơn nội suy.

**Hướng nội suy:** `limit_direction='both'` — nội suy cả từ trái sang phải (forward) và phải sang trái (backward), cho phép lấp NaN ở đầu/cuối chuỗi nếu trong giới hạn.

**Đối với Revenue và OrderVolume (tổng/đếm):** Dùng `fillna(0)` — "không có giao dịch"
là thông tin hợp lệ (giá trị 0 có ý nghĩa kinh tế thật).

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

Cột `is_filled` (boolean) ghi nhận mọi dòng được forward-fill:

$$
\text{is\_filled}_t = \begin{cases}
\text{True} & \text{nếu } y_t \text{ gốc là NaN AND } \hat{y}_t \neq \text{NaN} \\
\text{False} & \text{ngược lại}
\end{cases}
$$

Tầng 3 (Phase 1 trở đi) sử dụng cờ này cho phân tích độ nhạy: chạy lại kiểm
định trên tập dữ liệu loại tuần `is_filled = True` để đánh giá tác động
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
ngày thứ Hai (Monday) của tuần chứa $d$ — dùng làm trục thời gian chung khi merge 3 nguồn.

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
| OEE_Score | 1 | $I(1)$ |
| DelayRate | 0 | $I(0)$ |
| Revenue | 0 | $I(0)$ |
| OrderVolume | 0 | $I(0)$ |

$d_{\max} = \max\{d(i)\} = 1$ (dùng cho Toda-Yamamoto).

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
- $n$: số biến trong hệ thống (= 4 trong dự án này).

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

#### 3.4.4. Quyết định Rank $r = 2$ của Dự án

Với $n = 4$ biến, kết quả Johansen test (det_order = 1, $k\_ar\_diff = 0$):

- $H_0: r \leq 0$ → **Bác bỏ** (cả Trace lẫn Max-Eigenvalue)
- $H_0: r \leq 1$ → **Bác bỏ** (cả Trace lẫn Max-Eigenvalue)
- $H_0: r \leq 2$ → **Giữ** (không bác bỏ)

→ **$r = 2$**: tồn tại **2 vector đồng tích hợp** — 2 quan hệ cân bằng dài hạn giữa 4 biến.

**Route:** $0 < r = 2 < n = 4$ → sử dụng **VECM** (Vector Error Correction Model).

### 3.5. Kiểm định Nhân quả Toda-Yamamoto (Phase 3b)

**Mục đích:** Kiểm tra nhân quả Granger **trên chuỗi mức** (levels) — KHÔNG cần
sai phân, KHÔNG cần pre-testing đồng tích hợp.

#### 3.5.1. Phương trình VAR mở rộng

Ước lượng $\text{VAR}(k + d_{\max})$ trên chuỗi mức:

$$
y_t = c + \underbrace{\sum_{j=1}^{k} A_j \, y_{t-j}}_{\text{k lag kiểm định}} + \underbrace{\sum_{j=k+1}^{k+d_{\max}} A_j \, y_{t-j}}_{\text{d\_max lag "đệm"}} + u_t
$$

Trong đó:
- $y_t \in \mathbb{R}^n$: vector biến nội sinh (4 biến).
- $k$: lag tối ưu chọn trên chuỗi mức bằng AIC (= 1 trong dự án).
- $d_{\max} = 1$: bậc tích hợp lớn nhất (từ Phase 1).
- $A_j \in \mathbb{R}^{n \times n}$: ma trận hệ số lag $j$.
- Tổng lag mô hình: $k + d_{\max} = 1 + 1 = 2$.

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
- $y_t \in \mathbb{R}^n$: vector $n$ biến nội sinh tại thời điểm $t$ ($n = 4$).
- $\Delta y_t = y_t - y_{t-1}$: sai phân bậc 1.
- $\beta \in \mathbb{R}^{n \times r}$: ma trận vector đồng tích hợp ($r = 2$).
- $\alpha \in \mathbb{R}^{n \times r}$: ma trận tốc độ điều chỉnh (loading coefficients).
- $\Gamma_i \in \mathbb{R}^{n \times n}$: hệ số ngắn hạn (short-run dynamics) cho lag $i$.
- $k$: `k_ar_diff` = 0 → **không có thành phần $\Gamma$** trong mô hình thực tế.
- $c \in \mathbb{R}^n$: hằng số không hạn chế (unrestricted constant, `deterministic='co'`).
- $u_t \sim N(0, \Sigma_u)$: vector nhiễu trắng (innovation).

**Dạng rút gọn thực tế của dự án** (với $k\_ar\_diff = 0$):

$$
\boxed{\Delta y_t = \alpha \cdot \beta' y_{t-1} + c + u_t}
$$

Mô hình **chỉ có error correction term và constant** — không có lagged differences ($\Gamma$). Đây là lựa chọn phù hợp với mẫu nhỏ ($N = 10$, DoF = 6/equation).

### 4.2. Ma trận Impact $\Pi = \alpha \cdot \beta'$ (Phân rã Rank)

$$
\Pi = \alpha \cdot \beta' \in \mathbb{R}^{n \times n}, \quad \text{rank}(\Pi) = r = 2
$$

Ma trận $\Pi$ nắm bắt **toàn bộ thông tin dài hạn** của hệ thống. Phân rã thành $\alpha \cdot \beta'$ tách biệt:
- $\beta$: **hướng** cân bằng (equilibrium relationships).
- $\alpha$: **tốc độ** hội tụ về cân bằng (speed of adjustment).

### 4.3. Phương trình Đồng tích hợp Dài hạn (Cointegrating Equations)

Kết quả thực tế từ VECM fit ($r = 2$ vector):

#### CE1 (Cointegrating Equation 1):

$$
\underbrace{1.000000}_{\beta_{11}} \cdot \text{OEE\_Score} + \underbrace{(\approx 0)}_{\beta_{21}} \cdot \text{DelayRate} + \underbrace{(-8.20 \times 10^{-7})}_{\beta_{31}} \cdot \text{Revenue} + \underbrace{0.091302}_{\beta_{41}} \cdot \text{OrderVolume} \approx 0
$$

**Diễn giải:** CE1 chủ yếu liên kết OEE_Score với OrderVolume — mỗi đơn vị tăng OrderVolume đi kèm OEE giảm $\approx 0.091$ trong dài hạn (quan hệ tỷ lệ nghịch).

#### CE2 (Cointegrating Equation 2):

$$
\underbrace{(\approx 0)}_{\beta_{12}} \cdot \text{OEE\_Score} + \underbrace{1.000000}_{\beta_{22}} \cdot \text{DelayRate} + \underbrace{6.79 \times 10^{-6}}_{\beta_{32}} \cdot \text{Revenue} + \underbrace{(-0.659381)}_{\beta_{42}} \cdot \text{OrderVolume} \approx 0
$$

**Diễn giải:** CE2 chủ yếu liên kết DelayRate với OrderVolume — mỗi đơn vị tăng OrderVolume đi kèm DelayRate tăng $\approx 0.659$ (nhiều đơn hàng hơn → tỷ lệ trễ cao hơn).

#### Dạng ma trận $\beta$ (normalized):

$$
\beta = \begin{pmatrix}
1.000000 & \approx 0 \\
\approx 0 & 1.000000 \\
-8.20 \times 10^{-7} & 6.79 \times 10^{-6} \\
0.091302 & -0.659381
\end{pmatrix}
\quad
\begin{matrix}
\leftarrow \text{OEE\_Score} \\
\leftarrow \text{DelayRate} \\
\leftarrow \text{Revenue} \\
\leftarrow \text{OrderVolume}
\end{matrix}
$$

### 4.4. Ma trận Hệ số Điều chỉnh Tốc độ $\alpha$ (Speed of Adjustment)

$$
\alpha = \begin{pmatrix}
-1.1261 & -0.1500 \\
+0.2171 & +0.0060 \\
+1{,}258{,}017.9 & -391{,}622.1 \\
+0.1568 & -2.3527
\end{pmatrix}
\quad
\begin{matrix}
\leftarrow \text{OEE\_Score} \\
\leftarrow \text{DelayRate} \\
\leftarrow \text{Revenue} \\
\leftarrow \text{OrderVolume}
\end{matrix}
$$

**Diễn giải cơ chế hội tụ:**

| Biến | $\alpha_{i,1}$ (CE1) | $\alpha_{i,2}$ (CE2) | Diễn giải |
|------|---------------------|---------------------|-----------|
| OEE_Score | $-1.126$ | $-0.150$ | Phản ứng **mạnh** với CE1: error correcting (tự điều chỉnh giảm khi lệch dương) |
| DelayRate | $+0.217$ | $+0.006$ | Khuếch đại nhẹ lệch CE1; gần như không phản ứng CE2 (weakly exogenous) |
| Revenue | $+1.26 \times 10^6$ | $-3.92 \times 10^5$ | Phản ứng cực mạnh (do thang đo lớn — VNĐ) |
| OrderVolume | $+0.157$ | $-2.353$ | Phản ứng mạnh với CE2: error correcting cho cân bằng Delay-Order |

**Ý nghĩa kinh tế của $\alpha < 0$ (error correcting):**
- Khi ECT > 0 (hệ thống lệch khỏi cân bằng theo hướng dương), biến có $\alpha < 0$ sẽ **giảm** ở kỳ tiếp theo → kéo hệ thống quay về cân bằng.
- $|\alpha| = 1.126$ cho OEE_Score/CE1 nghĩa là: nếu OEE lệch cân bằng 1 đơn vị, OEE sẽ "quá điều chỉnh" (overcorrect) hơn 100% trong 1 tuần → dao động hội tụ.

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
- $\mathcal{L}$: log-likelihood ($= -63.40$ trong dự án).
- $k$: tổng số tham số ($= 12$: 4 biến × 3 params/eq).
- $T$: số quan sát hiệu dụng ($= 9$).

**Kết quả:** AIC = 150.80, BIC = 153.17.

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
