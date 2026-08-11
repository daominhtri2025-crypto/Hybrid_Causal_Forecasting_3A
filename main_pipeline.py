"""
main_pipeline.py — Orchestrator one-click cho toàn bộ pipeline Phương án 3-A.

Mục đích:
    Điều phối tuần tự 7 Phase (0 → 5) của pipeline phân tích nhân quả VECM,
    từ dữ liệu thô đến trực quan hóa IRF/FEVD, trong MỘT lần chạy duy nhất.

Cách dùng:
    # Chế độ 1: DEMO — Phase 0 tự sinh toàn bộ dữ liệu giả lập
    python main_pipeline.py

    # Chế độ 2: HYBRID — Delay thật từ Tầng 1 + OEE/Revenue giả lập
    python main_pipeline.py --delay-csv "data/raw/snapshot_.../cmt_delay_results.csv"

    # Chế độ 3: DỮ LIỆU THẬT — bỏ qua Phase 0, nạp thẳng dataset hoàn chỉnh
    python main_pipeline.py --data "path/to/real_data.xlsx"

    # Chỉ chạy đến Phase 3 (debug / kiểm tra trung gian)
    python main_pipeline.py --stop-after phase3

    # Tiếp tục từ Phase 3 (bỏ qua Phase 0-2 nếu output đã có)
    python main_pipeline.py --resume-from phase3

Input:
    --delay-csv  : (tùy chọn) Đường dẫn CSV chứa Sales Order thật từ Tầng 1.
                   Phase 0 dùng Delay thật + tạo OEE/Revenue giả lập có tương quan.
    --data       : (tùy chọn) Đường dẫn file CSV/Excel chứa dataset hoàn chỉnh.
                   Yêu cầu: cột Date, OEE_Score, DelayRate, Revenue, OrderVolume.
                   Bỏ qua Phase 0 hoàn toàn.
    --stop-after : (tùy chọn) Dừng pipeline sau Phase chỉ định.
    --resume-from: (tùy chọn) Tiếp tục từ Phase chỉ định, bỏ qua các Phase
                   trước nếu output đã tồn tại từ lần chạy trước.
    --seed       : (tùy chọn) Random seed cho Phase 0 (mặc định: 42).

    Lưu ý: --data và --delay-csv loại trừ nhau. Không truyền cả hai.

Output:
    data/processed/causal_weekly_dataset.csv   — Dataset tuần chuẩn hóa
    reports/phase1_stationarity.json           — Kết quả ADF + KPSS
    reports/phase2_granger_causality.json      — Nhân quả Granger
    reports/phase3_cointegration.json          — Johansen cointegration
    reports/phase3b_toda_yamamoto.json         — Cross-validation Toda-Yamamoto
    reports/tang4_vecm_results.json            — VECM estimation + forecasts
    reports/phase5_irf_fevd_results.json       — IRF + FEVD
    data/processed/figures/*.png               — Biểu đồ IRF, FEVD (DPI=300)
    docs/thesis_draft/chapter4_draft.md        — Bản thảo Chương 4 (nếu đã có)

Tuân thủ: CLAUDE.md mục 3 (Coding), mục 7 (Logging), mục 3.5 (Reproducibility).
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Đường dẫn gốc — dùng vị trí file main_pipeline.py làm neo
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent

# Thêm thư mục scripts/ vào sys.path để import được các module Phase
sys.path.insert(0, str(BASE_DIR / "scripts"))

from utils import get_logger  # noqa: E402 — phải sau sys.path

# ---------------------------------------------------------------------------
# Hằng số pipeline
# ---------------------------------------------------------------------------
REQUIRED_COLUMNS = ["Date", "OEE_Score", "DelayRate", "Revenue", "OrderVolume"]

OUTPUT_DIRS = [
    BASE_DIR / "data" / "processed",
    BASE_DIR / "data" / "processed" / "figures",
    BASE_DIR / "reports",
    BASE_DIR / "reports" / "logs",
    BASE_DIR / "reports" / "forecasts",
    BASE_DIR / "docs" / "thesis_draft",
]

# Thứ tự Phase — mỗi tuple: (tên hiển thị, tên module, hàm chạy)
PHASE_REGISTRY = [
    ("Phase 0", "Tạo dữ liệu giả lập (Synthetic Pipeline)"),
    ("Phase 1", "Kiểm định tính dừng (ADF + KPSS)"),
    ("Phase 2", "Kiểm định nhân quả Granger"),
    ("Phase 3", "Kiểm định đồng liên kết Johansen"),
    ("Phase 3b", "Kiểm tra chéo Toda-Yamamoto"),
    ("Phase 4", "Ước lượng VECM & Dự báo"),
    ("Phase 5", "Trực quan hóa IRF & FEVD"),
]

STOP_POINTS = {
    "phase0": 0, "phase1": 1, "phase2": 2,
    "phase3": 3, "phase3b": 4, "phase4": 5, "phase5": 6,
}


# ===================================================================
# PHẦN 1: TIỆN ÍCH HỖ TRỢ
# ===================================================================

def _ensure_output_dirs():
    """Tạo toàn bộ thư mục đầu ra nếu chưa tồn tại."""
    for d in OUTPUT_DIRS:
        d.mkdir(parents=True, exist_ok=True)


def _load_external_data(data_path: str, logger) -> str:
    """
    Nạp dữ liệu thật từ file CSV hoặc Excel, validate cột bắt buộc,
    rồi ghi ra vị trí chuẩn `data/processed/causal_weekly_dataset.csv`.

    Trả về: đường dẫn tới file CSV đã chuẩn hóa.

    Quy trình:
        1. Phát hiện định dạng qua phần mở rộng (.csv / .xlsx / .xls).
        2. Kiểm tra đủ 5 cột bắt buộc (Date, OEE_Score, ...).
        3. Parse cột Date thành datetime, sắp xếp theo thời gian.
        4. Ghi ra data/processed/causal_weekly_dataset.csv (UTF-8).
    """
    p = Path(data_path)
    if not p.exists():
        raise FileNotFoundError(f"Không tìm thấy file dữ liệu: {data_path}")

    ext = p.suffix.lower()
    logger.info(f"Đang nạp dữ liệu thật từ: {data_path} (định dạng: {ext})")

    if ext == ".csv":
        df = pd.read_csv(data_path, encoding="utf-8-sig")
    elif ext in (".xlsx", ".xls"):
        df = pd.read_excel(data_path)
    else:
        raise ValueError(
            f"Định dạng file không được hỗ trợ: '{ext}'. "
            f"Chỉ chấp nhận .csv, .xlsx, hoặc .xls."
        )

    # --- Validate cột bắt buộc ---
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"File thiếu {len(missing)} cột bắt buộc: {missing}. "
            f"Cần đủ: {REQUIRED_COLUMNS}"
        )

    # --- Chuẩn hóa Date và sắp xếp ---
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date").reset_index(drop=True)

    n_rows = len(df)
    date_min = df["Date"].min().strftime("%Y-%m-%d")
    date_max = df["Date"].max().strftime("%Y-%m-%d")
    logger.info(f"Dữ liệu thật: {n_rows} quan sát, từ {date_min} đến {date_max}")

    # Kiểm tra NaN trong các cột số
    numeric_cols = [c for c in REQUIRED_COLUMNS if c != "Date"]
    nan_counts = df[numeric_cols].isna().sum()
    total_nan = nan_counts.sum()
    if total_nan > 0:
        logger.warning(
            f"Phát hiện {total_nan} giá trị NaN trong cột số: "
            f"{nan_counts[nan_counts > 0].to_dict()}"
        )

    # --- Ghi ra vị trí chuẩn ---
    out_path = str(BASE_DIR / "data" / "processed" / "causal_weekly_dataset.csv")
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    logger.info(f"Đã ghi dữ liệu chuẩn hóa → {out_path}")

    return out_path


def _format_elapsed(seconds: float) -> str:
    """Định dạng thời gian chạy thân thiện: '2.3s' hoặc '1m 45s'."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    mins = int(seconds // 60)
    secs = seconds % 60
    return f"{mins}m {secs:.0f}s"


