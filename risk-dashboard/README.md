# Dashboard Phan tich Lan truyen Rui ro Van hanh

> **Operational Risk Propagation Analysis Dashboard**
>
> Ung dung web truc quan hoa ket qua tu mo hinh VAR (Vector Autoregression)
> 3 bien: ProductionVolume, DelayRate, OrderDemand.

## Gioi thieu

Dashboard doc cac file JSON output tu Python Pipeline (Phuong An 3-A) va
hien thi tren giao dien web voi bieu do tuong tac. Dashboard hoat dong
hoan toan **READ-ONLY** — khong tinh toan lai, khong ghi de du lieu.

**Cac trang phan tich:**

| Trang | Noi dung |
|---|---|
| Summary | KPI cards, cau hinh mo hinh, trang thai 6 Phase |
| Stationarity | Kiem dinh tinh dung ADF/KPSS voi verdict badges |
| Granger | Heatmap nhan qua Granger + bang chi tiet |
| Cointegration | Kiem dinh dong tich hop Johansen + route decision |
| Toda-Yamamoto | Bang cross-check Granger vs Toda-Yamamoto |
| Forecast | Bieu do du bao 4 tuan voi 95% CI bands |
| IRF | Impulse Response Functions theo tung bien phan ung |
| FEVD | Stacked area FEVD voi Null Finding callout |

## Yeu cau he thong (Prerequisites)

| Phan mem | Phien ban toi thieu | Kiem tra |
|---|---|---|
| PHP | 8.3+ | `php -v` |
| Composer | 2.x | `composer -V` |
| Node.js | 18+ | `node -v` |
| NPM | 9+ | `npm -v` |

> **Luu y:** Dashboard khong su dung database cho du lieu pipeline.
> SQLite chi dung cho session/cache cua Laravel (tu dong tao).

## Cai dat (Installation)

### Buoc 1: Clone hoac giai nen du an

```bash
# Neu tu file nen:
unzip risk-dashboard-v1.zip
cd risk-dashboard

# Hoac neu tu Git:
git clone <url-repo> risk-dashboard
cd risk-dashboard
```

### Buoc 2: Cai dat PHP dependencies

```bash
composer install
```

### Buoc 3: Cai dat Node.js dependencies

```bash
npm install
```

### Buoc 4: Cau hinh moi truong

```bash
# Copy file cau hinh mau
cp .env.example .env

# Tao application key
php artisan key:generate
```

### Buoc 5: Tao database SQLite (cho session/cache)

```bash
touch database/database.sqlite
php artisan migrate
```

### Buoc 6: Cau hinh duong dan du lieu (QUAN TRONG)

Mo file `.env` va chinh sua bien `PIPELINE_REPORTS_PATH`:

```dotenv
PIPELINE_REPORTS_PATH=/duong/dan/tuyet/doi/den/Phuong_An_3/reports
```

**Huong dan chi tiet:**

Bien `PIPELINE_REPORTS_PATH` tro den thu muc `reports/` cua Python Pipeline,
noi chua 6 file JSON output:

```
reports/
  ├── phase1_stationarity.json
  ├── phase2_granger_causality.json
  ├── phase3_cointegration.json
  ├── phase3b_toda_yamamoto.json
  ├── tang4_vecm_results.json
  └── phase5_irf_fevd_results.json
```

**Vi du tren Windows:**

```dotenv
PIPELINE_REPORTS_PATH=D:\CLAUDE COWORD\NCS_TIEN_SI_2026\Phuong_An_3\reports
```

**Vi du tren Linux/macOS:**

```dotenv
PIPELINE_REPORTS_PATH=/home/user/Phuong_An_3/reports
```

> **Luu y:**
> - Dung duong dan **tuyet doi** (absolute path), khong dung duong dan tuong doi.
> - Neu duong dan chua dau cach (Windows), ghi nguyen — khong can dau ngoac kep.
> - Thu muc `reports/` phai chua du 6 file JSON o tren. Neu thieu file,
>   trang tuong ung se hien thong bao loi (khong crash).
> - Neu khong set bien nay, Laravel se mac dinh tim o
>   `../Hybrid_Causal_Forecasting_3A/reports` (tuong doi tu thu muc goc du an web).

### Buoc 7: Build frontend

```bash
npm run build
```

## Khoi chay (Run)

```bash
php artisan serve
```

Mo trinh duyet tai: **http://localhost:8000**

Trang chu (`/`) tu dong chuyen huong den trang Summary.

## Cau truc du an

```
risk-dashboard/
├── app/
│   ├── Http/Controllers/Dashboard/   # 7 API controllers (READ-ONLY)
│   └── Services/PipelineDataService.php  # Doc/parse file JSON
├── config/dashboard.php              # Mapping Phase → file JSON, target variables
├── resources/
│   ├── css/app.css                   # Tailwind 4 + dark theme tokens
│   ├── js/app.js                     # Chart.js 4 + global utilities
│   └── views/
│       ├── layouts/dashboard.blade.php  # Master layout voi sidebar
│       └── dashboard/                   # 8 trang Blade
├── routes/
│   ├── api.php                       # 8 GET endpoints (/api/dashboard/*)
│   └── web.php                       # 8 Route::view endpoints
└── .env                              # PIPELINE_REPORTS_PATH config o day
```

## Cong nghe su dung

- **Backend:** Laravel 13 (PHP 8.3)
- **Frontend:** Blade Templates + Tailwind CSS 4 (dark theme)
- **Bieu do:** Chart.js 4.x + chartjs-plugin-annotation
- **Build tool:** Vite 8
- **Du lieu:** Doc JSON files tu Python Pipeline (khong dung database cho data)

## Luu y quan trong

- Dashboard la **READ-ONLY**: chi doc du lieu tu file JSON, khong bao gio
  ghi de hay tinh toan lai ket qua thong ke.
- Khi Python Pipeline chay lai va tao JSON moi, chi can **restart Laravel
  server** (hoac reload trang) de dashboard cap nhat — khong can build lai.
- Config mapping file JSON nam tai `config/dashboard.php`. Neu Pipeline doi
  ten file output, chi can sua mapping o day.
