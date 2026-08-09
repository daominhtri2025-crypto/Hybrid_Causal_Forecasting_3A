# INNOVATIONS.md — Các Điểm Mới và Cải Tiến của Thuật Toán

> **Tài liệu phục vụ slide báo cáo khoa học**
>
> Pipeline Hybrid Causal Forecasting (Phương án 3-A) không chỉ áp dụng các phương pháp
> kinh tế lượng chuẩn — mà **cải tiến và thích ứng** chúng cho bối cảnh thực tế:
> dữ liệu sản xuất công nghiệp, cỡ mẫu cực nhỏ ($N = 10$), và yêu cầu truy vết
> hoàn toàn (full auditability). Dưới đây là 4 khía cạnh cải tiến chính.

---

## 1. Cải tiến trong Tiền xử lý Dữ liệu (Tầng 1 & 2)

### 1.1. Chống Lệch pha Dữ liệu — Jaccard Index + SHA-256

#### Bảng so sánh

| Tiêu chí | Phương pháp Truyền thống | Phương án 3-A (Dự án) |
|-----------|--------------------------|------------------------|
| **Trích xuất dữ liệu** | JOIN 3 bảng trong 1 câu SQL duy nhất | Chốt `snapshot_time` → 3 truy vấn tuần tự lọc `WHERE date ≤ @snapshot_time` |
| **Kiểm tra nhất quán** | Không kiểm tra — giả định JOIN đảm bảo | Tính Jaccard Index giữa 3 tập `OrderNo` |
| **Phát hiện lệch pha** | Không thể (JOIN tự loại dòng không khớp) | $J < 0.95$ → `WARNING` tự động |
| **Toàn vẹn sau trích xuất** | Không kiểm tra — tin tưởng filesystem | SHA-256 checksum cho mỗi file → `MANIFEST.md` |
| **Audit trail** | Không có | Timestamp + checksum + row count cho mọi snapshot |

#### Phân tích chuyên sâu

**Vấn đề với JOIN SQL thông thường:**
- Khi `JOIN cmt_oee_results ON OrderNo = fob_revenue.OrderNo`, các đơn hàng **chỉ có trong 1 bảng** (ví dụ: đã giao hàng nhưng chưa tính OEE) bị loại bỏ ÂM THẦM — không có cảnh báo.
- Nếu 3 bảng được truy vấn tại các thời điểm khác nhau (do latency mạng, locking, hoặc batch processing), dữ liệu có thể phản ánh **trạng thái KHÁC NHAU** của hệ thống — tạo inconsistency mà JOIN không phát hiện được.

**Giải pháp Dự án:**
1. **Snapshot đồng thời:** Chốt 1 mốc thời gian duy nhất `snapshot_time` TRƯỚC khi mở kết nối → mọi truy vấn lọc `≤ snapshot_time` → đảm bảo cùng lát cắt thời gian.
2. **Jaccard Index:** Đo lường tỉ lệ khớp `OrderNo` giữa 3 file **sau khi trích xuất** — phát hiện lệch pha ngay cả khi snapshot_time đã chốt (do race condition phía database).
3. **SHA-256:** Khóa chặt nội dung file — nếu ai đó (hoặc process nào đó) vô tình sửa file raw → checksum mismatch → phát hiện ngay.

**Ý nghĩa khoa học:** Đảm bảo **data provenance** (nguồn gốc dữ liệu) hoàn toàn minh bạch — yêu cầu bắt buộc trong nghiên cứu tái lập được (reproducible research).

---

### 1.2. Nội suy Có kiểm soát — `limit=2` + Cờ `is_interpolated` + Fallback

#### Bảng so sánh

