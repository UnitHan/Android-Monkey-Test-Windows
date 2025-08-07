#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gemini API 기반 적응형 테스트 제어기
"""
import json
import time
import logging
from typing import Dict, List, Any, Optional, Tuple
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

class GeminiAdaptiveController:
    """Gemini API를 활용한 지능형 적응형 테스트 제어"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
        self.learning_history = []
        self.optimization_cache = {}
        self.target_duration = 18 * 60  # 18분 = 1080초
        
    def analyze_performance_and_recommend(self, 
                                        performance_history: List[Dict],
                                        current_run: int,
                                        device_info: Dict,
                                        app_package: str) -> Dict[str, Any]:
        """성능 데이터 분석 후 최적화 권장사항 생성"""
        try:
            # 성능 데이터 준비
            analysis_data = self._prepare_analysis_data(performance_history, device_info, app_package)
            
            # Gemini에게 분석 요청
            prompt = self._create_analysis_prompt(analysis_data, current_run)
            response = self._call_gemini_api(prompt)
            
            if response:
                recommendations = self._parse_gemini_response(response)
                
                # 캐시에 저장
                cache_key = f"{app_package}_{device_info.get('model', 'unknown')}"
                self.optimization_cache[cache_key] = {
                    'timestamp': datetime.now(),
                    'recommendations': recommendations,
                    'run': current_run
                }
                
                logger.info(f"🤖 Gemini 분석 완료: {recommendations.get('summary', 'N/A')}")
                return recommendations
            else:
                logger.warning("Gemini API 응답 실패, 기본 로직 사용")
                return self._fallback_analysis(performance_history)
                
        except Exception as e:
            logger.error(f"Gemini 분석 중 오류: {e}")
            return self._fallback_analysis(performance_history)
    
    def _prepare_analysis_data(self, history: List[Dict], device_info: Dict, app_package: str) -> Dict:
        """분석용 데이터 정리"""
        if not history:
            return {}
        
        # 최근 3회차 데이터 추출
        recent_data = history[-3:] if len(history) >= 3 else history
        
        # 통계 계산
        durations = [d.get('actual_duration', 0) for d in recent_data]
        accuracy_scores = [d.get('accuracy_percent', 0) for d in recent_data]
        event_rates = [d.get('events_completed', 0) / d.get('actual_duration', 1) for d in recent_data]
        
        return {
            'app_package': app_package,
            'device_model': device_info.get('model', 'Unknown'),
            'android_version': device_info.get('android_version', 'Unknown'),
            'target_duration': self.target_duration,
            'recent_performance': {
                'runs': len(recent_data),
                'avg_duration': sum(durations) / len(durations) if durations else 0,
                'avg_accuracy': sum(accuracy_scores) / len(accuracy_scores) if accuracy_scores else 0,
                'avg_event_rate': sum(event_rates) / len(event_rates) if event_rates else 0,
                'duration_trend': self._calculate_trend(durations),
                'accuracy_trend': self._calculate_trend(accuracy_scores)
            },
            'detailed_history': recent_data
        }
    
    def _create_analysis_prompt(self, data: Dict, current_run: int) -> str:
        """Gemini 분석용 프롬프트 생성"""
        return f"""
안드로이드 Monkey 테스트 성능 분석 및 최적화 요청

## 테스트 환경
- 앱: {data.get('app_package', 'Unknown')}
- 디바이스: {data.get('device_model', 'Unknown')} (Android {data.get('android_version', 'Unknown')})
- 목표: 정확히 18분(1080초) 실행
- 현재 회차: {current_run}

## 최근 성능 데이터
{json.dumps(data.get('recent_performance', {}), indent=2, ensure_ascii=False)}

## 상세 이력
{json.dumps(data.get('detailed_history', []), indent=2, ensure_ascii=False)}

## 분석 요청
1. 현재 성능 트렌드 분석 (시간 정확도, 이벤트 처리 속도)
2. 18분 목표 달성을 위한 최적 이벤트 수 계산
3. throttle 값 조정 권장사항
4. 다음 회차 예상 성능 및 위험 요소

## 중요 제약사항
- Deep Test의 경우 이벤트 수는 22,000개 고정 (±5% 범위 내에서만 조정)
- 18분 정확도 우선: 이벤트 수보다는 throttle 조정으로 시간 제어
- 급격한 변화 금지: 이전 회차 대비 10% 이상 변경 불가

## 응답 형식 (JSON)
{{
    "summary": "분석 요약 (한 줄)",
    "trend_analysis": "성능 트렌드 분석",
    "recommended_events": 추천_이벤트_수(정수_22000_고정),
    "recommended_throttle": 추천_throttle값(정수_ms),
    "confidence": 신뢰도(0-100),
    "reasoning": "추천 근거 (한 줄)",
    "risk_factors": ["위험요소1", "위험요소2"],
    "next_run_prediction": {{
        "expected_duration": 예상_실행시간_초,
        "accuracy_score": 예상_정확도점수
    }}
}}

정확한 JSON 형식으로만 응답해주세요.
"""
    
    def _call_gemini_api(self, prompt: str) -> Optional[str]:
        """Gemini API 호출"""
        try:
            # API 호출 로깅 강화
            logger.info(f"🌐 Gemini API 호출 시작 (시간: {datetime.now().strftime('%H:%M:%S')})")
            
            headers = {
                'Content-Type': 'application/json',
            }
            
            payload = {
                "contents": [{
                    "parts": [{
                        "text": prompt
                    }]
                }],
                "generationConfig": {
                    "temperature": 0.1,
                    "topK": 1,
                    "topP": 1,
                    "maxOutputTokens": 2048,
                }
            }
            
            url = f"{self.base_url}?key={self.api_key}"
            start_time = time.time()
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            api_duration = time.time() - start_time
            
            logger.info(f"🌐 Gemini API 응답 (소요시간: {api_duration:.2f}초, 상태: {response.status_code})")
            
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and len(result['candidates']) > 0:
                    content = result['candidates'][0]['content']['parts'][0]['text']
                    logger.info(f"✅ Gemini API 성공 - 응답 길이: {len(content)}자")
                    return content.strip()
            else:
                logger.error(f"❌ Gemini API 오류: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Gemini API 호출 실패: {e}")
            return None
    
    def _parse_gemini_response(self, response_text: str) -> Dict[str, Any]:
        """Gemini 응답 파싱"""
        try:
            # JSON 부분만 추출
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_text = response_text[start_idx:end_idx]
                parsed = json.loads(json_text)
                
                # 데이터 유효성 검증
                if self._validate_recommendations(parsed):
                    return parsed
                else:
                    logger.warning("Gemini 응답 데이터 유효성 검증 실패")
                    return self._fallback_analysis([])
            else:
                logger.warning("Gemini 응답에서 JSON 형식을 찾을 수 없음")
                return self._fallback_analysis([])
                
        except json.JSONDecodeError as e:
            logger.error(f"Gemini 응답 JSON 파싱 실패: {e}")
            return self._fallback_analysis([])
    
    def _validate_recommendations(self, data: Dict) -> bool:
        """권장사항 유효성 검증"""
        required_fields = ['recommended_events', 'recommended_throttle', 'confidence']
        
        for field in required_fields:
            if field not in data:
                logger.warning(f"누락된 필드: {field}")
                return False
        
        # 범위 검증
        events = data.get('recommended_events', 0)
        throttle = data.get('recommended_throttle', 0)
        confidence = data.get('confidence', 0)
        
        if not (5000 <= events <= 50000):  # 이벤트 수 범위
            logger.warning(f"이벤트 수 범위 벗어남: {events} (5000-50000 필요)")
            return False
        if not (50 <= throttle <= 500):    # throttle 범위
            logger.warning(f"throttle 범위 벗어남: {throttle} (50-500 필요)")
            return False
        if not (0 <= confidence <= 100):   # 신뢰도 범위
            logger.warning(f"신뢰도 범위 벗어남: {confidence} (0-100 필요)")
            return False
        
        return True
    
    def _fallback_analysis(self, history: List[Dict]) -> Dict[str, Any]:
        """API 실패 시 기본 분석"""
        if not history:
            return {
                'summary': '데이터 부족으로 기본 설정 사용',
                'optimal_events': 15000,
                'optimal_throttle': 150,
                'confidence': 50,
                'trend_analysis': '분석 데이터 부족',
                'risk_factors': ['성능 데이터 부족'],
                'next_run_prediction': {
                    'expected_duration': 1080,
                    'accuracy_score': 80
                }
            }
        
        # 간단한 통계 기반 분석
        recent = history[-1]
        duration = recent.get('actual_duration', 1080)
        events = recent.get('events_target', 15000)
        
        # 비율 기반 조정
        time_ratio = duration / self.target_duration
        optimal_events = int(events / time_ratio)
        optimal_events = max(5000, min(50000, optimal_events))  # 범위 제한
        
        return {
            'summary': f'기본 분석: 시간 비율 {time_ratio:.2f} 기반 조정',
            'optimal_events': optimal_events,
            'optimal_throttle': 150,
            'confidence': 70,
            'trend_analysis': '단순 비율 기반 분석',
            'risk_factors': ['AI 분석 실패'],
            'next_run_prediction': {
                'expected_duration': self.target_duration,
                'accuracy_score': 75
            }
        }
    
    def _calculate_trend(self, values: List[float]) -> str:
        """트렌드 계산"""
        if len(values) < 2:
            return "데이터 부족"
        
        if values[-1] > values[0]:
            return "증가"
        elif values[-1] < values[0]:
            return "감소"
        else:
            return "안정"
    
    def get_cached_recommendation(self, app_package: str, device_model: str) -> Optional[Dict]:
        """캐시된 권장사항 조회"""
        cache_key = f"{app_package}_{device_model}"
        cached = self.optimization_cache.get(cache_key)
        
        if cached:
            # 1시간 이내 캐시만 유효
            time_diff = (datetime.now() - cached['timestamp']).total_seconds()
            if time_diff < 3600:  # 1시간
                return cached['recommendations']
        
        return None
    
    def save_learning_data(self, run_data: Dict):
        """학습 데이터 저장"""
        self.learning_history.append({
            'timestamp': datetime.now(),
            'data': run_data
        })
        
        # 최근 100개만 유지
        if len(self.learning_history) > 100:
            self.learning_history = self.learning_history[-100:]
