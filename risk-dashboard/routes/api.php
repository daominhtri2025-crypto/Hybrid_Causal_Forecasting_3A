<?php

use App\Http\Controllers\Dashboard\CointegrationController;
use App\Http\Controllers\Dashboard\ForecastController;
use App\Http\Controllers\Dashboard\GrangerController;
use App\Http\Controllers\Dashboard\IrfFevdController;
use App\Http\Controllers\Dashboard\StationarityController;
use App\Http\Controllers\Dashboard\SummaryController;
use App\Http\Controllers\Dashboard\TodaYamamotoController;
use Illuminate\Support\Facades\Route;

/*
|--------------------------------------------------------------------------
| Dashboard API Routes
|--------------------------------------------------------------------------
|
| Prefix: /api
| Tất cả endpoint đều READ-ONLY (GET) — Dashboard không ghi dữ liệu.
| Mỗi endpoint parse 1 file JSON từ Python Pipeline và trả về cấu trúc
| đã transform, sẵn sàng cho Chart.js frontend.
|
*/

Route::prefix('dashboard')->group(function () {

    // Tổng quan hệ thống: model route, KPI cards, trạng thái Phase
    Route::get('/summary', SummaryController::class);

    // Phase 1: Kiểm định tính dừng ADF/KPSS
    Route::get('/stationarity', StationarityController::class);

    // Phase 2: Kiểm định nhân quả Granger (heatmap + data table)
    Route::get('/granger', GrangerController::class);

    // Phase 3: Kiểm định đồng tích hợp Johansen (rank, route)
    Route::get('/cointegration', CointegrationController::class);

    // Phase 3b: Toda-Yamamoto cross-check (bảng so sánh Granger vs TY)
    Route::get('/toda-yamamoto', TodaYamamotoController::class);

    // Phase 4: Dự báo VAR 4 tuần + CI 95%
    Route::get('/forecast', ForecastController::class);

    // Phase 5: IRF — Impulse Response Functions
    Route::get('/irf', [IrfFevdController::class, 'irf']);

    // Phase 5: FEVD — Forecast Error Variance Decomposition
    Route::get('/fevd', [IrfFevdController::class, 'fevd']);
});
