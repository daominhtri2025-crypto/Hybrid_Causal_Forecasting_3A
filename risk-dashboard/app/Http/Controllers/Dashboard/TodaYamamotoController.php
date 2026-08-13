<?php

namespace App\Http\Controllers\Dashboard;

use App\Http\Controllers\Controller;
use App\Services\PipelineDataService;
use Illuminate\Http\JsonResponse;

/**
 * Phase 3b — Kiểm định Toda-Yamamoto.
 * Trả về bảng so sánh Granger vs TY (cross-check nhân quả).
 */
class TodaYamamotoController extends Controller
{
    public function __construct(
        private PipelineDataService $pipeline
    ) {}

    public function __invoke(): JsonResponse
    {
        try {
            $rawTY = $this->pipeline->loadPhaseData('phase3b_toda_yamamoto');
            $tyPairs = $rawTY['pairwise_results'] ?? [];

            // Thử load Granger để so sánh song song
            $grangerPairs = [];
            try {
                $rawGranger = $this->pipeline->loadPhaseData('phase2_granger');
                $grangerPairs = $rawGranger['pairwise_results'] ?? [];
            } catch (\RuntimeException) {
                // Granger data không bắt buộc cho endpoint này
            }

            // Xây bảng so sánh: mỗi cặp cause→effect có cả kết quả Granger lẫn TY
            $comparison = [];
            foreach ($tyPairs as $ty) {
                $cause = $ty['cause'];
                $effect = $ty['effect'];

                // Tìm cặp Granger tương ứng
                $granger = $this->findPair($grangerPairs, $cause, $effect);

                $comparison[] = [
                    'cause'  => $cause,
                    'effect' => $effect,
                    // Toda-Yamamoto
                    'ty_wald_statistic' => $ty['wald_statistic'] ?? null,
                    'ty_p_value'        => $ty['p_value'] ?? null,
                    'ty_significant'    => $ty['significant'] ?? false,
                    'ty_conclusion'     => $ty['conclusion'] ?? '',
                    // Granger (nếu có)
                    'granger_f_statistic' => $this->extractFStat($granger),
                    'granger_p_value'     => $granger['best_p_value'] ?? null,
                    'granger_significant' => $granger['significant'] ?? null,
                    // Đồng thuận?
                    'agreement' => ($granger !== null)
                        ? ($ty['significant'] === $granger['significant'] ? 'agree' : 'disagree')
                        : 'granger_missing',
                ];
            }

            // Tính tỷ lệ đồng thuận
            $withGranger = array_filter($comparison, fn($c) => $c['agreement'] !== 'granger_missing');
            $agreeCount = count(array_filter($withGranger, fn($c) => $c['agreement'] === 'agree'));
            $agreementPct = count($withGranger) > 0
                ? round($agreeCount / count($withGranger) * 100, 0)
                : null;

            return response()->json([
                'status' => 'ok',
                'data'   => [
                    'metadata'    => $rawTY['metadata'],
                    'k'           => $rawTY['k'] ?? null,
                    'd_max'       => $rawTY['d_max'] ?? null,
                    'total_var_lags' => $rawTY['total_var_lags'] ?? null,
                    'comparison'  => $comparison,
                    'summary'     => [
                        'ty_significant_count' => count(array_filter($tyPairs, fn($p) => $p['significant'] ?? false)),
                        'total_pairs'          => count($tyPairs),
                        'agreement_pct'        => $agreementPct,
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

    private function findPair(array $pairs, string $cause, string $effect): ?array
    {
        foreach ($pairs as $p) {
            if (($p['cause'] ?? '') === $cause && ($p['effect'] ?? '') === $effect) {
                return $p;
            }
        }
        return null;
    }

    private function extractFStat(?array $pair): ?float
    {
        if ($pair === null) return null;
        $bestLag = (string) ($pair['best_lag'] ?? '');
        return $pair['lag_results'][$bestLag]['f_statistic'] ?? null;
    }
}
