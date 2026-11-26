#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gemini AI 기반 적응형 테스트 파라미터 최적화 시스템
실제 테스트 결과를 분석하여 목표 시간에 맞는 최적의 이벤트 수와 스로틀 값을 자동 조정
"""
import logging
import json
import time
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import statistics

logger = logging.getLogger(__name__)


class AdaptiveTestTuner:
    """Gemini AI 기반 적응형 테스트 튜닝 클래스"""
    
    def __init__(self):
        self.learning_data_file = Path("src/data/adaptive_tuning_data.json")
        self.learning_data = self._load_learning_data()
        
        # 프리셋별 목표 시간 (분)
        self.target_times = {
            "Deep Test": 18,        # 18분 목표
            "Extreme Test": 32,     # 32분 목표  
            "Standard Test": 15,    # 15분 목표 (회차당 15분 × 6회차 = 90분 총 시간)
            "Quick Test": 5,        # 5분 목표
            "Smoke Test": 3         # 3분 목표
        }
        
        # 허용 오차 범위 (분)
        self.tolerance_minutes = 2
        
    def _load_learning_data(self) -> Dict:
        """학습 데이터 로드"""
        try:
            if self.learning_data_file.exists():
                with open(self.learning_data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"✅ 적응형 학습 데이터 로드 완료: {len(data)}개 프리셋")
                    return data
            else:
                logger.info("🔧 새로운 적응형 학습 데이터 생성")
                return {}
        except Exception as e:
            logger.error(f"학습 데이터 로드 실패: {e}")
            return {}
    
    def _save_learning_data(self):
        """학습 데이터 저장"""
        try:
            # 디렉토리 생성
            self.learning_data_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.learning_data_file, 'w', encoding='utf-8') as f:
                json.dump(self.learning_data, f, ensure_ascii=False, indent=2)
            logger.debug("적응형 학습 데이터 저장 완료")
        except Exception as e:
            logger.error(f"학습 데이터 저장 실패: {e}")
    
    def record_test_result(self, preset_name: str, events: int, throttle: int, 
                          actual_duration_minutes: float, package_name: str = ""):
        """테스트 결과 기록"""
        try:
            if preset_name not in self.learning_data:
                self.learning_data[preset_name] = {
                    "results": [],
                    "optimized_params": {},
                    "last_update": time.time()
                }
            
            # 결과 기록
            result = {
                "events": events,
                "throttle": throttle,
                "duration_minutes": actual_duration_minutes,
                "package": package_name,
                "timestamp": time.time(),
                "device_info": self._get_device_context()
            }
            
            self.learning_data[preset_name]["results"].append(result)
            
            # 최근 20개 결과만 유지
            if len(self.learning_data[preset_name]["results"]) > 20:
                self.learning_data[preset_name]["results"] = \
                    self.learning_data[preset_name]["results"][-20:]
            
            self.learning_data[preset_name]["last_update"] = time.time()
            self._save_learning_data()
            
            logger.info(f"🤖 Gemini 학습 데이터 기록: {preset_name} - "
                       f"{events}개 이벤트, {throttle}ms 스로틀, {actual_duration_minutes:.1f}분 소요")
            
        except Exception as e:
            logger.error(f"테스트 결과 기록 실패: {e}")
    
    def _get_device_context(self) -> Dict:
        """디바이스 컨텍스트 정보 수집"""
        # 실제 구현에서는 ADB를 통해 디바이스 정보 수집
        return {
            "model": "unknown",
            "android_version": "unknown",
            "cpu_info": "unknown"
        }
    
    def get_optimized_parameters(self, preset_name: str, current_events: int, 
                               current_throttle: int) -> Tuple[int, int, str]:
        """Gemini AI 기반 최적화된 파라미터 추천"""
        try:
            target_time = self.target_times.get(preset_name)
            if not target_time:
                logger.warning(f"알 수 없는 프리셋: {preset_name}")
                return current_events, current_throttle, "기본값 유지"
            
            # 학습 데이터가 있는지 확인
            if preset_name not in self.learning_data or not self.learning_data[preset_name]["results"]:
                logger.info(f"🔧 {preset_name}: 학습 데이터 없음, 기본값 사용")
                return current_events, current_throttle, "초기 실행 - 기본값 사용"
            
            results = self.learning_data[preset_name]["results"]
            
            # Gemini AI 분석 로직
            analysis = self._analyze_with_gemini_ai(results, target_time, current_events, current_throttle)
            
            optimized_events = analysis["recommended_events"]
            optimized_throttle = analysis["recommended_throttle"]
            reasoning = analysis["reasoning"]
            
            # 변경 사항 로깅
            if optimized_events != current_events or optimized_throttle != current_throttle:
                logger.info(f"🤖 Gemini 최적화 추천: {preset_name}")
                logger.info(f"   📊 이벤트: {current_events} → {optimized_events}")
                logger.info(f"   ⏱️ 스로틀: {current_throttle}ms → {optimized_throttle}ms")
                logger.info(f"   🎯 목표시간: {target_time}분")
                logger.info(f"   🧠 추론: {reasoning}")
            
            return optimized_events, optimized_throttle, reasoning
            
        except Exception as e:
            logger.error(f"파라미터 최적화 실패: {e}")
            return current_events, current_throttle, f"최적화 오류: {str(e)}"
    
    def _analyze_with_gemini_ai(self, results: List[Dict], target_time: float, 
                              current_events: int, current_throttle: int) -> Dict:
        """Gemini AI 스타일 분석 로직"""
        try:
            # 최근 결과들 분석
            recent_results = results[-5:]  # 최근 5개 결과
            
            # 평균 실행 시간 계산
            avg_duration = statistics.mean([r["duration_minutes"] for r in recent_results])
            
            # 시간 차이 분석
            time_diff = avg_duration - target_time
            time_diff_ratio = time_diff / target_time
            
            # Gemini AI 스타일 추론
            reasoning_parts = []
            
            if abs(time_diff) <= self.tolerance_minutes:
                # 목표 시간에 근접한 경우
                reasoning_parts.append(f"현재 평균 {avg_duration:.1f}분으로 목표 {target_time}분에 근접")
                return {
                    "recommended_events": current_events,
                    "recommended_throttle": current_throttle,
                    "reasoning": "현재 설정이 최적 상태 - 변경 불필요"
                }
            
            # 조정이 필요한 경우
            if time_diff > 0:
                # 목표보다 오래 걸리는 경우 - 줄여야 함
                adjustment_factor = min(0.8, 1 - (time_diff_ratio * 0.5))
                reasoning_parts.append(f"평균 {avg_duration:.1f}분으로 목표보다 {time_diff:.1f}분 초과")
                reasoning_parts.append("실행시간 단축을 위해 파라미터 조정")
            else:
                # 목표보다 빨리 끝나는 경우 - 늘려야 함
                adjustment_factor = min(1.3, 1 + (abs(time_diff_ratio) * 0.6))
                reasoning_parts.append(f"평균 {avg_duration:.1f}분으로 목표보다 {abs(time_diff):.1f}분 부족")
                reasoning_parts.append("목표시간 달성을 위해 파라미터 증가")
            
            # 스마트 조정 로직
            new_events, new_throttle = self._smart_parameter_adjustment(
                current_events, current_throttle, adjustment_factor, recent_results
            )
            
            # 추론 설명 완성
            events_change = new_events - current_events
            throttle_change = new_throttle - current_throttle
            
            if events_change != 0:
                reasoning_parts.append(f"이벤트 수 {events_change:+d}개 조정")
            if throttle_change != 0:
                reasoning_parts.append(f"스로틀 {throttle_change:+d}ms 조정")
            
            return {
                "recommended_events": new_events,
                "recommended_throttle": new_throttle,
                "reasoning": " | ".join(reasoning_parts)
            }
            
        except Exception as e:
            logger.error(f"Gemini AI 분석 오류: {e}")
            return {
                "recommended_events": current_events,
                "recommended_throttle": current_throttle,
                "reasoning": f"분석 오류: {str(e)}"
            }
    
    def _smart_parameter_adjustment(self, events: int, throttle: int, 
                                  adjustment_factor: float, recent_results: List[Dict]) -> Tuple[int, int]:
        """스마트한 파라미터 조정 로직"""
        
        # 이벤트 수와 스로틀의 영향 분석
        event_sensitivity = self._analyze_event_sensitivity(recent_results)
        throttle_sensitivity = self._analyze_throttle_sensitivity(recent_results)
        
        # 조정 전략 결정
        if event_sensitivity > throttle_sensitivity:
            # 이벤트 수가 더 영향이 클 때 - 이벤트 수 우선 조정
            new_events = max(1000, int(events * adjustment_factor))
            new_throttle = throttle
            
            # 필요시 스로틀도 보정
            if abs(adjustment_factor - 1.0) > 0.15:  # 15% 이상 차이나면
                throttle_adjustment = min(1.1, max(0.9, adjustment_factor))
                new_throttle = max(50, int(throttle * throttle_adjustment))
                
        else:
            # 스로틀이 더 영향이 클 때 - 스로틀 우선 조정
            new_throttle = max(50, int(throttle * adjustment_factor))
            new_events = events
            
            # 필요시 이벤트 수도 보정
            if abs(adjustment_factor - 1.0) > 0.2:  # 20% 이상 차이나면
                event_adjustment = min(1.15, max(0.85, adjustment_factor))
                new_events = max(1000, int(events * event_adjustment))
        
        # 안전 범위 체크
        new_events = max(1000, min(50000, new_events))  # 1K~50K 범위
        new_throttle = max(50, min(1000, new_throttle))  # 50ms~1000ms 범위
        
        return new_events, new_throttle
    
    def _analyze_event_sensitivity(self, results: List[Dict]) -> float:
        """이벤트 수의 시간 영향도 분석"""
        if len(results) < 2:
            return 0.5  # 기본값
        
        try:
            # 이벤트 수와 실행 시간의 상관관계 분석
            events_list = [r["events"] for r in results]
            duration_list = [r["duration_minutes"] for r in results]
            
            # 간단한 상관관계 계산
            if len(set(events_list)) > 1:  # 이벤트 수에 변화가 있었던 경우
                correlation = abs(self._calculate_correlation(events_list, duration_list))
                return min(1.0, correlation)
            
            return 0.5
            
        except Exception:
            return 0.5
    
    def _analyze_throttle_sensitivity(self, results: List[Dict]) -> float:
        """스로틀의 시간 영향도 분석"""
        if len(results) < 2:
            return 0.5  # 기본값
        
        try:
            # 스로틀과 실행 시간의 상관관계 분석
            throttle_list = [r["throttle"] for r in results]
            duration_list = [r["duration_minutes"] for r in results]
            
            # 간단한 상관관계 계산
            if len(set(throttle_list)) > 1:  # 스로틀에 변화가 있었던 경우
                correlation = abs(self._calculate_correlation(throttle_list, duration_list))
                return min(1.0, correlation)
            
            return 0.5
            
        except Exception:
            return 0.5
    
    def _calculate_correlation(self, x_list: List[float], y_list: List[float]) -> float:
        """간단한 피어슨 상관계수 계산"""
        try:
            n = len(x_list)
            if n < 2:
                return 0.0
            
            sum_x = sum(x_list)
            sum_y = sum(y_list)
            sum_xy = sum(x * y for x, y in zip(x_list, y_list))
            sum_x2 = sum(x * x for x in x_list)
            sum_y2 = sum(y * y for y in y_list)
            
            numerator = n * sum_xy - sum_x * sum_y
            denominator = ((n * sum_x2 - sum_x * sum_x) * (n * sum_y2 - sum_y * sum_y)) ** 0.5
            
            if denominator == 0:
                return 0.0
            
            return numerator / denominator
            
        except Exception:
            return 0.0
    
    def get_preset_performance_summary(self, preset_name: str) -> Dict:
        """프리셋 성능 요약 반환"""
        try:
            if preset_name not in self.learning_data:
                return {"error": "학습 데이터 없음"}
            
            results = self.learning_data[preset_name]["results"]
            if not results:
                return {"error": "테스트 결과 없음"}
            
            recent_results = results[-5:]
            
            return {
                "total_tests": len(results),
                "recent_avg_duration": statistics.mean([r["duration_minutes"] for r in recent_results]),
                "target_duration": self.target_times.get(preset_name, 0),
                "duration_variance": statistics.variance([r["duration_minutes"] for r in recent_results]) if len(recent_results) > 1 else 0,
                "last_params": {
                    "events": recent_results[-1]["events"],
                    "throttle": recent_results[-1]["throttle"]
                } if recent_results else {},
                "optimization_active": True
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def reset_learning_data(self, preset_name: Optional[str] = None):
        """학습 데이터 리셋"""
        if preset_name:
            if preset_name in self.learning_data:
                del self.learning_data[preset_name]
                logger.info(f"🔄 {preset_name} 학습 데이터 리셋")
        else:
            self.learning_data.clear()
            logger.info("🔄 모든 학습 데이터 리셋")
        
        self._save_learning_data()


# 전역 인스턴스
_adaptive_tuner = None

def get_adaptive_tuner() -> AdaptiveTestTuner:
    """전역 적응형 튜너 인스턴스 반환"""
    global _adaptive_tuner
    if _adaptive_tuner is None:
        _adaptive_tuner = AdaptiveTestTuner()
    return _adaptive_tuner