def _print_banner(logger):
    """In banner khởi động pipeline."""
    banner = (
        "\n"
        "╔══════════════════════════════════════════════════════════════╗\n"
        "║   PHƯƠNG ÁN 3-A — HYBRID CAUSAL FORECASTING PIPELINE      ║\n"
        "║   One-click Execution: Phase 0 → Phase 5                   ║\n"
        "╚══════════════════════════════════════════════════════════════╝"
    )
    logger.info(banner)


def _print_summary(results: dict, total_time: float, logger):
    """In bảng tổng kết cuối pipeline."""
    logger.info("")
    logger.info("=" * 62)
    logger.info("  TỔNG KẾT PIPELINE — PHƯƠNG ÁN 3-A")
    logger.info("=" * 62)

    for phase_id, info in results.items():
        status = info["status"]
        elapsed = info.get("elapsed", 0)
        if status == "success":
            icon = "OK"
        elif status in ("skipped", "skipped (resume)"):
            icon = "SKIP"
        else:
            icon = "FAIL"
        logger.info(f"  [{icon:>4}]  {phase_id:<10} — {info['label']:<45} ({_format_elapsed(elapsed)})")

    logger.info("-" * 62)
    logger.info(f"  Tổng thời gian: {_format_elapsed(total_time)}")
    logger.info("")

    # Liệt kê file output quan trọng
    output_files = {
        "Dataset tuần":          "data/processed/causal_weekly_dataset.csv",
        "Kiểm định tính dừng":   "reports/phase1_stationarity.json",
        "Nhân quả Granger":      "reports/phase2_granger_causality.json",
        "Đồng liên kết Johansen":"reports/phase3_cointegration.json",
        "Toda-Yamamoto":         "reports/phase3b_toda_yamamoto.json",
        "VECM Results":          "reports/tang4_vecm_results.json",
        "VECM Forecast":         "reports/forecasts/vecm_forecast.csv",
        "IRF & FEVD Results":    "reports/phase5_irf_fevd_results.json",
        "Biểu đồ IRF":          "data/processed/figures/irf_delayrate_response.png",
        "Biểu đồ FEVD":         "data/processed/figures/fevd_delayrate_decomposition.png",
        "Bản thảo Chương 4":     "docs/thesis_draft/chapter4_draft.md",
    }

    logger.info("  OUTPUT FILES:")
    for label, rel_path in output_files.items():
        full = BASE_DIR / rel_path
        exists = full.exists()
        mark = "  +  " if exists else "  -  "
        logger.info(f"{mark}{label:<25} → {rel_path}")

    logger.info("")
    logger.info(f"  Thư mục gốc: {BASE_DIR}")
    logger.info("=" * 62)


