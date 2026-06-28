import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler


def setup_logger(
    name: str = "pipeline",
    log_file: str = "logs/pipeline.log",
    level: str = "INFO",
    max_bytes: int = 5_000_000,
    backup_count: int = 5
) -> logging.Logger:
    """
    Cấu hình logger dùng chung cho toàn bộ pipeline.

    - Ghi log ra console
    - Ghi log ra file
    - Tự tạo thư mục logs nếu chưa có
    - Tránh bị duplicate log handler khi import nhiều lần
    """

    logger = logging.getLogger(name)

    # Nếu logger đã có handler thì không add lại nữa
    if logger.handlers:
        return logger

    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(log_level)
    logger.propagate = False

    # Tạo thư mục logs nếu chưa tồn tại
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Log ra console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    # Log ra file, tự xoay file nếu quá lớn
    file_handler = RotatingFileHandler(
        filename=log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8"
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "pipeline") -> logging.Logger:
    """
    Lấy logger đã cấu hình.
    Nếu chưa cấu hình thì tự setup mặc định.
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        return setup_logger(name=name)

    return logger