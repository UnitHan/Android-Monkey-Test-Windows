#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
실행 시간 측정 및 포맷팅 유틸리티
"""
import time
import logging
from typing import Union

logger = logging.getLogger(__name__)

def format_duration(seconds: Union[int, float]) -> str:
    """
    초 단위 시간을 사용자 친화적 형식으로 포맷팅
    
    Args:
        seconds: 초 단위 시간
        
    Returns:
        포맷팅된 시간 문자열
        
    예시:
        - 30 -> "30초"
        - 90 -> "1분 30초"
        - 3661 -> "1시간 01분"
    """
    try:
        total_seconds = int(round(seconds))
        
        if total_seconds < 60:
            # 60초 미만: "00초"
            return f"{total_seconds:02d}초"
        elif total_seconds < 3600:
            # 60분 미만: "00분 00초"
            minutes = total_seconds // 60
            remaining_seconds = total_seconds % 60
            return f"{minutes:02d}분 {remaining_seconds:02d}초"
        else:
            # 60분 이상: "0시간 00분"
            hours = total_seconds // 3600
            remaining_minutes = (total_seconds % 3600) // 60
            return f"{hours}시간 {remaining_minutes:02d}분"
            
    except (ValueError, TypeError) as e:
        logger.error(f"시간 포맷팅 오류: {e}")
        return "00초"

class ExecutionTimer:
    """실행 시간 측정 클래스"""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.elapsed_seconds = 0
        
    def start(self):
        """시간 측정 시작"""
        self.start_time = time.time()
        self.end_time = None
        self.elapsed_seconds = 0
        logger.debug("실행 시간 측정 시작")
        
    def stop(self):
        """시간 측정 종료"""
        if self.start_time is None:
            logger.warning("타이머가 시작되지 않았습니다")
            return 0
            
        self.end_time = time.time()
        self.elapsed_seconds = self.end_time - self.start_time
        logger.debug(f"실행 시간 측정 완료: {self.elapsed_seconds:.2f}초")
        return self.elapsed_seconds
        
    def get_elapsed_seconds(self) -> float:
        """경과 시간 반환 (초)"""
        if self.start_time is None:
            return 0
            
        if self.end_time is None:
            # 아직 종료되지 않은 경우 현재까지의 경과 시간
            return time.time() - self.start_time
        else:
            return self.elapsed_seconds
            
    def get_formatted_duration(self) -> str:
        """포맷팅된 실행 시간 반환"""
        return format_duration(self.get_elapsed_seconds())
        
    def reset(self):
        """타이머 리셋"""
        self.start_time = None
        self.end_time = None
        self.elapsed_seconds = 0
        logger.debug("실행 시간 측정 리셋")

class RepeatExecutionTimer:
    """반복 실행을 위한 타이머 클래스"""
    
    def __init__(self):
        self.total_timer = ExecutionTimer()
        self.repeat_timer = ExecutionTimer()
        self.repeat_durations = []
        
    def start_total(self):
        """전체 실행 시간 측정 시작"""
        self.total_timer.start()
        self.repeat_durations = []
        
    def start_repeat(self):
        """개별 반복 시간 측정 시작"""
        self.repeat_timer.start()
        
    def stop_repeat(self):
        """개별 반복 시간 측정 종료"""
        duration = self.repeat_timer.stop()
        self.repeat_durations.append(duration)
        return duration
        
    def stop_total(self):
        """전체 실행 시간 측정 종료"""
        return self.total_timer.stop()
        
    def get_repeat_duration(self, repeat_index: int) -> float:
        """특정 반복의 실행 시간 반환"""
        if 0 <= repeat_index < len(self.repeat_durations):
            return self.repeat_durations[repeat_index]
        return 0
        
    def get_formatted_repeat_duration(self, repeat_index: int) -> str:
        """특정 반복의 포맷팅된 실행 시간 반환"""
        duration = self.get_repeat_duration(repeat_index)
        return format_duration(duration)
        
    def get_total_formatted_duration(self) -> str:
        """전체 포맷팅된 실행 시간 반환"""
        return self.total_timer.get_formatted_duration()
        
    def get_average_repeat_duration(self) -> float:
        """평균 반복 실행 시간 반환"""
        if not self.repeat_durations:
            return 0
        return sum(self.repeat_durations) / len(self.repeat_durations)
        
    def get_formatted_average_duration(self) -> str:
        """평균 반복 실행 시간 포맷팅"""
        return format_duration(self.get_average_repeat_duration())