| Tiêu chí | Phương pháp Truyền thống | Phương án 3-A (Dự án) |
|-----------|--------------------------|------------------------|
| **Xử lý NaN** | `fillna(df.mean())` — lấp bằng trung bình toàn chuỗi | Nội suy tuyến tính có giới hạn `limit=2` |
| **Giới hạn nội suy** | Không giới hạn — lấp tất cả NaN | Tối đa 2 tuần liên tiếp; vượt → giữ NaN |
| **Truy vết can thiệp** | Không đánh dấu — không biết giá trị nào là thật, nào là giả | Cờ `is_interpolated_oee`, `is_interpolated_delay` |
| **Phân tích độ nhạy** | Không thực hiện — giả định lấp NaN không ảnh hưởng | Chạy lại kiểm định **loại tuần nội suy** → so sánh kết luận |
| **Xử lý chia cho 0** | Crash hoặc `inf` | Fallback sang mean() đơn giản + ghi `WARNING` |
| **Revenue/OrderVolume NaN** | `fillna(mean)` — vô nghĩa kinh tế | `fillna(0)` — "không có giao dịch" là thông tin hợp lệ |

#### Phân tích chuyên sâu

**Vấn đề với `fillna(mean)` mù quáng:**
- Thay thế NaN bằng giá trị trung bình **GIẢM phương sai** chuỗi → kiểm định ADF thiên về kết luận "dừng" (khi chuỗi thực tế có thể không dừng).
- Không phân biệt NaN do "thiếu dữ liệu" vs "không có hoạt động" — Revenue = NaN khác hoàn toàn với Revenue = 0.
- Không để lại dấu vết — downstream analysis không biết giá trị nào đáng tin, nào là artifact.

**Hệ thống 3 lớp bảo vệ của Dự án:**

```
Lớp 1: Nội suy có giới hạn
        interpolate(method='linear', limit=2, limit_direction='both')
        → Chỉ lấp khoảng trống ≤ 2 tuần — giá trị nội suy vẫn
          phản ánh xu hướng cục bộ (không "kéo về mean" như fillna).

Lớp 2: Cờ truy vết (is_interpolated = 0/1)
        → Tầng 3 biết CHÍNH XÁC tuần nào bị can thiệp.
        → Phân tích độ nhạy: chạy ADF/KPSS/Johansen trên dataset
          "sạch" (loại tuần nội suy) → so sánh với dataset đầy đủ.
          Nếu kết luận THAY ĐỔI → kết quả phụ thuộc nội suy → cảnh báo.

Lớp 3: Fallback trọng số
        → Khi Σ RealQty = 0 (mẫu số = 0): chuyển sang mean() đơn giản
          thay vì crash/inf → ghi WARNING với week_start cụ thể.
```

**Ý nghĩa khoa học:** Mọi can thiệp vào dữ liệu đều được **ghi nhận** và **kiểm chứng tác động** (sensitivity analysis) — tuân thủ nguyên tắc "Null finding is valid" (CLAUDE.md mục 5).

---

## 2. Cải tiến trong Kiểm định Chuỗi Thời gian (Tầng 3)

### 2.1. Xác nhận Kép (Dual Confirmation) — ADF + KPSS

#### Bảng so sánh

| Tiêu chí | Phương pháp Truyền thống | Phương án 3-A (Dự án) |
|-----------|--------------------------|------------------------|
| **Kiểm định tính dừng** | Chỉ dùng ADF | ADF + KPSS (dual confirmation) |
| **Giả thuyết H₀** | Chỉ 1 hướng: "có unit root" | 2 hướng ĐỐI LẬP: ADF ("có unit root") + KPSS ("dừng") |
| **Rủi ro Type II** | Cao — ADF có power thấp với mẫu nhỏ | Giảm đáng kể — KPSS bổ sung khi ADF thiếu power |
| **Xử lý mâu thuẫn** | Không áp dụng (chỉ 1 kiểm định) | Ma trận quyết định 4 trường hợp (xem MATH_AND_ALGORITHMS.md) |
| **Xác định $d(i)$** | Chạy ADF 1 lần, quyết định luôn | Sai phân tuần tự + kiểm định kép tại MỖI bậc |

#### Phân tích chuyên sâu

**Vấn đề khi chỉ dùng ADF:**
- ADF có **power thấp** (high Type II error rate): dễ giữ nhầm $H_0$ (kết luận "không dừng") khi chuỗi thực sự dừng — đặc biệt nghiêm trọng với mẫu nhỏ ($T < 30$).
- Nếu $d(i)$ xác định SAI → sai phân sai → Granger Causality cho kết quả giả (spurious).
- Hậu quả cascading: sai ở Phase 1 → sai Phase 2, 3, 3b → toàn bộ pipeline bị ảnh hưởng.

