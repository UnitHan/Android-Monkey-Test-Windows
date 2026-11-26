#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
성능 데이터 처리 모듈
테스트 완료 후 수집된 성능 데이터를 가공하여 차트 생성 및 분석을 수행
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import statistics

logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    """성능 메트릭 데이터 클래스"""
    timestamp: str
    run_number: int
    memory_mb: float
    cpu_percent: float
    
    def __post_init__(self):
        """데이터 타입 검증 및 변환"""
        self.memory_mb = float(self.memory_mb) if self.memory_mb is not None else 0.0
        self.cpu_percent = float(self.cpu_percent) if self.cpu_percent is not None else 0.0
        self.run_number = int(self.run_number) if self.run_number is not None else 0

@dataclass
class RunSummary:
    """회차별 요약 데이터"""
    run_number: int
    execution_time: float
    event_count: int
    crash_count: int = 0
    anr_count: int = 0
    timeout_count: int = 0
    memory_peak: float = 0.0
    cpu_peak: float = 0.0
    memory_avg: float = 0.0
    cpu_avg: float = 0.0
    memory_min: float = 0.0
    cpu_min: float = 0.0

class PerformanceProcessor:
    """성능 데이터 처리 및 분석 클래스"""
    
    def __init__(self):
        self.raw_performance_data: List[Dict[str, Any]] = []
        self.processed_metrics: List[PerformanceMetrics] = []
        self.run_summaries: List[RunSummary] = []
        
    def load_performance_data(self, performance_data: List[Dict[str, Any]]) -> bool:
        """성능 데이터 로드"""
        try:
            if not performance_data:
                logger.warning("성능 데이터가 비어있습니다.")
                return False
            
            self.raw_performance_data = performance_data
            logger.info(f"성능 데이터 로드 완료: {len(performance_data)}개 데이터포인트")
            
            # 샘플 데이터 로깅
            if len(performance_data) > 0:
                sample = performance_data[0]
                logger.info(f"샘플 데이터: {sample}")
            
            return True
            
        except Exception as e:
            logger.error(f"성능 데이터 로드 실패: {e}")
            return False
    
    def process_metrics(self) -> bool:
        """원시 데이터를 구조화된 메트릭으로 변환"""
        try:
            self.processed_metrics = []
            
            for data in self.raw_performance_data:
                try:
                    metric = PerformanceMetrics(
                        timestamp=data.get('timestamp', ''),
                        run_number=data.get('run', 0),
                        memory_mb=data.get('memory_mb', data.get('mem_mb', 0.0)),
                        cpu_percent=data.get('cpu_percent', 0.0)
                    )
                    self.processed_metrics.append(metric)
                    
                except Exception as e:
                    logger.warning(f"메트릭 변환 실패 (항목 스킵): {data} - {e}")
                    continue
            
            logger.info(f"메트릭 처리 완료: {len(self.processed_metrics)}개 처리됨")
            return len(self.processed_metrics) > 0
            
        except Exception as e:
            logger.error(f"메트릭 처리 실패: {e}")
            return False
    
    def calculate_run_summaries(self, test_results: Optional[List[Dict[str, Any]]] = None) -> bool:
        """회차별 요약 데이터 계산"""
        try:
            self.run_summaries = []
            
            # 회차별로 그룹화
            runs_data = {}
            for metric in self.processed_metrics:
                run_num = metric.run_number
                if run_num not in runs_data:
                    runs_data[run_num] = []
                runs_data[run_num].append(metric)
            
            logger.info(f"회차별 데이터 그룹화: {list(runs_data.keys())}")
            
            # 각 회차별 요약 계산
            for run_num, metrics in runs_data.items():
                if not metrics:
                    continue
                
                try:
                    memory_values = [m.memory_mb for m in metrics if m.memory_mb > 0]
                    cpu_values = [m.cpu_percent for m in metrics if m.cpu_percent > 0]
                    
                    # 테스트 결과에서 추가 정보 가져오기
                    execution_time = 0.0
                    event_count = 0
                    crash_count = 0
                    anr_count = 0
                    timeout_count = 0
                    
                    if test_results:
                        for result in test_results:
                            if result.get('repeat') == run_num:
                                execution_time = self._safe_float(result.get('time', 0.0))
                                event_count = self._safe_int(result.get('events', 0))
                                crash_count = self._safe_int(result.get('crash', 0))
                                anr_count = self._safe_int(result.get('anr', 0))
                                timeout_count = self._safe_int(result.get('timeout', 0))
                                break
                    
                    summary = RunSummary(
                        run_number=run_num,
                        execution_time=execution_time,
                        event_count=event_count,
                        crash_count=crash_count,
                        anr_count=anr_count,
                        timeout_count=timeout_count,
                        memory_peak=max(memory_values) if memory_values else 0.0,
                        cpu_peak=max(cpu_values) if cpu_values else 0.0,
                        memory_avg=statistics.mean(memory_values) if memory_values else 0.0,
                        cpu_avg=statistics.mean(cpu_values) if cpu_values else 0.0,
                        memory_min=min(memory_values) if memory_values else 0.0,
                        cpu_min=min(cpu_values) if cpu_values else 0.0
                    )
                    
                    self.run_summaries.append(summary)
                    
                except Exception as e:
                    logger.warning(f"회차 {run_num} 요약 계산 실패: {e}")
                    continue
            
            # 회차 순서로 정렬
            self.run_summaries.sort(key=lambda x: x.run_number)
            
            logger.info(f"회차별 요약 계산 완료: {len(self.run_summaries)}회차")
            for summary in self.run_summaries:
                logger.info(f"회차 {summary.run_number}: 메모리 피크={summary.memory_peak:.1f}MB, "
                          f"CPU 피크={summary.cpu_peak:.1f}%, 실행시간={summary.execution_time:.1f}초")
            
            return len(self.run_summaries) > 0
            
        except Exception as e:
            logger.error(f"회차별 요약 계산 실패: {e}")
            return False
    
    def _safe_float(self, value, default=0.0) -> float:
        """안전한 float 변환"""
        try:
            if isinstance(value, str):
                # "11.7초" -> 11.7, "696MB" -> 696.0
                import re
                match = re.search(r'(\d+(?:\.\d+)?)', value)
                if match:
                    return float(match.group(1))
            return float(value) if value is not None else default
        except (ValueError, TypeError):
            return default
    
    def _safe_int(self, value, default=0) -> int:
        """안전한 int 변환"""
        try:
            if isinstance(value, str):
                import re
                match = re.search(r'(\d+)', value)
                if match:
                    return int(match.group(1))
            return int(value) if value is not None else default
        except (ValueError, TypeError):
            return default
    
    def generate_chart_data(self) -> Dict[str, Any]:
        """차트 생성을 위한 데이터 구조 생성"""
        try:
            if not self.run_summaries:
                logger.warning("회차별 요약 데이터가 없습니다.")
                return {}
            
            # TestResultData 형식으로 변환 (chart_generator.py 호환)
            from src.utils.chart_generator import TestResultData
            test_results = []
            
            for summary in self.run_summaries:
                test_result = TestResultData(
                    repeat_number=summary.run_number,
                    execution_time=summary.execution_time,
                    event_count=summary.event_count,
                    crash_count=summary.crash_count,
                    anr_count=summary.anr_count,
                    timeout_count=summary.timeout_count,
                    memory_peak=summary.memory_peak,
                    cpu_peak=summary.cpu_peak,
                    timestamp=None
                )
                test_results.append(test_result)
            
            logger.info(f"차트 데이터 생성 완료: {len(test_results)}개 테스트 결과")
            
            return {
                'test_results': test_results,
                'raw_metrics': self.processed_metrics,
                'run_summaries': self.run_summaries
            }
            
        except Exception as e:
            logger.error(f"차트 데이터 생성 실패: {e}")
            return {}
    
    def get_overall_statistics(self) -> Dict[str, Any]:
        """전체 통계 정보 계산"""
        try:
            if not self.run_summaries:
                return {}
            
            memory_peaks = [s.memory_peak for s in self.run_summaries if s.memory_peak > 0]
            cpu_peaks = [s.cpu_peak for s in self.run_summaries if s.cpu_peak > 0]
            execution_times = [s.execution_time for s in self.run_summaries if s.execution_time > 0]
            
            total_crashes = sum(s.crash_count for s in self.run_summaries)
            total_anrs = sum(s.anr_count for s in self.run_summaries)
            total_timeouts = sum(s.timeout_count for s in self.run_summaries)
            total_events = sum(s.event_count for s in self.run_summaries)
            
            stats = {
                'total_runs': len(self.run_summaries),
                'total_events': total_events,
                'total_crashes': total_crashes,
                'total_anrs': total_anrs,
                'total_timeouts': total_timeouts,
                'total_errors': total_crashes + total_anrs + total_timeouts,
                'memory_stats': {
                    'max': max(memory_peaks) if memory_peaks else 0.0,
                    'min': min(memory_peaks) if memory_peaks else 0.0,
                    'avg': statistics.mean(memory_peaks) if memory_peaks else 0.0
                },
                'cpu_stats': {
                    'max': max(cpu_peaks) if cpu_peaks else 0.0,
                    'min': min(cpu_peaks) if cpu_peaks else 0.0,
                    'avg': statistics.mean(cpu_peaks) if cpu_peaks else 0.0
                },
                'execution_stats': {
                    'total': sum(execution_times) if execution_times else 0.0,
                    'avg': statistics.mean(execution_times) if execution_times else 0.0,
                    'max': max(execution_times) if execution_times else 0.0,
                    'min': min(execution_times) if execution_times else 0.0
                }
            }
            
            logger.info(f"전체 통계 계산 완료: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"전체 통계 계산 실패: {e}")
            return {}
    
    def export_processed_data(self) -> Dict[str, Any]:
        """처리된 데이터 전체 반환"""
        return {
            'raw_data': self.raw_performance_data,
            'processed_metrics': [
                {
                    'timestamp': m.timestamp,
                    'run': m.run_number,
                    'memory_mb': m.memory_mb,
                    'cpu_percent': m.cpu_percent
                }
                for m in self.processed_metrics
            ],
            'run_summaries': [
                {
                    'repeat': s.run_number,
                    'time': s.execution_time,
                    'events': s.event_count,
                    'crash': s.crash_count,
                    'anr': s.anr_count,
                    'timeout': s.timeout_count,
                    'mem_peak': s.memory_peak,
                    'cpu_peak': s.cpu_peak
                }
                for s in self.run_summaries
            ],
            'statistics': self.get_overall_statistics()
        }
