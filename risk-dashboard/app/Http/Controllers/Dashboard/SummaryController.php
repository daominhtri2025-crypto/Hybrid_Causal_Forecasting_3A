<?php

namespace App\Http\Controllers\Dashboard;

use App\Http\Controllers\Controller;
use App\Services\PipelineDataService;
use Illuminate\Http\JsonResponse;

/**
 * Tổng quan hệ thống: model route, KPI, trạng thái các Phase.
 */
class SummaryController extends Controller
{
    public function __construct(
        private PipelineDataService $pipeline
    ) {}

    public function __invoke(): JsonResponse
    {
        try {
            $summary = $this->pipeline->getSummary();

            return response()->json([
                'status' => 'ok',
                'data'   => $summary,
            ]);
        } catch (\RuntimeException $e) {
            return response()->json([
                'status'  => 'error',
                'message' => $e->getMessage(),
            ], 500);
        }
    }
}
