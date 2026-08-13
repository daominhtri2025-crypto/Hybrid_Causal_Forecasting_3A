<?php

namespace App\Http\Controllers\Dashboard;

use App\Http\Controllers\Controller;
use App\Services\PipelineDataService;
use Illuminate\Http\JsonResponse;

/**
 * Phase 3 — Kiểm định đồng tích hợp Johansen.
 * Trả về rank r, route (VECM/VAR), chi tiết Trace + Max-Eigenvalue test.
 */
class CointegrationController extends Controller
{
    public function __construct(
        private PipelineDataService $pipeline
    ) {}

    public function __invoke(): JsonResponse
    {
        try {
            $raw = $this->pipeline->loadPhaseData('phase3_cointegration');

            $johansen = $raw['johansen_result'] ?? [];
            $traceTest = $johansen['trace_test'] ?? [];
            $maxEigenTest = $johansen['max_eigen_test'] ?? [];

            // Route quyết định từ Phase 3
            $rank = $traceTest['rank'] ?? $maxEigenTest['rank'] ?? null;
            $nVariables = count($raw['metadata']['d_values_from_phase1'] ?? []);

            // Xác định route dựa trên rank
            $route = 'unknown';
            if ($rank !== null) {
                if ($rank === 0) {
                    $route = 'VAR_on_differences';
                } elseif ($rank > 0 && $rank < $nVariables) {
                    $route = 'VECM';
                } else {
                    // rank == n (full rank) → không đồng tích hợp → VAR trên levels
                    $route = 'VAR_on_levels';
                }
            }

            return response()->json([
                'status' => 'ok',
                'data'   => [
                    'metadata'    => $raw['metadata'],
                    'lag_selection' => $raw['lag_selection'] ?? null,
                    'rank'        => $rank,
                    'n_variables' => $nVariables,
                    'route'       => $raw['model_route'] ?? $route,
                    'route_explanation' => $this->explainRoute($route, $rank, $nVariables),
                    'trace_test'  => $traceTest,
                    'max_eigen_test' => $maxEigenTest,
                ],
            ]);
        } catch (\RuntimeException $e) {
            return response()->json([
                'status'  => 'error',
                'message' => $e->getMessage(),
            ], str_contains($e->getMessage(), 'không tìm thấy') ? 404 : 422);
        }
    }

    private function explainRoute(string $route, ?int $rank, int $n): string
    {
        return match ($route) {
            'VAR_on_levels' => "Johansen rank = {$rank} (full rank = {$n}) → Không có đồng tích hợp → VAR trên mức gốc (levels).",
            'VECM' => "Johansen rank = {$rank} (0 < r < {$n}) → Có {$rank} quan hệ đồng tích hợp → VECM.",
            'VAR_on_differences' => "Johansen rank = 0 → Không có đồng tích hợp → VAR trên sai phân.",
            default => "Không xác định được route từ dữ liệu.",
        };
    }
}
