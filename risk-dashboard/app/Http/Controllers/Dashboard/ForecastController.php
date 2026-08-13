<?php

namespace App\Http\Controllers\Dashboard;

use App\Http\Controllers\Controller;
use App\Services\PipelineDataService;
use Illuminate\Http\JsonResponse;

/**
 * Phase 4 — Dự báo VAR.
 * Trả về dự báo 4 tuần + khoảng tin cậy 95% cho 3 biến,
 * cùng diagnostics mô hình và hệ số VAR.
 */
class ForecastController extends Controller
{
    public function __construct(
        private PipelineDataService $pipeline
    ) {}

    public function __invoke(): JsonResponse
    {
        try {
            $raw = $this->pipeline->loadPhaseData('phase4_forecast');

            $forecast = $raw['forecast'] ?? [];
            $diagnostics = $raw['model_diagnostics'] ?? [];
            $params = $raw['locked_parameters'] ?? [];

            // Transform dự báo thành cấu trúc chart-friendly:
            // Mỗi biến → mảng objects {date, point, lower, upper}
            $chartData = $this->transformForChart($forecast);

            return response()->json([
                'status' => 'ok',
                'data'   => [
                    'metadata' => $raw['metadata'],
                    'model'    => [
                        'route'     => $params['route'] ?? 'unknown',
                        'lag_order' => $params['lag_order'] ?? null,
                        'trend'     => $params['trend'] ?? null,
                    ],
                    'diagnostics' => [
                        'log_likelihood'    => $diagnostics['log_likelihood'] ?? null,
                        'aic'               => $diagnostics['aic'] ?? null,
                        'bic'               => $diagnostics['bic'] ?? null,
                        'effective_obs'     => $diagnostics['effective_observations'] ?? null,
                        'df_per_equation'   => $diagnostics['degrees_of_freedom_per_equation'] ?? null,
                        'total_parameters'  => $diagnostics['total_parameters'] ?? null,
                    ],
                    'forecast' => [
                        'dates'     => $forecast['dates'] ?? [],
                        'variables' => $chartData,
                    ],
                    'warnings' => $raw['warnings'] ?? [],
                ],
            ]);
        } catch (\RuntimeException $e) {
            return response()->json([
                'status'  => 'error',
                'message' => $e->getMessage(),
            ], str_contains($e->getMessage(), 'không tìm thấy') ? 404 : 422);
        }
    }

    /**
     * Transform forecast data thành cấu trúc mà Chart.js dễ consume:
     * { "VariableName": [ {date, point, lower, upper, se}, ... ] }
     */
    private function transformForChart(array $forecast): array
    {
        $dates = $forecast['dates'] ?? [];
        $points = $forecast['point_forecasts'] ?? [];
        $lowers = $forecast['lower_95'] ?? [];
        $uppers = $forecast['upper_95'] ?? [];
        $ses = $forecast['standard_errors'] ?? [];

        $chartData = [];

        foreach ($points as $variable => $values) {
            $series = [];
            foreach ($values as $i => $pointValue) {
                $series[] = [
                    'date'  => $dates[$i] ?? null,
                    'point' => round($pointValue, 6),
                    'lower' => isset($lowers[$variable][$i]) ? round($lowers[$variable][$i], 6) : null,
                    'upper' => isset($uppers[$variable][$i]) ? round($uppers[$variable][$i], 6) : null,
                    'se'    => isset($ses[$variable][$i]) ? round($ses[$variable][$i], 6) : null,
                ];
            }
            $chartData[$variable] = $series;
        }

        return $chartData;
    }
}
