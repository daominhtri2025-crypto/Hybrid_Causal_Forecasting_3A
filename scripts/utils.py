"""
Tiện ích dùng chung cho toàn bộ pipeline Phương án 3-A.

Mục đích chính:
  - Cung cấp hàm `get_logger()` tạo logger chuẩn cho mọi script trong `scripts/`.
  - Đảm bảo log ghi đồng thời ra console (để theo dõi trực tiếp) và file tập trung
    trong `reports/logs/` (để tra cứu lại sau).
  - Mỗi lần chạy pipeline tạo đúng 1 file log duy nhất, định danh bằng timestamp
    lúc bắt đầu chạy — không ghi đè log lần chạy trước (audit trail).

Input:  Không có (module tiện ích, được import bởi các script khác).
Output: Không trực tiếp — cấu hình logger ghi ra `reports/logs/pipeline_YYYYMMDD_HHMM.log`.

Tuân thủ: CLAUDE.md mục 7 (Logging), mục 3.1 (Comment tiếng Việt).
"""

import logging
import os
from datetime import datetime


# -------------------------------------------------------------------
# Timestamp khởi tạo module — chốt MỘT LẦN khi `utils.py` được import
# lần đầu tiên trong tiến trình Python. Tất cả các Phase gọi
# `get_logger()` trong cùng một lần chạy pipeline sẽ dùng chung
# timestamp này, nên mọi dòng log nằm trong cùng 1 file duy nhất.
# -------------------------------------------------------------------
_RUN_TIMESTAMP: str = datetime.now().strftime("%Y%m%d_%H%M")

# Đường dẫn gốc dự án — tính từ vị trí file utils.py (scripts/)
# lùi lên 1 cấp để ra thư mục gốc Phuong_An_3/
_BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Thư mục lưu log tập trung
_LOG_DIR: str = os.path.join(_BASE_DIR, "reports", "logs")


def get_logger(phase_name: str) -> logging.Logger:
    """
    Tạo logger dùng chung cho toàn pipeline.

    Tham số:
        phase_name: tên Phase/Tầng gọi hàm này (vd: "tang1", "phase0", "phase3b").
                    Dùng làm nhãn logger, giúp phân biệt log của từng Phase khi
                    đọc chung 1 file log.

    Trả về:
        logging.Logger đã cấu hình sẵn 2 handler:
          - ConsoleHandler: hiển thị trên terminal khi chạy tay.
          - FileHandler: ghi vào `reports/logs/pipeline_YYYYMMDD_HHMM.log`.

    Quy ước phân cấp log (xem CLAUDE.md mục 7.3):
        INFO     — bắt đầu/kết thúc Phase, số dòng input/output, thời gian xử lý.
        WARNING  — bất thường dữ liệu chưa crash (NaN, trùng lặp, bản ghi cận
                   nửa đêm) — BẮT BUỘC ghi rõ số lượng dòng bị ảnh hưởng.
        ERROR    — Phase dừng, bắt buộc kèm traceback (dùng logger.exception()).
        CRITICAL — lỗi hạ tầng nghiêm trọng (mất kết nối SQL sau retry, v.v.).
    """
    os.makedirs(_LOG_DIR, exist_ok=True)

    log_path = os.path.join(_LOG_DIR, f"pipeline_{_RUN_TIMESTAMP}.log")

    logger = logging.getLogger(phase_name)
    logger.setLevel(logging.DEBUG)

    # Tránh thêm handler trùng nếu `get_logger()` được gọi nhiều lần
    # cho cùng một phase_name trong cùng tiến trình (vd: khi test lặp lại).
    if not logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s"
        )

        # Handler 1: ghi ra file tập trung — mã hóa UTF-8 vì message log
        # viết bằng tiếng Việt (CLAUDE.md mục 7.3)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)

        # Handler 2: hiển thị trên console để Anh Béo theo dõi trực tiếp
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger


def get_base_dir() -> str:
    """Trả về đường dẫn tuyệt đối thư mục gốc dự án (Phuong_An_3/)."""
    return _BASE_DIR
