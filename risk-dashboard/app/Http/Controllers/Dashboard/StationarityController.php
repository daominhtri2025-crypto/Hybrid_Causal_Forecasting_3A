<?php

namespace App\Http\Controllers\Dashboard;

use App\Http\Controllers\Controller;
use App\Services\PipelineDataService;
use Illuminate\Http\JsonResponse;

/**
 * Phase 1 — Kiểm định tính dừng ADF/KPSS.
 * Trả về bảng tóm tắt bậc tích hợp d(i) cho từng biến.
 */
class StationarityController extends Controller
{
    public function __construct(
        private PipelineDataService $pipeline
    ) {}

    public function __invoke(): JsonResponse
    {
        try {
            $raw = $this->pipeline->loadPhaseData('phase1_stationarity');
            $results = $raw['results'] ?? [];

            // Transform sang cấu trúc phẳng cho frontend table
            $tableRows = [];
            foreach ($results as $variable => $detail) {
                $levelTests = $detail['tests']['level'] ?? [];

                $tableRows[] = [
                    'variable'          => $variable,
                    'integration_order' => $detail['integration_order'] ?? null,
                    'adf_statistic'     => $levelTests['adf']['statistic'] ?? null,
                    'adf_p_value'       => $levelTests['adf']['p_value'] ?? null,
                    'adf_reject'        => $levelTests['adf']['reject_h0'] ?? null,
                    'kpss_statistic'    => $levelTests['kpss']['statistic'] ?? null,
                    'kpss_p_value'      => $levelTests['kpss']['p_value'] ?? null,
                    'kpss_reject'       => $levelTests['kpss']['reject_h0'] ?? null,
                    'conclusion'        => $levelTests['conclusion'] ?? 'unknown',
                ];
            }

            // Tóm tắt d_max
            $dMax = $raw['summary']['d_max']
                ?? max(array_column($tableRows, 'integration_order'))
                ?? 0;

            return response()->json([
                'status' => 'ok',
                'data'   => [
                    'metadata' => $raw['metadata'],
                    'table'    => $tableRows,
                    'd_max'    => $dMax,
                ],
            ]);
        } catch (\RuntimeException $e) {
            return response()->json([
                'status'  => 'error',
                'message' => $e->getMessage(),
            ], $this->errorCode($e));
        }
    }

    private function errorCode(\RuntimeException $e): int
    {
        return str_contains($e->getMessage(), 'không tìm thấy') ? 404 : 422;
    }
}
