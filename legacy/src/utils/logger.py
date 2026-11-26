#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
로깅 유틸리티
"""
import logging
import sys
from pathlib import Path
from datetime import datetime
from src.config import LOGS_DIR, LOG_FORMAT, LOG_LEVEL

def setup_logger(name: str = __name__, package_name: str = None) -> logging.Logger:
    """로거 설정 및 반환 - 테스트 실행 단위로 로그 파일 분리"""
    logger = logging.getLogger(name)
    
    # 기존 핸들러 제거 (새로운 테스트 시작 시)
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    logger.setLevel(getattr(logging, LOG_LEVEL))
    
    # 포맷터 설정
    formatter = logging.Formatter(LOG_FORMAT)
    
    # 파일 핸들러 - 테스트 실행 단위로 파일명 생성
    if package_name:
        timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M")
        log_filename = f"{package_name}_{timestamp}.log"
    else:
        log_filename = 'monkey_test_general.log'
    
    log_file = LOGS_DIR / log_filename
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    
    # 콘솔 핸들러 (EXE 모드에서는 숨김)
    if not getattr(sys, 'frozen', False):  # 개발 모드에서만 콘솔 출력
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)
        logger.addHandler(console_handler)
    
    # 핸들러 추가
    logger.addHandler(file_handler)
    
    # 상위 로거로 전파 방지
    logger.propagate = False
    
    return logger

def get_current_log_file() -> Path:
    """현재 로그 파일 경로 반환"""
    # 현재 활성화된 로거에서 파일 핸들러 찾기
    logger = logging.getLogger("monkey_test")
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler):
            return Path(handler.baseFilename)
    
    # 기본 로그 파일 반환
    return LOGS_DIR / 'monkey_test_general.log'

# 기본 로거
logger = setup_logger("monkey_test")
