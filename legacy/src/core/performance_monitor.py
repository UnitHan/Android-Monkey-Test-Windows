#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
성능 모니터링
"""
import time
import threading
import datetime
from typing import List, Dict, Any, Optional, Callable
from src.core.adb_client import AdbClient
from src.core.test_context import TestContext
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class PerformanceMonitor:
    """성능 모니터링 클래스"""
    
    def __init__(self, adb_client: AdbClient, test_context: TestContext):
        self.adb_client = adb_client
        self.test_context = test_context
        self.monitoring_thread: Optional[threading.Thread] = None
        self.data_callback: Optional[Callable] = None
    
    def set_data_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """데이터 업데이트 콜백 설정"""
        self.data_callback = callback
    
    def start_monitoring(self, package_name: str, run_num: int, interval: int = 2):
        """성능 모니터링 시작"""
        if self.test_context.monitoring_active:
            logger.warning("모니터링이 이미 활성화되어 있습니다.")
            return
        
        self.test_context.monitoring_active = True
        self.monitoring_thread = threading.Thread(
            target=self._monitor_performance,
            args=(package_name, run_num, interval),
            daemon=True
        )
        self.monitoring_thread.start()
        logger.info(f"성능 모니터링 시작 - 회차 {run_num}")
    
    def stop_monitoring(self):
        """성능 모니터링 중지"""
        if not self.test_context.monitoring_active:
            return
        
        self.test_context.monitoring_active = False
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=5)
        
        logger.info("성능 모니터링 중지")
    
    def _monitor_performance(self, package_name: str, run_num: int, interval: int):
        """성능 모니터링 실행"""
        while self.test_context.monitoring_active:
            try:
                timestamp = datetime.datetime.now().strftime('%H:%M:%S')
                
                # 메모리 사용량 수집
                mem_mb = self.adb_client.get_memory_info(package_name)
                
                # CPU 사용률 수집
                cpu_percent = self.adb_client.get_cpu_usage(package_name)
                
                # 데이터 저장
                perf_data = {
                    "timestamp": timestamp,
                    "run": run_num,
                    "mem_mb": mem_mb,
                    "cpu_percent": cpu_percent
                }
                
                self.test_context.current_performance_data.append(perf_data)
                
                # 콜백 호출
                if self.data_callback:
                    try:
                        self.data_callback(perf_data)
                    except Exception as e:
                        logger.warning(f"데이터 콜백 실행 오류: {e}")
                
                logger.debug(f"성능 데이터 - 회차 {run_num}: 메모리={mem_mb}MB, CPU={cpu_percent}%")
                
            except Exception as e:
                logger.warning(f"성능 모니터링 오류: {e}")
            
            time.sleep(interval)
    
    def get_performance_summary(self, run_num: Optional[int] = None) -> Dict[str, Any]:
        """성능 요약 통계 반환"""
        data = self.test_context.current_performance_data
        
        if run_num is not None:
            data = [d for d in data if d.get("run") == run_num]
        
        if not data:
            return {"mem_peak": "N/A", "cpu_peak": "N/A", "mem_avg": "N/A", "cpu_avg": "N/A"}
        
        mem_values = [d["mem_mb"] for d in data if d.get("mem_mb") is not None]
        cpu_values = [d["cpu_percent"] for d in data if d.get("cpu_percent") is not None]
        
        summary = {
            "mem_peak": f"{max(mem_values):.0f}MB" if mem_values else "N/A",
            "cpu_peak": f"{max(cpu_values):.0f}%" if cpu_values else "N/A",
            "mem_avg": f"{sum(mem_values)/len(mem_values):.0f}MB" if mem_values else "N/A",
            "cpu_avg": f"{sum(cpu_values)/len(cpu_values):.0f}%" if cpu_values else "N/A"
        }
        
        return summary
    
    def analyze_performance_issues(self) -> List[str]:
        """성능 이슈 분석"""
        from src.config import MEMORY_WARNING_THRESHOLD, MEMORY_CRITICAL_THRESHOLD
        from src.config import CPU_WARNING_THRESHOLD, CPU_CRITICAL_THRESHOLD
        
        issues = []
        
        if not self.test_context.current_performance_data:
            return issues
        
        mem_values = [d["mem_mb"] for d in self.test_context.current_performance_data 
                     if d.get("mem_mb") is not None]
        cpu_values = [d["cpu_percent"] for d in self.test_context.current_performance_data 
                     if d.get("cpu_percent") is not None]
        
        # 메모리 분석
        if mem_values:
            max_mem = max(mem_values)
            avg_mem = sum(mem_values) / len(mem_values)
            
            if max_mem > MEMORY_CRITICAL_THRESHOLD:
                issues.append(f"🚨 메모리 사용량 최대 {max_mem:.0f}MB → 메모리 누수 점검 필요")
            elif max_mem > MEMORY_WARNING_THRESHOLD:
                issues.append(f"⚠️ 메모리 사용량 {max_mem:.0f}MB → 이미지 캐싱 최적화 권장")
            
            if avg_mem > MEMORY_WARNING_THRESHOLD:
                issues.append(f"📊 평균 메모리 사용량 {avg_mem:.0f}MB → 메모리 관리 검토 필요")
        
        # CPU 분석
        if cpu_values:
            max_cpu = max(cpu_values)
            avg_cpu = sum(cpu_values) / len(cpu_values)
            
            if max_cpu > CPU_CRITICAL_THRESHOLD:
                issues.append(f"🚨 CPU 사용률 최대 {max_cpu:.0f}% → CPU 집약적 작업 최적화 필요")
            elif max_cpu > CPU_WARNING_THRESHOLD:
                issues.append(f"⚠️ CPU 최대 사용률 {max_cpu:.0f}% → 성능 최적화 검토 권장")
            
            if avg_cpu > CPU_WARNING_THRESHOLD:
                issues.append(f"📊 평균 CPU 사용률 {avg_cpu:.0f}% → 백그라운드 작업 검토 권장")
        
        return issues
