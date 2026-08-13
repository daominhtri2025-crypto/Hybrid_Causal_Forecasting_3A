<?php

namespace App\Services;

use Illuminate\Support\Facades\Log;
use RuntimeException;

/**
 * Service duy nhất chịu trách nhiệm đọc và parse tất cả file JSON
 * từ Python Pipeline. Mọi Controller gọi qua Service này.
 *
 * KHÔNG tính toán lại bất kỳ kết quả thống kê nào — chỉ đọc và validate.
 */
class PipelineDataService
{
    private string $reportsPath;
    private array $jsonFiles;

    public function __construct()
    {
        $this->reportsPath = config('dashboard.reports_path');
        $this->jsonFiles = config('dashboard.json_files');
    }

    /**
     * Đọc và parse một file JSON theo tên Phase.
     *
     * @param string $phaseKey  Key trong config('dashboard.json_files'), vd: 'phase2_granger'
     * @return array            Dữ liệu đã parse từ JSON
     *
     * @throws RuntimeException Nếu file không tồn tại hoặc JSON không hợp lệ
     */
    public function loadPhaseData(string $phaseKey): array
    {
        $filename = $this->jsonFiles[$phaseKey] ?? null;

        if ($filename === null) {
            throw new RuntimeException(
                "Phase key không hợp lệ: '{$phaseKey}'. "
                . "Các key hợp lệ: " . implode(', ', array_keys($this->jsonFiles))
            );
        }

        $filePath = rtrim($this->reportsPath, '/') . '/' . $filename;

        // Kiểm tra file tồn tại
        if (!file_exists($filePath)) {
            throw new RuntimeException(
                "Pipeline report không tìm thấy: {$filename}. "
                . "Hãy chạy Python Pipeline (python -m scripts.{$phaseKey}) trước khi sử dụng Dashboard. "
                . "Đường dẫn kiểm tra: {$filePath}"
            );
        }

        // Đọc nội dung file
        $rawContent = file_get_contents($filePath);
        if ($rawContent === false) {
            throw new RuntimeException(
                "Không thể đọc file: {$filePath}. Kiểm tra quyền truy cập file."
            );
        }

        // Parse JSON
        $data = json_decode($rawContent, true);
        if (json_last_error() !== JSON_ERROR_NONE) {
            throw new RuntimeException(
                "JSON không hợp lệ trong {$filename}: " . json_last_error_msg()
                . ". File có thể bị hỏng — chạy lại Phase tương ứng."
            );
        }

        // Validate cấu trúc tối thiểu: mọi file Pipeline phải có key 'metadata'
        if (!isset($data['metadata'])) {
            throw new RuntimeException(
                "Schema mismatch: thiếu key 'metadata' trong {$filename}. "
                . "File có thể không phải output của Python Pipeline."
            );
        }

        Log::info("PipelineDataService: đã tải {$filename} thành công", [
            'phase' => $phaseKey,
            'timestamp' => $data['metadata']['timestamp'] ?? 'unknown',
        ]);

        return $data;
    }

    /**
     * Kiểm tra trạng thái tất cả Phase — file nào đã có, file nào thiếu.
     *
     * @return array Danh sách Phase với status (ready/missing) và metadata
     */
    public function checkAllPhaseStatus(): array
    {
        $statuses = [];

        foreach ($this->jsonFiles as $phaseKey => $filename) {
            $filePath = rtrim($this->reportsPath, '/') . '/' . $filename;
            $exists = file_exists($filePath);

            $status = [
                'phase'    => $phaseKey,
                'filename' => $filename,
                'status'   => $exists ? 'ready' : 'missing',
                'path'     => $filePath,
            ];

            if ($exists) {
                $rawContent = file_get_contents($filePath);
                $data = json_decode($rawContent, true);
                if (json_last_error() === JSON_ERROR_NONE && isset($data['metadata'])) {
                    $status['timestamp'] = $data['metadata']['timestamp'] ?? null;
                    $status['n_observations'] = $data['metadata']['n_observations']
                        ?? $data['metadata']['n_observations_raw']
                        ?? null;
                } else {
                    $status['status'] = 'error';
                    $status['error'] = 'JSON parse failed: ' . json_last_error_msg();
                }
            }

            $statuses[$phaseKey] = $status;
        }

        return $statuses;
    }

    /**
     * Lấy tổng quan hệ thống: model route, số quan sát, key findings.
     * Tổng hợp từ nhiều file JSON.
     *
     * @return array
     */
    public function getSummary(): array
    {
        $summary = [
            'model_route'     => null,
            'lag_order'       => null,
            'n_observations'  => null,
            'variables'       => config('dashboard.target_variables'),
            'granger_significant_count' => null,
            'granger_total_pairs'       => null,
            'null_finding_dr_self_pct'  => null,
            'phases_status'   => $this->checkAllPhaseStatus(),
        ];

        // Từ Phase 4: model route + diagnostics
        try {
            $phase4 = $this->loadPhaseData('phase4_forecast');
            $summary['model_route'] = $phase4['locked_parameters']['route'] ?? 'unknown';
            $summary['lag_order'] = $phase4['locked_parameters']['lag_order'] ?? null;
            $summary['n_observations'] = $phase4['model_diagnostics']['effective_observations'] ?? null;
            $summary['aic'] = $phase4['model_diagnostics']['aic'] ?? null;
            $summary['bic'] = $phase4['model_diagnostics']['bic'] ?? null;
        } catch (RuntimeException $e) {
            Log::warning("Summary: không thể đọc Phase 4 — {$e->getMessage()}");
        }

        // Từ Phase 2: Granger significant count
        try {
            $phase2 = $this->loadPhaseData('phase2_granger');
            $pairs = $phase2['pairwise_results'] ?? [];
            $sigCount = count(array_filter($pairs, fn($p) => $p['significant'] ?? false));
            $summary['granger_significant_count'] = $sigCount;
            $summary['granger_total_pairs'] = count($pairs);
        } catch (RuntimeException $e) {
            Log::warning("Summary: không thể đọc Phase 2 — {$e->getMessage()}");
        }

        // Từ Phase 5: FEVD Null Finding — tỷ lệ DelayRate tự giải thích
        try {
            $phase5 = $this->loadPhaseData('phase5_irf_fevd');
            $fevd = $phase5['fevd'] ?? [];
            // Tìm key DelayRate (hoặc tên biến tương đương)
            $drFevd = $fevd['DelayRate'] ?? null;
            if ($drFevd !== null) {
                $drSelf = $drFevd['DelayRate'] ?? [];
                if (!empty($drSelf)) {
                    // Giá trị cuối cùng (horizon dài nhất) = tỷ lệ tự giải thích
                    $summary['null_finding_dr_self_pct'] = round(end($drSelf) * 100, 1);
                }
            }
        } catch (RuntimeException $e) {
            Log::warning("Summary: không thể đọc Phase 5 — {$e->getMessage()}");
        }

        return $summary;
    }
}
