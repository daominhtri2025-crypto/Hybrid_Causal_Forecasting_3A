<?php

namespace App\Http\Controllers\Dashboard;

use App\Http\Controllers\Controller;
use App\Services\PipelineDataService;
use Illuminate\Http\JsonResponse;

/**
 * Phase 2 — Kiểm định nhân quả Granger.
 * Trả về ma trận pairwise (cause × effect) với p-value và significance.
 */
class GrangerController extends Controller
{
    public function __construct(
        private PipelineDataService $pipeline
    ) {}

    public function __invoke(): JsonResponse
    {
        try {
            $raw = $this->pipeline->loadPhaseData('phase2_granger');
            $pairs = $raw['pairwise_results'] ?? [];
            $alpha = config('dashboard.significance_level');

            // Transform: mỗi cặp → row cho heatmap + data table
            $pairRows = [];
            foreach ($pairs as $pair) {
                $pairRows[] = [
                    'cause'       => $pair['cause'],
                    'effect'      => $pair['effect'],
                    'best_lag'    => $pair['best_lag'] ?? null,
                    'p_value'     => $pair['best_p_value'] ?? null,
                    'f_statistic' => $this->extractBestFStat($pair),
                    'significant' => $pair['significant'] ?? false,
                    'conclusion'  => $pair['conclusion'] ?? '',
                ];
            }

            // Xây dựng ma trận 2D cho heatmap: cause (rows) × effect (cols)
            $variables = $this->extractVariables($pairRows);
            $heatmapMatrix = $this->buildHeatmapMatrix($pairRows, $variables);

            return response()->json([
                'status' => 'ok',
                'data'   => [
                    'metadata'        => $raw['metadata'],
                    'lag_selection'    => $raw['lag_selection'] ?? null,
                    'significance'    => $alpha,
                    'pairs'           => $pairRows,
                    'heatmap'         => [
                        'variables' => $variables,
                        'matrix'    => $heatmapMatrix,
                    ],
                    'summary' => [
                        'total_pairs'      => count($pairRows),
                        'significant_count' => count(array_filter($pairRows, fn($p) => $p['significant'])),
                    ],
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
     * Trích F-statistic từ lag_results theo best_lag.
     */
    private function extractBestFStat(array $pair): ?float
    {
        $bestLag = (string) ($pair['best_lag'] ?? '');
        return $pair['lag_results'][$bestLag]['f_statistic'] ?? null;
    }

    /**
     * Trích danh sách biến duy nhất từ kết quả pairwise.
     */
    private function extractVariables(array $pairRows): array
    {
        $vars = [];
        foreach ($pairRows as $row) {
            $vars[$row['cause']] = true;
            $vars[$row['effect']] = true;
        }
        return array_keys($vars);
    }

    /**
     * Xây dựng ma trận p-value 2D cho heatmap.
     * Cell [cause][effect] = p_value. Đường chéo (cause == effect) = null.
     */
    private function buildHeatmapMatrix(array $pairRows, array $variables): array
    {
        // Khởi tạo ma trận null
        $matrix = [];
        foreach ($variables as $cause) {
            foreach ($variables as $effect) {
                $matrix[$cause][$effect] = null;
            }
        }

        // Đổ dữ liệu từ pairwise
        foreach ($pairRows as $row) {
            $matrix[$row['cause']][$row['effect']] = [
                'p_value'     => $row['p_value'],
                'significant' => $row['significant'],
                'lag'         => $row['best_lag'],
            ];
        }

        return $matrix;
    }
}