# Mapping Phase → file output kỳ vọng (dùng cho checkpoint/resume)
PHASE_OUTPUT_FILES = {
    "Phase 0":  "data/processed/causal_weekly_dataset.csv",
    "Phase 1":  "reports/phase1_stationarity.json",
    "Phase 2":  "reports/phase2_granger_causality.json",
    "Phase 3":  "reports/phase3_cointegration.json",
    "Phase 3b": "reports/phase3b_toda_yamamoto.json",
    "Phase 4":  "reports/tang4_vecm_results.json",
    "Phase 5":  "reports/phase5_irf_fevd_results.json",
}


def _can_skip_phase(phase_id: str, logger) -> bool:
    """
    Kiểm tra Phase có thể bỏ qua (đã chạy thành công trước đó) dựa trên
    sự tồn tại và tính hợp lệ của file output kỳ vọng.

    Dùng cho --resume-from: các Phase trước điểm resume được bỏ qua nếu
    output đã tồn tại, tránh chạy lại toàn bộ pipeline khi chỉ cần debug
    Phase 3 trở đi.
    """
    output_rel = PHASE_OUTPUT_FILES.get(phase_id)
    if not output_rel:
        return False

    output_path = BASE_DIR / output_rel
    if not output_path.exists():
        logger.warning(
            f"  ⚠ {phase_id}: output kỳ vọng '{output_rel}' không tồn tại "
            f"— KHÔNG thể bỏ qua, phải chạy lại."
        )
        return False

    # Kiểm tra file không rỗng
    if output_path.stat().st_size == 0:
        logger.warning(
            f"  ⚠ {phase_id}: output '{output_rel}' tồn tại nhưng rỗng "
            f"— KHÔNG thể bỏ qua."
        )
        return False

    logger.info(
        f"  ⏭ {phase_id}: bỏ qua — output '{output_rel}' đã tồn tại "
        f"từ lần chạy trước."
    )
    return True