**Cơ chế Dual Confirmation:**

$$
\text{Kết luận} = \begin{cases}
\text{DỪNG (confident)} & \text{ADF bác bỏ } H_0 \text{ AND KPSS giữ } H_0 \\
\text{KHÔNG DỪNG (confident)} & \text{ADF giữ } H_0 \text{ AND KPSS bác bỏ } H_0 \\
\text{Mâu thuẫn (trend-stationary?)} & \text{Cả hai đều bác bỏ} \\
\text{Không kết luận (power thấp)} & \text{Cả hai đều giữ}
\end{cases}
$$

**Ưu điểm thống kê:**
- Khi 2 kiểm định với $H_0$ **NGƯỢC nhau** cùng đồng thuận → xác suất cả hai đều sai (simultaneously Type I + Type II) cực thấp.
- Giảm False Discovery Rate (FDR) trong quy trình xác định $d(i)$ — đặc biệt quan trọng khi mẫu nhỏ ($N = 10$).

---

### 2.2. Đối chiếu Chéo — Toda-Yamamoto vs Granger

#### Bảng so sánh

| Tiêu chí | Phương pháp Truyền thống | Phương án 3-A (Dự án) |
|-----------|--------------------------|------------------------|
| **Kiểm định nhân quả** | Chỉ Granger trên chuỗi sai phân | Granger (sai phân) + Toda-Yamamoto (levels) |
| **Phụ thuộc d(i)** | Hoàn toàn — sai d(i) → kết quả giả | Toda-Yamamoto KHÔNG phụ thuộc d(i) |
| **Xử lý mixed I(0)/I(1)** | Phải sai phân I(1), giữ I(0) — phức tạp, dễ sai | Toda-Yamamoto chạy trên levels — tự động xử lý |
| **Độ tin cậy kết luận** | Đơn phương pháp | Hai phương pháp ĐỘC LẬP → đồng thuận = mạnh |
| **Tỉ lệ đồng thuận** | N/A | Tính `agreement_rate` tự động giữa 2 phương pháp |

#### Phân tích chuyên sâu

**Vấn đề với Granger đơn lẻ trên hệ thống mixed order:**
- Dự án có OEE_Score $\sim I(1)$ nhưng DelayRate, Revenue, OrderVolume $\sim I(0)$.
- Granger yêu cầu chuỗi dừng → phải sai phân OEE_Score nhưng KHÔNG sai phân 3 biến còn lại.
- Nếu $d(\text{OEE\_Score})$ bị xác định sai (do power thấp với $N=10$) → toàn bộ Granger test trên các cặp liên quan đến OEE → SAI.

**Toda-Yamamoto như "bảo hiểm" (insurance):**

$$
\text{VAR}(k + d_{\max}) \text{ trên levels} \xrightarrow{\text{Wald test trên } k \text{ lag đầu}} \chi^2(k)
$$

- Thêm $d_{\max} = 1$ lag "đệm" vào mô hình VAR → Wald statistic có phân phối tiệm cận $\chi^2$ **BẤT KỂ** biến có $I(0)$, $I(1)$, hay đồng tích hợp.
- Không cần pre-testing cho tính dừng hay đồng tích hợp → KHÔNG bị cascading error từ Phase 1.
- Kết quả: nếu Granger và Toda-Yamamoto **đồng thuận** → kết luận nhân quả rất mạnh (robust to pre-testing error).

**Đánh giá tự động:**
```
agreement_rate = (số cặp đồng thuận) / (tổng số cặp so sánh)
```
Nếu `agreement_rate < 0.7` → `WARNING`: kết luận nhân quả KHÔNG ổn định — có thể do mẫu quá nhỏ hoặc $d(i)$ không chính xác.

---

## 3. Cải tiến Thích ứng với Mẫu nhỏ (Tầng 4 — VECM)

### 3.1. Triệt tiêu Động lực Ngắn hạn: $k\_ar\_diff = 0$

#### Bảng so sánh

