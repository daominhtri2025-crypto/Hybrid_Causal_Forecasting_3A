<?php

namespace App\Http\Controllers\Dashboard;

use App\Http\Controllers\Controller;
use App\Services\PipelineDataService;
use Illuminate\Http\JsonResponse;

/**
 * Phase 5 — IRF (Impulse Response Functions) và FEVD (Forecast Error Variance Decomposition).
 * Hai endpoint riêng biệt: /api/irf và /api/fevd.
 */
class IrfFevdController extends Controller
{
    public function __construct(
        private PipelineDataService $pipeline
    ) {}

    /**
     * GET /api/irf
     * Trả về IRF data — phản ứng đẩy cho từng cặp shock→response.
     * Trọng tâm: 3 biểu đồ *→DelayRate (tác động lên trễ giao hàng).
     */
    public function irf(): JsonResponse
    {
        try {
            $raw = $this->pipeline->loadPhaseData('phase5_irf_fevd');

            $irfRaw = $raw['irf'] ?? [];
            $ordering = $raw['metadata']['cholesky_ordering'] ?? [];
            $periods = $raw['metadata']['irf_periods'] ?? 12;

            // Transform: parse key pattern "{shock}_shock_to_{response}"
            $irfParsed = [];
            foreach ($irfRaw as $key => $values) {
                $parsed = $this->parseIrfKey($key);
                if ($parsed === null) continue;

                $irfParsed[] = [
                    'shock'    => $parsed['shock'],
                    'response' => $parsed['response'],
                    'key'      => $key,
                    'data'     => [
                        'horizons'  => range(0, count($values['irf_values'] ?? []) - 1),
                        'irf_values' => $values['irf_values'] ?? [],
                        'lower_95'   => $values['lower_95'] ?? [],
                        'upper_95'   => $values['upper_95'] ?? [],
                        'std_errors' => $values['std_errors'] ?? [],
                    ],
                ];
            }

            // Nhóm theo response variable — frontend cần nhóm theo biến chịu tác động
            $byResponse = [];
            foreach ($irfParsed as $irf) {
                $byResponse[$irf['response']][] = $irf;
            }

            return response()->json([
                'status' => 'ok',
                'data'   => [
                    'metadata' => [
                        'irf_periods'       => $periods,
                        'cholesky_ordering'  => $ordering,
                        'orthogonalization'  => $raw['metadata']['orthogonalization'] ?? null,
                        'ci_method'          => $raw['metadata']['ci_method'] ?? null,
                    ],
                    'model' => $raw['locked_parameters'] ?? [],
                    'all_pairs'   => $irfParsed,
                    'by_response' => $byResponse,
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
     * GET /api/fevd
     * Trả về FEVD data — phân rã phương sai cho từng biến mục tiêu.
     * Trọng tâm: DelayRate (94%+ tự giải thích → Null Finding).
     */
    public function fevd(): JsonResponse
    {
        try {
            $raw = $this->pipeline->loadPhaseData('phase5_irf_fevd');

            $fevdRaw = $raw['fevd'] ?? [];
            $ordering = $raw['metadata']['cholesky_ordering'] ?? [];

            // Transform FEVD thành cấu trúc stacked-area-friendly
            $fevdParsed = [];
            foreach ($fevdRaw as $targetVar => $sources) {
                $nHorizons = 0;
                $stackedData = [];

                foreach ($sources as $sourceVar => $values) {
                    $nHorizons = max($nHorizons, count($values));
                    $stackedData[$sourceVar] = array_map(
                        fn($v) => round($v * 100, 2),  // chuyển sang phần trăm
                        $values
                    );
                }

                // Validation: tổng tại mỗi horizon phải ≈ 100%
                $sumCheck = [];
                for ($h = 0; $h < $nHorizons; $h++) {
                    $total = 0;
                    foreach ($stackedData as $values) {
                        $total += $values[$h] ?? 0;
                    }
                    $sumCheck[] = round($total, 2);
                }

                $fevdParsed[$targetVar] = [
                    'horizons'    => range(1, $nHorizons),
                    'sources'     => $stackedData,
                    'sum_check'   => $sumCheck,
                    'self_pct_final' => $stackedData[$targetVar][count($stackedData[$targetVar] ?? []) - 1] ?? null,
                ];
            }

            // Null Finding highlight: tỷ lệ DelayRate tự giải thích
            $nullFinding = null;
            if (isset($fevdParsed['DelayRate'])) {
                $drSelf = $fevdParsed['DelayRate']['sources']['DelayRate'] ?? [];
                $nullFinding = [
                    'variable'         => 'DelayRate',
                    'self_pct_h1'      => $drSelf[0] ?? null,
                    'self_pct_h4'      => $drSelf[3] ?? null,
                    'self_pct_h8'      => $drSelf[7] ?? null,
                    'self_pct_h12'     => $drSelf[11] ?? null,
                    'interpretation'   => 'DelayRate chủ yếu mang tính tự hồi quy — '
                        . 'trễ giao hàng sinh ra từ nút thắt nội bộ, '
                        . 'không phải từ cú sốc sản lượng hay áp lực đơn hàng.',
                ];
            }

            return response()->json([
                'status' => 'ok',
                'data'   => [
                    'metadata' => [
                        'cholesky_ordering' => $ordering,
                    ],
                    'model'        => $raw['locked_parameters'] ?? [],
                    'variables'    => $fevdParsed,
                    'null_finding' => $nullFinding,
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
     * Parse IRF key: "ProductionVolume_shock_to_DelayRate"
     * → ['shock' => 'ProductionVolume', 'response' => 'DelayRate']
     */
    private function parseIrfKey(string $key): ?array
    {
        if (!str_contains($key, '_shock_to_')) {
            return null;
        }

        $parts = explode('_shock_to_', $key, 2);
        if (count($parts) !== 2) {
            return null;
        }

        return [
            'shock'    => $parts[0],
            'response' => $parts[1],
        ];
    }
}
