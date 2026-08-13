<?php

return [

    /*
    |--------------------------------------------------------------------------
    | Pipeline Reports Path
    |--------------------------------------------------------------------------
    |
    | Đường dẫn tuyệt đối đến thư mục reports/ của Python Pipeline.
    | Dashboard chỉ ĐỌC file JSON từ thư mục này — không bao giờ ghi.
    |
    */

    'reports_path' => env('PIPELINE_REPORTS_PATH', base_path('../Hybrid_Causal_Forecasting_3A/reports')),

    /*
    |--------------------------------------------------------------------------
    | JSON File Mapping
    |--------------------------------------------------------------------------
    |
    | Mapping tên Phase → tên file JSON tương ứng trong reports/.
    | Nếu Python Pipeline đổi tên file output, chỉ cần sửa ở đây.
    |
    */

    'json_files' => [
        'phase1_stationarity'    => 'phase1_stationarity.json',
        'phase2_granger'         => 'phase2_granger_causality.json',
        'phase3_cointegration'   => 'phase3_cointegration.json',
        'phase3b_toda_yamamoto'  => 'phase3b_toda_yamamoto.json',
        'phase4_forecast'        => 'tang4_vecm_results.json',
        'phase5_irf_fevd'        => 'phase5_irf_fevd_results.json',
    ],

    /*
    |--------------------------------------------------------------------------
    | Target Variables
    |--------------------------------------------------------------------------
    |
    | Ba biến số thực chứng trong hệ thống 3 biến mới.
    | Dùng để lọc kết quả khi file JSON vẫn còn chứa dữ liệu 4 biến cũ.
    |
    */

    'target_variables' => [
        'ProductionVolume',
        'DelayRate',
        'OrderDemand',
    ],

    /*
    |--------------------------------------------------------------------------
    | Significance Level
    |--------------------------------------------------------------------------
    */

    'significance_level' => 0.05,

];