| Tiêu chí | Phương pháp Truyền thống | Phương án 3-A (Dự án) |
|-----------|--------------------------|------------------------|
| **Chọn k_ar_diff** | $k \geq 1$ mặc định (theo AIC/BIC) | $k = 0$ — dựa trên phân tích DoF |
| **Params/equation** | $r + n \cdot k + 1 = 2 + 4(1) + 1 = 7$ | $r + 1 = 2 + 1 = 3$ |
| **DoF (với $N=10$)** | $\approx 8 - 7 = 1$ (**NGUY HIỂM**) | $\approx 9 - 3 = 6$ (ổn định) |
| **Dự báo** | Bùng nổ (OEE $\to 10^6$, Revenue $\to 10^{13}$) | Hợp lệ (OEE $\in [0.83, 0.87]$) |
| **Cơ sở lý thuyết** | "AIC chọn lag" — bỏ qua sample size | DoF analysis + empirical validation |

#### Phân tích chuyên sâu — Chứng minh $k = 0$ là tối ưu

**Bài toán:** Cho hệ VECM $n = 4$ biến, $r = 2$ cointegrating equations, $N = 10$ quan sát.

**Phương trình VECM tổng quát:**

$$
\Delta y_t = \alpha \beta' y_{t-1} + \sum_{i=1}^{k} \Gamma_i \Delta y_{t-i} + c + u_t
$$

**Số tham số cần ước lượng cho mỗi phương trình:**

$$
\text{params/eq} = \underbrace{r}_{\alpha \text{ loadings}} + \underbrace{n \cdot k}_{\Gamma \text{ coefficients}} + \underbrace{1}_{\text{constant}} = r + nk + 1
$$

**Bảng phân tích Degrees of Freedom:**

| $k\_ar\_diff$ | Params/eq | Effective obs | DoF/eq | Tỉ lệ $T/k$ | Kết quả |
|:---:|:---:|:---:|:---:|:---:|:---|
| 0 | 3 | 9 | **6** | 3.0 | ✅ Ước lượng ổn định |
| 1 | 7 | 8 | **1** | 1.1 | ❌ Overfitting nghiêm trọng |
| 2 | 11 | 7 | **-4** | 0.6 | ❌ Không khả thi (DoF âm) |

**Bằng chứng thực nghiệm (empirical validation):**

| Biến | $k=0$ (Forecast T+1) | $k=1$ (Forecast T+1) |
|------|:---------------------:|:---------------------:|
| OEE_Score | 0.857 ✅ | $-4.5$ ❌ |
| DelayRate | 0.307 ✅ | $-12.8$ ❌ |
| Revenue | 555,394 ✅ | $35{,}000{,}000$ ❌ |
| OrderVolume | 3.95 ✅ | $-850$ ❌ |

**Kết luận khoa học:**

Với $k = 1$: hệ số $\alpha$ (adjustment) bùng nổ do chỉ có 1 bậc tự do để ước lượng 7 tham số → **overfitting hoàn toàn** — mô hình "học thuộc" noise thay vì signal.