def log_phase_transition(phase_from: str, phase_to: str, status: str,
                         elapsed: float, logger, extra: dict = None):
    """
    Ghi log chuyển tiếp giữa các Phase theo định dạng JSON có cấu trúc.

    Mỗi lần Phase hoàn tất (thành công hoặc thất bại), hàm này ghi 1 dòng
    JSON vào file reports/logs/phase_transitions.jsonl — giúp giám sát và
    phân tích pipeline execution history một cách có hệ thống.
    """
    transition_dir = BASE_DIR / "reports" / "logs"
    transition_dir.mkdir(parents=True, exist_ok=True)
    transition_path = transition_dir / "phase_transitions.jsonl"

    record = {
        "timestamp": datetime.now().isoformat(),
        "from": phase_from,
        "to": phase_to,
        "status": status,
        "elapsed_seconds": round(elapsed, 2),
    }
    if extra:
        record["extra"] = extra

    with open(transition_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    logger.debug(
        f"Phase transition: {phase_from} → {phase_to} [{status}] "
        f"({_format_elapsed(elapsed)})"
    )


# ===================================================================
# PHẦN 2: ĐIỀU PHỐI TỪNG PHASE
# ===================================================================

def _run_phase0(data_path: str, delay_csv: str, seed: int, logger) -> str:
    """
    Phase 0: Tạo dữ liệu — 3 chế độ tuỳ tham số đầu vào.

    Chế độ 1 (DEMO):   Không có --data, không có --delay-csv
        → Phase 0 sinh toàn bộ 4 biến giả lập.
    Chế độ 2 (HYBRID): Có --delay-csv
        → Phase 0 dùng Delay thật + tạo OEE/Revenue giả lập có tương quan.
    Chế độ 3 (THẬT):   Có --data
        → Bỏ qua Phase 0, nạp thẳng dataset hoàn chỉnh.

    Trả về: đường dẫn tới causal_weekly_dataset.csv.
    """
    if data_path:
        logger.info("[PHASE 0] Chế độ DỮ LIỆU THẬT — bỏ qua synthetic pipeline")
        csv_path = _load_external_data(data_path, logger)
        return csv_path

    from phase0_synthetic_pipeline import run_phase0_synthetic

    if delay_csv:
        logger.info(f"[PHASE 0] Chế độ HYBRID — Delay thật từ: {delay_csv}")
        csv_path = run_phase0_synthetic(delay_csv=delay_csv, seed=seed)
    else:
        logger.info("[PHASE 0] Chế độ DEMO — kích hoạt full synthetic pipeline")
        csv_path = run_phase0_synthetic(seed=seed)

    return csv_path


def _run_phase1(csv_path: str, logger) -> str:
    """Phase 1: Kiểm định tính dừng ADF + KPSS cho mỗi biến."""
    from phase1_stationarity import run_phase1
    json_path = run_phase1(input_path=csv_path)
    return json_path


def _run_phase2(csv_path: str, logger) -> str:
    """Phase 2: Kiểm định nhân quả Granger (trên chuỗi đã sai phân)."""
    from phase2_granger_causality import run_phase2
    json_path = run_phase2(input_path=csv_path)
    return json_path


def _run_phase3(csv_path: str, logger) -> str:
    """Phase 3: Kiểm định đồng liên kết Johansen (Trace + Max-Eigenvalue)."""
    from phase3_cointegration import run_phase3
    json_path = run_phase3(input_path=csv_path)
    return json_path


def _run_phase3b(csv_path: str, logger) -> str:
    """Phase 3b: Kiểm tra chéo Toda-Yamamoto (trên levels, không sai phân)."""
    from phase3b_toda_yamamoto import run_phase3b
    json_path = run_phase3b(input_path=csv_path)
    return json_path


def _run_phase4(csv_path: str, logger) -> dict:
    """Phase 4: Ước lượng VECM, trích xuất phương trình, dự báo 12 tuần."""
    from tang4_vecm_forecasting import run_tang4
    result = run_tang4(input_csv=csv_path)
    return result


def _run_phase5(csv_path: str, logger) -> dict:
    """Phase 5: Trực quan hóa IRF (Cholesky) và FEVD (stacked area)."""
    from phase5_visualization import run_phase5
    result = run_phase5(input_csv=csv_path)
    return result


# ===================================================================
# PHẦN 3: HÀM CHÍNH — ORCHESTRATOR
# ===================================================================

def run_pipeline(
    data_path: str = None,
    delay_csv: str = None,
    seed: int = 42,
    stop_after: str = None,
    resume_from: str = None,
):
    """
    Hàm chính điều phối toàn bộ pipeline từ Phase 0 đến Phase 5.

    Luồng thực thi:
        Phase 0  →  tạo/nạp dữ liệu (3 chế độ: demo / hybrid / thật)
        Phase 1  →  kiểm định tính dừng
        Phase 2  →  nhân quả Granger
        Phase 3  →  đồng liên kết Johansen
        Phase 3b →  cross-validation Toda-Yamamoto
        Phase 4  →  ước lượng VECM + dự báo
        Phase 5  →  trực quan hóa IRF & FEVD

    Mỗi Phase chạy trong khối try/except riêng. Nếu bất kỳ Phase nào
    thất bại, pipeline dừng an toàn và in nguyên nhân chi tiết.

    Tham số:
        data_path:   đường dẫn dataset hoàn chỉnh (.csv/.xlsx). Bỏ qua Phase 0.
        delay_csv:   đường dẫn CSV Sales Order thật → Phase 0 hybrid mode.
        seed:        random seed cho Phase 0 (mặc định: 42).
        stop_after:  dừng sau Phase chỉ định ('phase0'..'phase5'). None = chạy hết.
        resume_from: tiếp tục từ Phase chỉ định, bỏ qua các Phase trước nếu
                     output đã tồn tại. Hữu ích khi debug Phase cuối mà không
                     cần chạy lại toàn bộ pipeline.
    """
    logger = get_logger("pipeline")
    pipeline_start = time.time()

    _print_banner(logger)
    _ensure_output_dirs()

    # Xác định điểm dừng và điểm tiếp tục
    max_phase_idx = STOP_POINTS.get(stop_after, len(PHASE_REGISTRY) - 1) if stop_after else len(PHASE_REGISTRY) - 1
    resume_idx = STOP_POINTS.get(resume_from, 0) if resume_from else 0

    if data_path:
        mode = "DỮ LIỆU THẬT (bỏ qua Phase 0)"
    elif delay_csv:
        mode = "HYBRID (Delay thật + OEE/Revenue giả lập)"
    else:
        mode = "DEMO (Full Synthetic)"
    logger.info(f"  Chế độ chạy : {mode}")
    logger.info(f"  Random seed : {seed}")
    if stop_after:
        logger.info(f"  Dừng sau    : {stop_after}")
    if resume_from:
        logger.info(f"  Tiếp tục từ : {resume_from}")
    logger.info(f"  Thời điểm   : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("")

    # Biến trạng thái pipeline — truyền giữa các Phase
    csv_path = None
    results = {}

    # ---------------------------------------------------------------
    # PHASE 0: Tạo / Nạp dữ liệu
    # ---------------------------------------------------------------
    phase_id = "Phase 0"
    phase_label = PHASE_REGISTRY[0][1]
    if max_phase_idx >= 0:
        # --resume-from: bỏ qua Phase 0 nếu resume_idx > 0 và output đã có
        if resume_idx > 0 and _can_skip_phase(phase_id, logger):
            csv_path = str(BASE_DIR / PHASE_OUTPUT_FILES[phase_id])
            results[phase_id] = {"status": "skipped (resume)", "label": phase_label, "elapsed": 0}
        else:
            logger.info(f"{'─' * 62}")
            logger.info(f"  ▶ {phase_id}: {phase_label}")
            logger.info(f"{'─' * 62}")
            t0 = time.time()
            try:
                csv_path = _run_phase0(data_path, delay_csv, seed, logger)
                elapsed = time.time() - t0
                results[phase_id] = {"status": "success", "label": phase_label, "elapsed": elapsed}
                log_phase_transition("start", phase_id, "success", elapsed, logger)
                logger.info(f"  ✓ {phase_id} hoàn tất ({_format_elapsed(elapsed)})")
            except Exception:
                elapsed = time.time() - t0
                results[phase_id] = {"status": "failed", "label": phase_label, "elapsed": elapsed}
                log_phase_transition("start", phase_id, "failed", elapsed, logger)
                logger.exception(f"  ✗ {phase_id} THẤT BẠI — pipeline dừng lại")
                _print_summary(results, time.time() - pipeline_start, logger)
                return False
    else:
        results[phase_id] = {"status": "skipped", "label": phase_label, "elapsed": 0}

    if max_phase_idx == 0:
        _print_summary(results, time.time() - pipeline_start, logger)
        return True

    # ---------------------------------------------------------------
    # PHASE 1–5: Các Phase phân tích
    # Danh sách (index, tên, label, hàm chạy, cần csv_path không)
    # ---------------------------------------------------------------
    analysis_phases = [
        (1, "Phase 1",  PHASE_REGISTRY[1][1], _run_phase1),
        (2, "Phase 2",  PHASE_REGISTRY[2][1], _run_phase2),
        (3, "Phase 3",  PHASE_REGISTRY[3][1], _run_phase3),
        (4, "Phase 3b", PHASE_REGISTRY[4][1], _run_phase3b),
        (5, "Phase 4",  PHASE_REGISTRY[5][1], _run_phase4),
        (6, "Phase 5",  PHASE_REGISTRY[6][1], _run_phase5),
    ]

    prev_phase = "Phase 0"
    for idx, phase_id, phase_label, phase_func in analysis_phases:
        if idx > max_phase_idx:
            results[phase_id] = {"status": "skipped", "label": phase_label, "elapsed": 0}
            continue

        # --resume-from: bỏ qua Phase trước điểm resume nếu output đã có
        if idx < resume_idx and _can_skip_phase(phase_id, logger):
            results[phase_id] = {"status": "skipped (resume)", "label": phase_label, "elapsed": 0}
            prev_phase = phase_id
            continue

        logger.info("")
        logger.info(f"{'─' * 62}")
        logger.info(f"  ▶ {phase_id}: {phase_label}")
        logger.info(f"{'─' * 62}")

        t0 = time.time()
        try:
            phase_func(csv_path, logger)
            elapsed = time.time() - t0
            results[phase_id] = {"status": "success", "label": phase_label, "elapsed": elapsed}
            log_phase_transition(prev_phase, phase_id, "success", elapsed, logger)
            logger.info(f"  ✓ {phase_id} hoàn tất ({_format_elapsed(elapsed)})")
        except Exception:
            elapsed = time.time() - t0
            results[phase_id] = {"status": "failed", "label": phase_label, "elapsed": elapsed}
            log_phase_transition(prev_phase, phase_id, "failed", elapsed, logger)
            logger.exception(f"  ✗ {phase_id} THẤT BẠI — pipeline dừng lại")
            _print_summary(results, time.time() - pipeline_start, logger)
            return False

        prev_phase = phase_id

    # ---------------------------------------------------------------
    # TỔNG KẾT
    # ---------------------------------------------------------------
    total_time = time.time() - pipeline_start
    _print_summary(results, total_time, logger)
    logger.info("  Pipeline Phương án 3-A hoàn tất thành công.")
    logger.info("")
    return True


# ===================================================================
# PHẦN 4: CLI ENTRY POINT
# ===================================================================

def _build_parser() -> argparse.ArgumentParser:
    """Xây dựng CLI parser với các tùy chọn rõ ràng."""
    parser = argparse.ArgumentParser(
        prog="main_pipeline.py",
        description=(
            "Phương án 3-A: Hybrid Causal Forecasting Pipeline\n"
            "Điều phối tuần tự Phase 0 → Phase 5 trong một lần chạy."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ví dụ:\n"
            "  python main_pipeline.py                                              # Demo (full synthetic)\n"
            "  python main_pipeline.py --delay-csv data/raw/snapshot_.../cmt_delay_results.csv  # Hybrid\n"
            "  python main_pipeline.py --data real_data.xlsx                        # Dữ liệu thật hoàn chỉnh\n"
            "  python main_pipeline.py --stop-after phase3                         # Chỉ chạy đến Phase 3\n"
            "  python main_pipeline.py --resume-from phase3                        # Tiếp tục từ Phase 3\n"
            "  python main_pipeline.py --resume-from phase4 --stop-after phase4    # Chỉ chạy Phase 4\n"
        ),
    )

    parser.add_argument(
        "--delay-csv",
        type=str,
        default=None,
        metavar="PATH",
        help=(
            "Chế độ HYBRID: Đường dẫn CSV Sales Order thật từ Tầng 1 "
            "(cmt_delay_results.csv). Phase 0 dùng Delay thật + tạo "
            "OEE/Revenue giả lập có tương quan. Loại trừ với --data."
        ),
    )

    parser.add_argument(
        "--data",
        type=str,
        default=None,
        metavar="PATH",
        help=(
            "Chế độ DỮ LIỆU THẬT: Đường dẫn file CSV/Excel chứa dataset "
            "hoàn chỉnh (cần cột Date, OEE_Score, DelayRate, Revenue, "
            "OrderVolume). Bỏ qua Phase 0. Loại trừ với --delay-csv."
        ),
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed cho Phase 0 synthetic (mặc định: 42).",
    )

    parser.add_argument(
        "--stop-after",
        type=str,
        default=None,
        choices=list(STOP_POINTS.keys()),
        metavar="PHASE",
        help=(
            "Dừng pipeline sau Phase chỉ định. "
            "Lựa chọn: phase0, phase1, phase2, phase3, phase3b, phase4, phase5."
        ),
    )

    parser.add_argument(
        "--resume-from",
        type=str,
        default=None,
        choices=list(STOP_POINTS.keys()),
        metavar="PHASE",
        help=(
            "Tiếp tục pipeline từ Phase chỉ định, bỏ qua các Phase trước "
            "nếu output đã tồn tại. Hữu ích khi debug Phase 3+ mà không "
            "cần chạy lại Phase 0-2. "
            "Lựa chọn: phase0, phase1, phase2, phase3, phase3b, phase4, phase5."
        ),
    )

    return parser


if __name__ == "__main__":
    parser = _build_parser()
    args = parser.parse_args()

    # Validate: --data và --delay-csv loại trừ nhau
    if args.data and args.delay_csv:
        parser.error("--data và --delay-csv loại trừ nhau. Chỉ truyền một trong hai.")

    success = run_pipeline(
        data_path=args.data,
        delay_csv=args.delay_csv,
        seed=args.seed,
        stop_after=args.stop_after,
        resume_from=args.resume_from,
    )

    sys.exit(0 if success else 1)