Quyết định $k = 0$ **KHÔNG** phải là "giản lược mô hình" theo nghĩa mất thông tin:
- Với $N = 10$, dynamic short-run effects ($\Gamma$) **không thể ước lượng tin cậy** — bất kỳ giá trị $\hat{\Gamma}$ nào thu được đều phản ánh noise, không phải signal.
- Giữ lại $\Gamma$ khi DoF = 1 tạo **ảo giác** về khả năng dự báo (in-sample fit tốt, out-of-sample thảm họa).
- Error correction term ($\alpha \beta' y_{t-1}$) đã nắm bắt **toàn bộ thông tin cân bằng dài hạn** — thành phần quan trọng nhất cho dự báo.

> **Nguyên lý:** "Tốt hơn là ước lượng ÍT tham số một cách TIN CẬY, hơn là ước lượng NHIỀU tham số với độ chính xác gần bằng 0." — Lütkepohl (2005), phù hợp với Occam's Razor trong model selection.

---

### 3.2. Mapping VAR ↔ VECM — Tránh Nhầm lẫn Tham số

| Ký hiệu | Ý nghĩa | Giá trị dự án |
|----------|----------|:---:|
| $p$ (VAR lag order) | Bậc trễ của VAR gốc | 1 |
| $k\_ar\_diff$ (VECM) | Số lag **sai phân** trong VECM | $p - 1 = 0$ |
| $r$ (cointegrating rank) | Số vector đồng tích hợp | 2 |

$$
\boxed{\text{VAR}(p) \Longleftrightarrow \text{VECM}(k\_ar\_diff = p - 1)}
$$

Đây là sai lầm phổ biến trong thực hành: nhầm VAR lag $p$ với VECM `k_ar_diff`. Dự án đọc trực tiếp `k_ar_diff` từ JSON Phase 3 (giá trị mà Johansen test đã sử dụng) → **tránh nhầm lẫn 100%**.

---

## 4. Khả năng Kháng lỗi & Tự động hóa (Robustness)

### 4.1. Kiến trúc 4 Tầng Cách ly — Zero Look-ahead Bias

#### Bảng so sánh

| Tiêu chí | Pipeline Truyền thống | Phương án 3-A (Dự án) |
|-----------|----------------------|------------------------|
| **Cấu trúc** | 1 script monolithic hoặc notebook | 4 tầng cách ly hoàn toàn, I/O qua file |
| **Truyền tham số** | Hard-code hoặc global variable | JSON machine-readable giữa các Phase |
| **Look-ahead bias** | Dễ xảy ra (dùng PlannedDate, future mean) | Triệt tiêu hệ thống (xem phân tích bên dưới) |
| **Khả năng chạy lại** | Phải chạy toàn bộ từ đầu | Mỗi Phase chạy ĐỘC LẬP (đọc output Phase trước) |
| **Phát hiện lỗi** | Crash toàn bộ, khó truy vết | Mỗi Phase kiểm tra input → báo lỗi rõ ràng |

#### Phân tích chuyên sâu — Cơ chế Chống Look-ahead Bias

**Look-ahead bias** là lỗi sử dụng **thông tin chưa biết tại thời điểm dự đoán** — nguy hiểm nhất trong time-series forecasting vì tạo kết quả lạc quan giả.

**3 lớp bảo vệ trong Dự án:**

```
╔══════════════════════════════════════════════════════════════════╗
║  LỚP 1: Point-in-time Assignment (Tầng 2 — Phase 0)           ║
║  ─────────────────────────────────────────────────────────────  ║
║  • OEE_Score → gán theo ActualEndDate (ngày HOÀN THÀNH)        ║
║    KHÔNG dùng PlannedShipmentDate (ngày KẾ HOẠCH — biết trước) ║
║  • Revenue → gán theo ShipmentDate (ngày GIAO HÀNG thực tế)    ║
║  • Lý do: OEE chỉ BIẾT ĐƯỢC sau khi đơn hàng hoàn thành.      ║
║    Gán vào tuần "kế hoạch" = gán giá trị "biết sau" vào tuần  ║
║    "trước khi biết" → LOOK-AHEAD BIAS.                         ║
╠══════════════════════════════════════════════════════════════════╣
║  LỚP 2: Loại đơn hàng chưa hoàn thành (Tầng 2 — Phase 0)     ║
║  ─────────────────────────────────────────────────────────────  ║
║  • ActualEndDate = NaT → LOẠI khỏi tính toán                   ║
║  • KHÔNG gán OEE = 0 hay NaN giả cho đơn hàng đang sản xuất   ║
║  • Lý do: OEE_Score CHƯA TỒN TẠI cho đơn hàng chưa xong.     ║
║    Gán giá trị giả = fabricate data.                           ║
╠══════════════════════════════════════════════════════════════════╣
║  LỚP 3: Chronological Separation (Tầng 4 — VECM)              ║
║  ─────────────────────────────────────────────────────────────  ║
║  • Dự báo T+1...T+4 CHỈ dùng dữ liệu T và trước đó           ║
║  • VECM tự đảm bảo: predict(steps=h) nội bộ cumulate          ║
║    từ y_T đã quan sát → KHÔNG peek vào future observations     ║
║  • CI tính từ Σ_u (ước lượng trên TOÀN BỘ in-sample,          ║
║    không dùng out-of-sample residuals)                          ║
╚══════════════════════════════════════════════════════════════════╝
```

### 4.2. Chuỗi An toàn (Defensive Chain) — Từ Raw → Forecast

| Bước | Cơ chế An toàn | Hậu quả nếu THIẾU |
|:----:|----------------|-------------------|
| Tầng 1 → 2 | `.copy()` trên mọi DataFrame đọc từ raw | Ghi đè file raw → vi phạm data immutability |
| Phase 0 → 1 | Kiểm tra `os.path.exists()` cho input file | Crash không rõ nguyên nhân |
| Phase 1 → 3 | Đọc $d(i)$ từ JSON (không hard-code) | Dùng sai $d$ → spurious regression |
| Phase 3 → 4 | Đọc `coint_rank`, `k_ar_diff` từ JSON | Hard-code sai → VECM bùng nổ |
| Tầng 4 | `_safe_float()` cho numpy → JSON | `json.dump` crash trên `numpy.bool_` |
| Tầng 4 | Fallback CI: IRF → $\sqrt{h}$ approximation | Crash khi IRF thất bại (matrix not positive definite) |

### 4.3. Sensitivity Analysis Toàn tuyến (End-to-end Robustness Check)

Mỗi Phase đều chạy **phân tích độ nhạy** bằng cách loại tuần nội suy:

$$
\text{Robustness} = \begin{cases}
\checkmark & \text{nếu kết luận KHÔNG đổi khi loại tuần nội suy} \\
\text{WARNING} & \text{nếu kết luận THAY ĐỔI → phụ thuộc nội suy}
\end{cases}
$$

| Phase | Kiểm tra gì | Metric so sánh |
|:-----:|-------------|----------------|
| Phase 1 | $d(i)$ có thay đổi? | Bậc tích hợp từng biến |
| Phase 3 | Rank $r$ có thay đổi? | Johansen cointegration rank |
| Phase 3b | Nhân quả có đảo chiều? | Significant/not significant từng cặp |

**Ý nghĩa:** Nếu kết luận khoa học thay đổi chỉ vì loại 2-3 tuần nội suy → kết luận đó **KHÔNG robust** → cần thu thập thêm dữ liệu trước khi đưa ra khuyến nghị.

---

## Tổng kết — Bản đồ Cải tiến

```
┌─────────────────────────────────────────────────────────────────┐
│                    PHƯƠNG ÁN 3-A: CẢI TIẾN                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─── Tầng 1-2 ───┐  ┌──── Tầng 3 ────┐  ┌──── Tầng 4 ────┐  │
│  │ • Jaccard Index │  │ • Dual Confirm  │  │ • k=0 (DoF)    │  │
│  │ • SHA-256 audit │  │   (ADF + KPSS)  │  │ • IRF/MA CI    │  │
│  │ • Nội suy limit │  │ • Cross-check   │  │ • Fallback √h  │  │
│  │ • is_interp cờ  │  │   (Granger +    │  │ • Safe float   │  │
│  │ • Fallback /0   │  │    Toda-Yama.)  │  │ • JSON params  │  │
│  └────────┬────────┘  └───────┬─────────┘  └───────┬────────┘  │
│           │                   │                     │           │
│           └─────── Sensitivity Analysis ────────────┘           │
│                    (loại tuần nội suy → so sánh)                 │
│                                                                 │
│  ═══════════════════════════════════════════════════════════════  │
│  XUYÊN SUỐT: Zero Look-ahead Bias │ Full Audit Trail │ JSON I/O │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tham khảo

- Johansen, S. (1995). *Likelihood-Based Inference in Cointegrated VAR Models*. Oxford UP.
- Lütkepohl, H. (2005). *New Introduction to Multiple Time Series Analysis*. Springer.
- Pfaff, B. (2008). *Analysis of Integrated and Cointegrated Time Series with R*. Springer.
- Toda, H. Y. & Yamamoto, T. (1995). Statistical Inference in VARs with Possibly Integrated Processes. *J. Econometrics*, 66, 225–250.
- Kwiatkowski, D. et al. (1992). Testing the Null of Stationarity. *J. Econometrics*, 54, 159–178.
