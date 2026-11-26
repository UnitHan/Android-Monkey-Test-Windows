import matplotlib
import threading
import os

# 스레드별 matplotlib 백엔드 설정
def setup_matplotlib_backend():
    """스레드별 matplotlib 백엔드 안전 설정"""
    try:
        # 메인 스레드가 아닌 경우 또는 GUI가 없는 환경에서는 Agg 사용
        if threading.current_thread() != threading.main_thread() or os.environ.get('DISPLAY') is None:
            matplotlib.use('Agg', force=True)
        else:
            # 메인 스레드에서는 현재 백엔드 유지 또는 Agg 사용
            current_backend = matplotlib.get_backend()
            if current_backend in ['TkAgg', 'Qt5Agg', 'Qt4Agg']:
                # GUI 백엔드인 경우 Agg로 변경하여 스레드 안전성 확보
                matplotlib.use('Agg', force=True)
    except Exception as e:
        # 설정 실패 시 기본 Agg 사용
        matplotlib.use('Agg', force=True)

# 백엔드 설정 실행
setup_matplotlib_backend()

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter, MaxNLocator
import numpy as np
import seaborn as sns
import base64
import io
import tempfile
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# matplotlib 사용 가능 여부 확인
try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

@dataclass
class TestResultData:
    """테스트 결과 데이터 구조"""
    repeat_number: int
    execution_time: float
    event_count: int
    crash_count: int
    anr_count: int
    timeout_count: int
    memory_peak: float
    cpu_peak: float
    seed: Optional[str] = None
    timestamp: Optional[str] = None
    start_time: Optional[str] = None  # 테스트 시작 시간 (시간대 표시용)

class ChartGenerator:
    def __init__(self):
        """차트 생성기 초기화"""
        self.setup_font()
        self.figures = {}
        
    def setup_font(self):
        """한글 폰트 설정"""
        try:
            # 현재 작업 디렉토리의 fonts 폴더에서 폰트 찾기
            font_paths = [
                'fonts/NotoSansKR_Regular.otf',
                'fonts/NotoSansKR_Medium.otf', 
                'fonts/NotoSansKR_Bold.otf'
            ]
            
            font_found = False
            for font_path in font_paths:
                if os.path.exists(font_path):
                    prop = fm.FontProperties(fname=font_path)
                    plt.rcParams['font.family'] = prop.get_name()
                    font_found = True
                    print(f"Custom font loaded: {font_path}")
                    break
            
            if not font_found:
                # 시스템 한글 폰트 찾기
                system_fonts = ['Malgun Gothic', 'Microsoft YaHei', 'SimHei', 'DejaVu Sans']
                for font_name in system_fonts:
                    try:
                        plt.rcParams['font.family'] = font_name
                        print(f"System font loaded: {font_name}")
                        break
                    except:
                        continue
                else:
                    print("Warning: No Korean font found, using default font")
            
        except Exception as e:
            print(f"Font setup error: {e}")
            
        # 기본 설정
        plt.rcParams['font.size'] = 9
        plt.rcParams['axes.unicode_minus'] = False
        
    def create_performance_charts(self, test_results, app_package="Unknown Package"):
        """성능 차트 생성 (메모리 + CPU)"""
        if not test_results:
            return None
            
        try:
            # 차트 생성
            memory_chart = self._create_memory_chart(test_results, app_package)
            cpu_chart = self._create_cpu_chart(test_results, app_package)
            
            return {
                'memory': memory_chart,
                'cpu': cpu_chart
            }
            
        except Exception as e:
            print(f"Chart generation error: {e}")
            return None
    
    def create_simple_performance_charts(self, performance_data, app_package="Unknown Package"):
        """간단한 성능 데이터로부터 차트 생성 (Old 버전 스타일)"""
        try:
            logger.info(f"간단한 성능 차트 생성 시작 - 데이터: {len(performance_data)}개")
            
            if not performance_data:
                logger.warning("성능 데이터가 비어있습니다")
                return None
            
            # 데이터 샘플 로깅
            if performance_data:
                logger.info(f"성능 데이터 샘플: {performance_data[0]}")
            
            # 메모리와 CPU 데이터 직접 추출
            memory_values = []
            cpu_values = []
            timestamps = []
            
            for i, data in enumerate(performance_data):
                try:
                    # 다양한 데이터 구조에 대응
                    memory_val = None
                    cpu_val = None
                    timestamp = None
                    
                    # 메모리 값 추출
                    if 'memory' in data:
                        memory_val = float(data['memory'])
                    elif 'memory_mb' in data:
                        memory_val = float(data['memory_mb'])
                    elif 'memory_peak' in data:
                        memory_val = float(data['memory_peak'])
                    
                    # CPU 값 추출  
                    if 'cpu' in data:
                        cpu_val = float(data['cpu'])
                    elif 'cpu_percent' in data:
                        cpu_val = float(data['cpu_percent'])
                    elif 'cpu_peak' in data:
                        cpu_val = float(data['cpu_peak'])
                    
                    # 타임스탬프 추출
                    if 'timestamp' in data:
                        timestamp = data['timestamp']
                    elif 'time' in data:
                        timestamp = data['time']
                    else:
                        timestamp = f"데이터{i+1}"
                    
                    # 유효한 데이터만 추가
                    if memory_val is not None and memory_val > 0:
                        memory_values.append(memory_val)
                    if cpu_val is not None and cpu_val > 0:
                        cpu_values.append(cpu_val)
                    if timestamp is not None:
                        # 시간 형식을 HH:MM으로 변환
                        formatted_time = self._format_time_for_chart(timestamp)
                        timestamps.append(formatted_time)
                        
                    if i < 3:  # 첫 3개만 로그
                        logger.info(f"데이터 {i}: 메모리={memory_val}MB, CPU={cpu_val}%, 시간={timestamp} -> {formatted_time if timestamp else 'N/A'}")
                        
                except Exception as e:
                    logger.warning(f"데이터 {i} 처리 실패: {e}")
                    continue
            
            logger.info(f"데이터 추출 완료 - 메모리: {len(memory_values)}개, CPU: {len(cpu_values)}개")
            
            charts = {}
            
            # 메모리 차트 생성
            if memory_values:
                memory_chart = self._create_simple_memory_chart(memory_values, timestamps[:len(memory_values)], app_package)
                if memory_chart:
                    charts['memory'] = memory_chart
                    logger.info("메모리 차트 생성 성공")
            
            # CPU 차트 생성
            if cpu_values:
                cpu_chart = self._create_simple_cpu_chart(cpu_values, timestamps[:len(cpu_values)], app_package)
                if cpu_chart:
                    charts['cpu'] = cpu_chart
                    logger.info("CPU 차트 생성 성공")
            
            if charts:
                logger.info(f"간단한 성능 차트 생성 완료: {list(charts.keys())}")
                return charts
            else:
                logger.warning("유효한 차트를 생성할 수 없습니다")
                return None
                
        except Exception as e:
            logger.error(f"간단한 성능 차트 생성 오류: {e}")
            return None
    
    def _create_memory_chart(self, test_results, app_package="Unknown Package"):
        """메모리 사용량 차트 생성"""
        try:
            # 데이터 추출
            memory_data = []
            for i, result in enumerate(test_results):
                if hasattr(result, 'performance_data') and result.performance_data:
                    memory_data.extend(result.performance_data.get('memory', []))
            
            if not memory_data:
                return None
            
            # 차트 생성
            fig, ax = plt.subplots(figsize=(10, 6))
            
            # 데이터 플롯
            iterations = range(len(memory_data))
            ax.plot(iterations, memory_data, 'b-', linewidth=2, marker='o', markersize=4)
            
            # 차트 스타일링
            app_name = app_package if app_package != "Unknown Package" else "앱"
            ax.set_title(f'{app_name} 메모리 사용량', fontsize=14, fontweight='bold')
            ax.set_xlabel('테스트 횟수', fontsize=12)
            ax.set_ylabel('메모리 사용량 (MB)', fontsize=12)
            ax.grid(True, alpha=0.3)
            
            # 통계 정보 표시
            max_memory = max(memory_data)
            min_memory = min(memory_data)
            avg_memory = sum(memory_data) / len(memory_data)
            
            ax.axhline(y=avg_memory, color='r', linestyle='--', alpha=0.7, label=f'평균: {avg_memory:.1f}MB')
            ax.legend()
            
            plt.tight_layout()
            
            # figure 저장
            self.figures['memory'] = fig
            
            return {
                'figure': fig,
                'base64_image': self._figure_to_base64(fig),
                'temp_file': self._save_figure_temp(fig, 'memory_chart'),
                'title': '메모리 사용량',
                'data': {
                    'max': max_memory,
                    'min': min_memory,
                    'avg': avg_memory,
                    'count': len(memory_data)
                }
            }
            
        except Exception as e:
            print(f"Memory chart creation error: {e}")
            return None
    
    def _create_cpu_chart(self, test_results, app_package="Unknown Package"):
        """CPU 사용률 차트 생성"""
        try:
            # 데이터 추출
            cpu_data = []
            for i, result in enumerate(test_results):
                if hasattr(result, 'performance_data') and result.performance_data:
                    cpu_data.extend(result.performance_data.get('cpu', []))
            
            if not cpu_data:
                return None
            
            # 차트 생성
            fig, ax = plt.subplots(figsize=(10, 6))
            
            # 데이터 플롯
            iterations = range(len(cpu_data))
            ax.plot(iterations, cpu_data, 'g-', linewidth=2, marker='s', markersize=4)
            
            # 차트 스타일링
            app_name = app_package if app_package != "Unknown Package" else "앱"
            ax.set_title(f'{app_name} CPU 사용률', fontsize=14, fontweight='bold')
            ax.set_xlabel('테스트 횟수', fontsize=12)
            ax.set_ylabel('CPU 사용률 (%)', fontsize=12)
            ax.grid(True, alpha=0.3)
            ax.set_ylim(0, 100)
            
            # 통계 정보 표시
            max_cpu = max(cpu_data)
            min_cpu = min(cpu_data)
            avg_cpu = sum(cpu_data) / len(cpu_data)
            
            ax.axhline(y=avg_cpu, color='r', linestyle='--', alpha=0.7, label=f'평균: {avg_cpu:.1f}%')
            ax.legend()
            
            plt.tight_layout()
            
            # figure 저장  
            self.figures['cpu'] = fig
            
            return {
                'figure': fig,
                'base64_image': self._figure_to_base64(fig),
                'temp_file': self._save_figure_temp(fig, 'cpu_chart'),
                'title': 'CPU 사용률',
                'data': {
                    'max': max_cpu,
                    'min': min_cpu,
                    'avg': avg_cpu,
                    'count': len(cpu_data)
                }
            }
            
        except Exception as e:
            print(f"CPU chart creation error: {e}")
            return None

    def create_timeline_charts(self, test_results, app_package="Unknown Package"):
        """시간대별 성능 차트 생성"""
        if not test_results:
            return None
            
        try:
            # 차트 생성
            memory_chart = self._create_memory_timeline_chart_simple(test_results, app_package)
            cpu_chart = self._create_cpu_timeline_chart_simple(test_results, app_package)
            
            return {
                'memory': memory_chart,
                'cpu': cpu_chart
            }
            
        except Exception as e:
            print(f"Timeline chart generation error: {e}")
            return None

    def _create_timeline_charts_from_time_data(self, time_data, app_package="Unknown Package"):
        """시간 데이터로부터 타임라인 차트 생성"""
        try:
            if not time_data:
                logger.warning("시간 데이터가 비어있습니다")
                return None
                
            logger.info(f"시간 데이터로 차트 생성 시작: {len(time_data)}개 데이터")
            logger.info(f"시간 데이터 샘플: {time_data[0] if time_data else 'None'}")
            
            # 메모리와 CPU 데이터 분리
            memory_data = [d['memory'] for d in time_data if 'memory' in d and d['memory'] > 0]
            cpu_data = [d['cpu'] for d in time_data if 'cpu' in d and d['cpu'] > 0]
            times = [d['time'] for d in time_data if 'time' in d]
            
            logger.info(f"데이터 분리 완료 - 메모리: {len(memory_data)}개, CPU: {len(cpu_data)}개, 시간: {len(times)}개")
            
            charts = {}
            
            # 메모리 차트 생성
            if memory_data and len(memory_data) > 0:
                logger.info("메모리 타임라인 차트 생성 시도")
                memory_chart = self._create_memory_timeline_chart_from_time_data(time_data, app_package)
                if memory_chart:
                    charts['memory'] = memory_chart
                    logger.info("메모리 타임라인 차트 생성 성공")
                else:
                    logger.warning("메모리 타임라인 차트 생성 실패")
            else:
                logger.warning(f"메모리 데이터 부족: {len(memory_data)}개")
            
            # CPU 차트 생성
            if cpu_data and len(cpu_data) > 0:
                logger.info("CPU 타임라인 차트 생성 시도")
                cpu_chart = self._create_cpu_timeline_chart_from_time_data(time_data, app_package)
                if cpu_chart:
                    charts['cpu'] = cpu_chart
                    logger.info("CPU 타임라인 차트 생성 성공")
                else:
                    logger.warning("CPU 타임라인 차트 생성 실패")
            else:
                logger.warning(f"CPU 데이터 부족: {len(cpu_data)}개")
            
            if charts:
                logger.info(f"타임라인 차트 생성 완료: {list(charts.keys())}")
                return charts
            else:
                logger.warning("타임라인 차트 생성 실패: 유효한 데이터 없음")
                return None
                
        except Exception as e:
            logger.error(f"타임라인 차트 생성 오류: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def _create_memory_timeline_chart_from_time_data(self, time_data, app_package="Unknown Package"):
        """시간 데이터로부터 메모리 타임라인 차트 생성"""
        try:
            logger.info(f"메모리 차트 생성 시작 - 입력 데이터: {len(time_data)}개")
            if time_data:
                logger.info(f"메모리 차트 데이터 샘플: {time_data[0]}")
            
            memory_values = []
            time_labels = []
            
            for i, data in enumerate(time_data):
                if 'memory' in data and 'time' in data:
                    memory_val = data['memory']
                    memory_values.append(memory_val)
                    # 시간을 문자열로 변환
                    time_obj = data['time']
                    if hasattr(time_obj, 'strftime'):
                        time_labels.append(time_obj.strftime("%H:%M"))
                    else:
                        time_labels.append(str(time_obj))
                    
                    if i < 3:  # 첫 3개만 로그
                        logger.info(f"메모리 데이터 {i}: 메모리={memory_val}MB, 시간={time_labels[-1]}")
                else:
                    logger.warning(f"메모리 데이터 {i}에서 필수 키 누락: {list(data.keys())}")
            
            logger.info(f"메모리 차트 데이터 추출 완료 - 메모리 값: {len(memory_values)}개, 시간 라벨: {len(time_labels)}개")
            
            if not memory_values:
                logger.warning("메모리 차트 생성 실패: 메모리 값이 없음")
                return None
                
            # 차트 생성
            fig, ax = plt.subplots(figsize=(10, 6), dpi=100)
            
            # 한글 폰트 설정
            self._set_korean_font(fig)
            
            # 라인 차트
            ax.plot(range(len(memory_values)), memory_values, 'b-o', linewidth=2, markersize=4)
            
            # 제목과 라벨 설정
            chart_title = f'메모리 사용량 시간대별 추이 - {app_package}' if app_package != "Unknown Package" else '메모리 사용량 시간대별 추이'
            ax.set_title(chart_title, fontsize=12, fontweight='bold', pad=15)
            ax.set_xlabel('시간대', fontsize=10)
            ax.set_ylabel('메모리 (MB)', fontsize=10)
            ax.grid(True, alpha=0.3)
            
            # X축 라벨 설정
            if len(memory_values) <= 10:
                ax.set_xticks(range(len(time_labels)))
                ax.set_xticklabels(time_labels, rotation=45, ha='right')
            else:
                # 데이터가 많으면 일부만 표시
                step = len(time_labels) // 8
                indices = range(0, len(time_labels), step)
                ax.set_xticks(indices)
                ax.set_xticklabels([time_labels[i] for i in indices], rotation=45, ha='right')
            
            # 통계 정보 추가
            if memory_values:
                max_mem = max(memory_values)
                min_mem = min(memory_values)
                avg_mem = sum(memory_values) / len(memory_values)
                ax.text(0.02, 0.98, f'최대: {max_mem:.1f}MB\n평균: {avg_mem:.1f}MB\n최소: {min_mem:.1f}MB', 
                       transform=ax.transAxes, verticalalignment='top', fontsize=9,
                       bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.7))
            
            plt.tight_layout()
            
            chart_result = {
                'figure': fig,
                'base64_image': self._figure_to_base64(fig),
                'temp_file': self._save_figure_temp(fig, f'memory_timeline_{app_package}'),
                'title': chart_title,
                'data': {
                    'max': max(memory_values) if memory_values else 0,
                    'min': min(memory_values) if memory_values else 0,
                    'avg': sum(memory_values) / len(memory_values) if memory_values else 0,
                    'count': len(memory_values)
                }
            }
            
            logger.info(f"메모리 차트 생성 성공 - {len(memory_values)}개 데이터, 최대={max(memory_values):.1f}MB")
            return chart_result
            
        except Exception as e:
            logger.error(f"메모리 타임라인 차트 생성 오류: {e}")
            return None

    def _create_cpu_timeline_chart_from_time_data(self, time_data, app_package="Unknown Package"):
        """시간 데이터로부터 CPU 타임라인 차트 생성"""
        try:
            logger.info(f"CPU 차트 생성 시작 - 입력 데이터: {len(time_data)}개")
            
            cpu_values = []
            time_labels = []
            
            for i, data in enumerate(time_data):
                if 'cpu' in data and 'time' in data:
                    cpu_val = data['cpu']
                    cpu_values.append(cpu_val)
                    # 시간을 문자열로 변환
                    time_obj = data['time']
                    if hasattr(time_obj, 'strftime'):
                        time_labels.append(time_obj.strftime("%H:%M"))
                    else:
                        time_labels.append(str(time_obj))
                    
                    if i < 3:  # 첫 3개만 로그
                        logger.info(f"CPU 데이터 {i}: CPU={cpu_val}%, 시간={time_labels[-1]}")
                else:
                    logger.warning(f"CPU 데이터 {i}에서 필수 키 누락: {list(data.keys())}")
            
            logger.info(f"CPU 차트 데이터 추출 완료 - CPU 값: {len(cpu_values)}개, 시간 라벨: {len(time_labels)}개")
            
            if not cpu_values:
                logger.warning("CPU 차트 생성 실패: CPU 값이 없음")
                return None
                
            # 차트 생성
            fig, ax = plt.subplots(figsize=(10, 6), dpi=100)
            
            # 한글 폰트 설정
            self._set_korean_font(fig)
            
            # 라인 차트
            ax.plot(range(len(cpu_values)), cpu_values, 'g-s', linewidth=2, markersize=4)
            
            # 제목과 라벨 설정
            chart_title = f'CPU 사용률 시간대별 추이 - {app_package}' if app_package != "Unknown Package" else 'CPU 사용률 시간대별 추이'
            ax.set_title(chart_title, fontsize=12, fontweight='bold', pad=15)
            ax.set_xlabel('시간대', fontsize=10)
            ax.set_ylabel('CPU (%)', fontsize=10)
            ax.set_ylim(0, max(100, max(cpu_values) * 1.1) if cpu_values else 100)
            ax.grid(True, alpha=0.3)
            
            # X축 라벨 설정
            if len(cpu_values) <= 10:
                ax.set_xticks(range(len(time_labels)))
                ax.set_xticklabels(time_labels, rotation=45, ha='right')
            else:
                # 데이터가 많으면 일부만 표시
                step = len(time_labels) // 8
                indices = range(0, len(time_labels), step)
                ax.set_xticks(indices)
                ax.set_xticklabels([time_labels[i] for i in indices], rotation=45, ha='right')
            
            # 통계 정보 추가
            if cpu_values:
                max_cpu = max(cpu_values)
                avg_cpu = sum(cpu_values) / len(cpu_values)
                ax.text(0.02, 0.98, f'최대: {max_cpu:.1f}%\n평균: {avg_cpu:.1f}%', 
                       transform=ax.transAxes, verticalalignment='top', fontsize=9,
                       bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.7))
            
            plt.tight_layout()
            
            return {
                'figure': fig,
                'base64_image': self._figure_to_base64(fig),
                'temp_file': self._save_figure_temp(fig, f'cpu_timeline_{app_package}'),
                'title': chart_title,
                'data': {
                    'max': max(cpu_values) if cpu_values else 0,
                    'avg': sum(cpu_values) / len(cpu_values) if cpu_values else 0,
                    'count': len(cpu_values)
                }
            }
            
        except Exception as e:
            logger.error(f"CPU 타임라인 차트 생성 오류: {e}")
            return None

    def create_performance_charts_from_data(self, performance_data: List[Dict], test_details: List[Dict], app_package: str = "Unknown Package") -> Dict[str, Any]:
        """
        테스트 완료 후 수집된 데이터로부터 성능 차트 생성 (시간대별)
        
        Args:
            performance_data: 성능 모니터링 데이터 (메모리, CPU)
            test_details: 테스트 상세 결과 데이터
            
        Returns:
            차트 정보 딕셔너리
        """
        try:
            logger.info(f"테스트 완료 데이터로 차트 생성 - 성능 데이터: {len(performance_data)}개, 상세 결과: {len(test_details)}개")
            
            # 데이터 디버깅 정보 출력
            if performance_data:
                logger.info(f"성능 데이터 샘플: {performance_data[0] if performance_data else 'None'}")
            if test_details:
                logger.info(f"상세 결과 샘플: {test_details[0] if test_details else 'None'}")
            
            # 성능 데이터가 있으면 시간대별 차트 우선 생성
            if performance_data:
                logger.info("성능 데이터를 사용한 시간대별 차트 생성")
                
                # 시간 정보 파싱 및 정렬
                time_data = []
                for data in performance_data:
                    try:
                        time_str = data.get('timestamp', '')
                        if time_str and len(time_str) >= 19:  # "2025-07-18 23:47:30" 최소 길이
                            time_obj = datetime.strptime(time_str[:19], "%Y-%m-%d %H:%M:%S")
                            time_data.append({
                                'time': time_obj,
                                'memory': data.get('memory_mb', 0),
                                'cpu': data.get('cpu_percent', 0),
                                'run': data.get('run', 1)
                            })
                    except Exception as e:
                        logger.warning(f"시간 파싱 실패: {data.get('timestamp', 'Unknown')}, {e}")
                        continue
                
                logger.info(f"시간 데이터 파싱 완료: {len(time_data)}개")
                
                if time_data:
                    # 시간 순으로 정렬
                    time_data.sort(key=lambda x: x['time'])
                    
                    # 실제 시간대별 차트 생성
                    timeline_charts = self._create_timeline_charts_from_time_data(time_data, app_package)
                    if timeline_charts:
                        logger.info(f"시간대별 차트 생성 성공: {len(timeline_charts)}개")
                        return timeline_charts
                    else:
                        logger.warning("시간대별 차트 생성 실패")
            
            # 시간대별 차트 생성 실패 시 기존 방식으로 fallback
            logger.info("기존 회차별 차트 생성 방식으로 fallback")
            
            if not performance_data and not test_details:
                logger.warning("차트 생성용 데이터가 없습니다")
                return {}
            
            # TestResultData 객체로 변환
            test_results = []
            
            # 상세 결과 데이터가 있으면 이를 기준으로 생성
            if test_details:
                for i, detail in enumerate(test_details):
                    try:
                        # 반복 번호 파싱
                        repeat_num = detail.get('repeat', i + 1)
                        if isinstance(repeat_num, str):
                            import re
                            repeat_match = re.search(r'(\d+)', str(repeat_num))
                            repeat_num = int(repeat_match.group(1)) if repeat_match else i + 1
                        
                        # 실행 시간 파싱 ("12초" -> 12.0)
                        exec_time = detail.get('time', 0.0)
                        if isinstance(exec_time, str):
                            import re
                            time_match = re.search(r'(\d+(?:\.\d+)?)', str(exec_time))
                            exec_time = float(time_match.group(1)) if time_match else 0.0
                        
                        # 메모리/CPU 피크 값 (상세 결과에서)
                        mem_peak = detail.get('mem_peak', 0.0)
                        if isinstance(mem_peak, str):
                            import re
                            mem_match = re.search(r'(\d+(?:\.\d+)?)', str(mem_peak))
                            mem_peak = float(mem_match.group(1)) if mem_match else 0.0
                        
                        cpu_peak = detail.get('cpu_peak', 0.0)
                        if isinstance(cpu_peak, str):
                            import re
                            cpu_match = re.search(r'(\d+(?:\.\d+)?)', str(cpu_peak))
                            cpu_peak = float(cpu_match.group(1)) if cpu_match else 0.0
                        
                        # 오류 수 파싱
                        def parse_count(value):
                            if isinstance(value, str):
                                import re
                                match = re.search(r'(\d+)', str(value))
                                return int(match.group(1)) if match else 0
                            return int(value) if value is not None else 0
                        
                        test_result = TestResultData(
                            repeat_number=int(repeat_num),
                            execution_time=float(exec_time),
                            event_count=parse_count(detail.get('events', 0)),
                            crash_count=parse_count(detail.get('crash', 0)),
                            anr_count=parse_count(detail.get('anr', 0)),
                            timeout_count=parse_count(detail.get('timeout', 0)),
                            memory_peak=float(mem_peak),
                            cpu_peak=float(cpu_peak),
                            timestamp=detail.get('timestamp'),
                            start_time=detail.get('start_time')
                        )
                        
                        test_results.append(test_result)
                        
                    except Exception as e:
                        logger.warning(f"테스트 결과 데이터 변환 실패 (항목 {i}): {e}")
                        continue
            
            if not test_results:
                logger.warning("변환 가능한 테스트 결과 데이터가 없습니다")
                return {}
            
            # 메모리와 CPU 차트만 생성 (GUI용)
            charts = {}
            
            if any(r.memory_peak > 0 for r in test_results):
                charts['memory'] = self._create_memory_chart_from_testdata(test_results, app_package)
                logger.info("메모리 차트 생성 완료")
            
            if any(r.cpu_peak > 0 for r in test_results):
                charts['cpu'] = self._create_cpu_chart_from_testdata(test_results, app_package)
                logger.info("CPU 차트 생성 완료")
            
            return charts
            
        except Exception as e:
            logger.error(f"테스트 완료 차트 생성 실패: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {}

    def _create_memory_timeline_chart_simple(self, test_results, app_package="Unknown Package"):
        """간단한 메모리 시간대별 차트 생성"""
        try:
            # 데이터 추출
            memory_usage = []
            times = []
            base_time = None  # base_time 초기화
            
            for i, result in enumerate(test_results):
                if hasattr(result, 'performance_data') and result.performance_data:
                    # start_time이 있으면 사용, 없으면 인덱스 기반 시간 계산
                    if hasattr(result, 'start_time') and result.start_time:
                        try:
                            # start_time을 파싱하여 분 단위로 변환
                            start_time = datetime.strptime(result.start_time, "%Y-%m-%d %H:%M:%S")
                            if i == 0:
                                base_time = start_time
                            if base_time:
                                elapsed_minutes = (start_time - base_time).total_seconds() / 60
                                times.append(elapsed_minutes)
                            else:
                                times.append(i * 2)  # 2분 간격으로 가정
                        except:
                            # 파싱 실패시 인덱스 기반
                            times.append(i * 2)  # 2분 간격으로 가정
                    else:
                        times.append(i * 2)  # 2분 간격으로 가정
                    
                    mem_data = result.performance_data.get('memory', [])
                    if mem_data:
                        memory_usage.append(sum(mem_data) / len(mem_data))  # 평균값 사용
                    else:
                        memory_usage.append(0)
            
            if not memory_usage:
                return None
            
            # 차트 생성
            fig, ax = plt.subplots(figsize=(8, 3.5))
            
            # 데이터 플롯 - 인덱스 기반으로 변경
            ax.plot(range(len(memory_usage)), memory_usage, 'b-', linewidth=2, marker='o', markersize=3)
            
            # 차트 스타일링
            app_name = app_package if app_package != "Unknown Package" else "앱"
            ax.set_title(f'{app_name} 메모리 사용량 시간대별 추이', fontsize=10, fontweight='bold')
            ax.set_ylabel('메모리 (MB)', fontsize=9)
            ax.set_xlabel('테스트 순서', fontsize=10)
            ax.grid(True, alpha=0.3)
            
            # 통계 정보
            max_memory = max(memory_usage)
            min_memory = min(memory_usage)
            avg_memory = sum(memory_usage) / len(memory_usage)
            
            # X축 라벨 설정
            if len(memory_usage) <= 10:
                ax.set_xticks(range(len(memory_usage)))
                ax.set_xticklabels([f"테스트{i+1}" for i in range(len(memory_usage))])
            else:
                # 데이터가 많으면 일부만 표시
                step = len(memory_usage) // 8
                indices = range(0, len(memory_usage), step)
                ax.set_xticks(indices)
                ax.set_xticklabels([f"테스트{i+1}" for i in indices])
        
            plt.tight_layout()
            
            # figure 저장
            self.figures['memory_timeline'] = fig
            
            return {
                'figure': fig,
                'base64_image': self._figure_to_base64(fig),
                'temp_file': self._save_figure_temp(fig, 'memory_timeline_chart'),
                'title': '메모리 사용량 시간대별 추이',
                'data': {
                    'max': max_memory,
                    'min': min_memory,
                    'avg': avg_memory,
                    'count': len(memory_usage),
                    'duration_minutes': max(times) if times else 0
                }
            }
            
        except Exception as e:
            print(f"Memory timeline chart creation error: {e}")
            return None

    def _create_cpu_timeline_chart_simple(self, test_results, app_package="Unknown Package"):
        """간단한 CPU 시간대별 차트 생성"""
        try:
            # 데이터 추출
            cpu_usage = []
            times = []
            base_time = None  # base_time 초기화
            
            for i, result in enumerate(test_results):
                if hasattr(result, 'performance_data') and result.performance_data:
                    # start_time이 있으면 사용, 없으면 인덱스 기반 시간 계산
                    if hasattr(result, 'start_time') and result.start_time:
                        try:
                            # start_time을 파싱하여 분 단위로 변환
                            start_time = datetime.strptime(result.start_time, "%Y-%m-%d %H:%M:%S")
                            if i == 0:
                                base_time = start_time
                            if base_time:
                                elapsed_minutes = (start_time - base_time).total_seconds() / 60
                                times.append(elapsed_minutes)
                            else:
                                times.append(i * 2)  # 2분 간격으로 가정
                        except:
                            # 파싱 실패시 인덱스 기반
                            times.append(i * 2)  # 2분 간격으로 가정
                    else:
                        times.append(i * 2)  # 2분 간격으로 가정
                    
                    cpu_data = result.performance_data.get('cpu', [])
                    if cpu_data:
                        cpu_usage.append(sum(cpu_data) / len(cpu_data))  # 평균값 사용
                    else:
                        cpu_usage.append(0)
            
            if not cpu_usage:
                return None
            
            # 차트 생성
            fig, ax = plt.subplots(figsize=(8, 3.5))
            
            # 데이터 플롯 - 인덱스 기반으로 변경
            ax.plot(range(len(cpu_usage)), cpu_usage, 'g-', linewidth=2, marker='s', markersize=3)
            
            # 차트 스타일링
            app_name = app_package if app_package != "Unknown Package" else "앱"
            ax.set_title(f'{app_name} CPU 사용률 시간대별 추이', fontsize=10, fontweight='bold')
            ax.set_ylabel('CPU (%)', fontsize=9)
            ax.set_xlabel('테스트 순서', fontsize=10)
            ax.grid(True, alpha=0.3)
            ax.set_ylim(0, 100)
            
            # 통계 정보
            max_cpu = max(cpu_usage)
            min_cpu = min(cpu_usage)
            avg_cpu = sum(cpu_usage) / len(cpu_usage)
            
            # X축 라벨 설정
            if len(cpu_usage) <= 10:
                ax.set_xticks(range(len(cpu_usage)))
                ax.set_xticklabels([f"테스트{i+1}" for i in range(len(cpu_usage))])
            else:
                # 데이터가 많으면 일부만 표시
                step = len(cpu_usage) // 8
                indices = range(0, len(cpu_usage), step)
                ax.set_xticks(indices)
                ax.set_xticklabels([f"테스트{i+1}" for i in indices])
        
            plt.tight_layout()
            
            # figure 저장
            self.figures['cpu_timeline'] = fig
            
            return {
                'figure': fig,
                'base64_image': self._figure_to_base64(fig),
                'temp_file': self._save_figure_temp(fig, 'cpu_timeline_chart'),
                'title': 'CPU 사용률 시간대별 추이',
                'data': {
                    'max': max(cpu_usage),
                    'min': min(cpu_usage), 
                    'avg': avg_cpu,
                    'count': len(cpu_usage),
                    'duration_minutes': max(times) if times else 0
                }
            }
            
        except Exception as e:
            print(f"CPU timeline chart creation error: {e}")
            return None

    def _figure_to_base64(self, fig):
        """Figure를 base64 문자열로 변환"""
        try:
            buffer = io.BytesIO()
            fig.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.getvalue()).decode()
            buffer.close()
            return image_base64
        except Exception as e:
            print(f"Base64 conversion error: {e}")
            return None
    
    def _save_figure_temp(self, fig, prefix='chart'):
        """Figure를 임시 파일로 저장 (시간 형식 HH:MM으로 통일)"""
        try:
            # prefix에서 패키지명 추출 시도
            safe_prefix = prefix
            if prefix and 'simple_memory_' in prefix:
                # simple_memory_com.example.app -> simple_memory_com_example_app
                safe_prefix = prefix.replace('.', '_')
            elif prefix and 'simple_cpu_' in prefix:
                # simple_cpu_com.example.app -> simple_cpu_com_example_app  
                safe_prefix = prefix.replace('.', '_')
            else:
                safe_prefix = prefix.replace('.', '_') if '.' in prefix else prefix
            
            # 파일명에 시간 정보 추가 (HH:MM 형식으로)
            current_time = datetime.now().strftime("%H%M")  # HHMM 형식 (콜론 제거)
            current_date = datetime.now().strftime("%Y%m%d")
            
            temp_file = tempfile.NamedTemporaryFile(
                suffix='.png', 
                prefix=f'{safe_prefix}_{current_date}_{current_time}_',
                delete=False
            )
            fig.savefig(temp_file.name, format='png', dpi=100, bbox_inches='tight')
            return temp_file.name
        except Exception as e:
            print(f"Temp file save error: {e}")
            return None
    
    def save_chart(self, chart_data, filename, save_dir='charts'):
        """차트를 파일로 저장"""
        try:
            if not chart_data or 'figure' not in chart_data:
                return None
                
            # 저장 디렉토리 생성
            os.makedirs(save_dir, exist_ok=True)
            
            # 파일 경로 생성
            filepath = os.path.join(save_dir, f"{filename}.png")
            
            # 차트 저장
            chart_data['figure'].savefig(filepath, format='png', dpi=150, bbox_inches='tight')
            
            return filepath
            
        except Exception as e:
            print(f"Chart save error: {e}")
            return None

    def _create_memory_chart_from_testdata(self, test_results, app_package="Unknown Package"):
        """TestResultData를 사용한 메모리 차트 생성"""
        try:
            if not test_results:
                return None
                
            memory_data = [r.memory_peak for r in test_results]
            if all(m == 0 for m in memory_data):
                return None
                
            return self._create_memory_chart(test_results, app_package)
        except Exception as e:
            logger.error(f"메모리 차트 생성 실패: {e}")
            return None

    def _create_cpu_chart_from_testdata(self, test_results, app_package="Unknown Package"):
        """TestResultData를 사용한 CPU 차트 생성"""
        try:
            if not test_results:
                return None
                
            cpu_data = [r.cpu_peak for r in test_results]
            if all(c == 0 for c in cpu_data):
                return None
                
            return self._create_cpu_chart(test_results, app_package)
        except Exception as e:
            logger.error(f"CPU 차트 생성 실패: {e}")
            return None

    def _create_error_chart(self, test_results, app_package="Unknown Package"):
        """오류 발생 현황 차트 생성"""
        try:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), dpi=100)
            
            # 한글 폰트 적용
            self._set_korean_font(fig)
            
            # 1. 오류 유형별 총 발생 횟수 (파이 차트)
            crash_total = sum(int(r.crash_count) if hasattr(r, 'crash_count') else 0 for r in test_results)
            anr_total = sum(int(r.anr_count) if hasattr(r, 'anr_count') else 0 for r in test_results)
            timeout_total = sum(int(r.timeout_count) if hasattr(r, 'timeout_count') else 0 for r in test_results)
            
            error_labels = ['Crash', 'ANR', 'Timeout']
            error_counts = [crash_total, anr_total, timeout_total]
            colors = ['#E74C3C', '#F39C12', '#8E44AD']
            
            # 0이 아닌 값들만 표시
            filtered_data = [(label, count, color) for label, count, color in zip(error_labels, error_counts, colors) if count > 0]
            
            if filtered_data:
                labels, counts, colors = zip(*filtered_data)
                ax1.pie(counts, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
                ax1.set_title('오류 유형별 발생 비율', fontsize=10, fontweight='bold')
            else:
                ax1.text(0.5, 0.5, '오류 발생 없음', transform=ax1.transAxes, 
                        ha='center', va='center', fontsize=12, color='green')
                ax1.set_title('오류 발생 현황', fontsize=10, fontweight='bold')
            
            # 2. 테스트 회차별 오류 발생 추이
            time_labels = [f"회차 {i+1}" for i in range(len(test_results))]
            x_positions = range(len(test_results))
            crashes = [getattr(r, 'crash_count', 0) for r in test_results]
            anrs = [getattr(r, 'anr_count', 0) for r in test_results]
            timeouts = [getattr(r, 'timeout_count', 0) for r in test_results]
            
            width = 0.6
            ax2.bar(x_positions, crashes, width, label='Crash', color='#E74C3C')
            ax2.bar(x_positions, anrs, width, bottom=crashes, label='ANR', color='#F39C12')
            ax2.bar(x_positions, timeouts, width, bottom=[c+a for c,a in zip(crashes, anrs)], 
                    label='Timeout', color='#8E44AD')
            
            ax2.set_title('테스트 회차별 오류 발생', fontsize=10, fontweight='bold')
            ax2.set_xlabel('테스트 회차', fontsize=9)
            ax2.set_ylabel('오류 발생 횟수', fontsize=9)
            ax2.legend(fontsize=8)
            ax2.grid(True, alpha=0.3, axis='y')
            
            if len(test_results) > 0:
                ax2.set_xticks(x_positions)
                ax2.set_xticklabels(time_labels, rotation=45, ha='right')
            
            # 전체 제목 설정
            fig.suptitle(f'오류 발생 현황 - {app_package}', fontsize=12, fontweight='bold')
            
            plt.tight_layout()
            
            return {
                'figure': fig,
                'base64_image': self._figure_to_base64(fig),
                'temp_file': self._save_figure_temp(fig, f'error_chart_{app_package}'),
                'title': f'오류 발생 현황 - {app_package}',
                'data': {
                    'crash_total': crash_total,
                    'anr_total': anr_total,
                    'timeout_total': timeout_total,
                    'total_errors': crash_total + anr_total + timeout_total
                }
            }
            
        except Exception as e:
            logger.error(f"오류 차트 생성 실패: {e}")
            return None

    def _create_execution_time_chart(self, test_results, app_package="Unknown Package"):
        """실행 시간 추이 차트 생성"""
        try:
            fig, ax = plt.subplots(figsize=(10, 6), dpi=100)
            
            # 한글 폰트 적용
            self._set_korean_font(fig)
            
            time_labels = [f"회차 {i+1}" for i in range(len(test_results))]
            exec_times = [getattr(r, 'execution_time', 0) for r in test_results]
            
            # 바 차트
            x_positions = range(len(test_results))
            bars = ax.bar(x_positions, exec_times, color='#27AE60', alpha=0.7, edgecolor='darkgreen')
            
            # 평균선 추가
            if exec_times:
                avg_time = float(np.mean(exec_times))
                ax.axhline(y=avg_time, color='red', linestyle='--', alpha=0.7, 
                          label=f'평균: {avg_time:.1f}초')
            
            ax.set_title(f'실행 시간 추이 - {app_package}', fontsize=12, fontweight='bold', pad=15)
            ax.set_xlabel('테스트 회차', fontsize=10)
            ax.set_ylabel('실행 시간 (초)', fontsize=10)
            ax.grid(True, alpha=0.3, axis='y')
            if exec_times:
                ax.legend(fontsize=9)
            
            if len(test_results) > 0:
                ax.set_xticks(x_positions)
                ax.set_xticklabels(time_labels, rotation=45, ha='right')
            
            # 막대 위에 값 표시
            for bar, time in zip(bars, exec_times):
                height = bar.get_height()
                if height > 0:
                    ax.text(bar.get_x() + bar.get_width()/2., height + max(exec_times)*0.01,
                           f'{time:.1f}s', ha='center', va='bottom', fontsize=7)
            
            plt.tight_layout(pad=1.0)
            
            return {
                'figure': fig,
                'base64_image': self._figure_to_base64(fig),
                'temp_file': self._save_figure_temp(fig, f'execution_time_chart_{app_package}'),
                'title': f'실행 시간 추이 - {app_package}',
                'data': {
                    'max': max(exec_times) if exec_times else 0,
                    'min': min(exec_times) if exec_times else 0,
                    'avg': np.mean(exec_times) if exec_times else 0,
                    'total': sum(exec_times) if exec_times else 0
                }
            }
            
        except Exception as e:
            logger.error(f"실행 시간 차트 생성 실패: {e}")
            return None

    def create_gui_canvas(self, parent, chart_data):
        """GUI용 matplotlib 캔버스 생성"""
        if not MATPLOTLIB_AVAILABLE:
            logger.error("matplotlib을 사용할 수 없습니다")
            return None
            
        if 'figure' not in chart_data:
            logger.error(f"차트 데이터에 'figure' 키가 없습니다. 사용 가능한 키: {list(chart_data.keys())}")
            return None
        
        try:
            figure = chart_data['figure']
            logger.info(f"GUI 캔버스 생성 중 - figure 타입: {type(figure)}")
            canvas = FigureCanvasTkAgg(figure, parent)
            logger.info("✅ GUI 캔버스 생성 성공")
            return canvas
        except Exception as e:
            logger.error(f"❌ GUI 캔버스 생성 실패: {e}")
            import traceback
            logger.error(f"상세 오류: {traceback.format_exc()}")
            return None

    def create_popup_safe_figure(self, chart_data):
        """팝업 윈도우용 matplotlib figure 생성"""
        if not MATPLOTLIB_AVAILABLE:
            logger.error("matplotlib을 사용할 수 없습니다")
            return None
            
        try:
            if 'figure' in chart_data:
                # 기존 figure 반환 (TkAgg 백엔드 호환)
                return chart_data['figure']
            else:
                logger.error("차트 데이터에 figure가 없습니다")
                return None
                
        except Exception as e:
            logger.error(f"팝업용 figure 생성 실패: {e}")
            return None

    def _set_korean_font(self, fig):
        """한글 폰트 설정"""
        try:
            import matplotlib.font_manager as fm
            
            # 프로젝트 내 폰트 경로
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            font_dir = os.path.join(base_dir, 'fonts')
            
            # Noto Sans KR 폰트 파일들
            font_files = [
                'NotoSansKR_Regular.otf',
                'NotoSansKR_Medium.otf', 
                'NotoSansKR_Bold.otf'
            ]
            
            font_registered = False
            font_name = None
            
            for font_file in font_files:
                font_path = os.path.join(font_dir, font_file)
                if os.path.exists(font_path):
                    try:
                        # 폰트를 matplotlib에 등록
                        fm.fontManager.addfont(font_path)
                        
                        # FontProperties로 폰트 이름 확인
                        font_props = fm.FontProperties(fname=font_path)
                        font_name = font_props.get_name()
                        
                        font_registered = True
                        logger.debug(f"폰트 등록 성공: {font_file} -> {font_name}")
                        break  # 첫 번째 성공한 폰트 사용
                        
                    except Exception as e:
                        logger.warning(f"폰트 등록 실패 {font_file}: {e}")
            
            if font_registered and font_name:
                # 폰트 캐시 새로고침
                try:
                    # _rebuild는 private method이므로 hasattr로 확인 후 사용
                    if hasattr(fm.fontManager, '_rebuild'):
                        fm.fontManager._rebuild()  # type: ignore
                except:
                    pass
                
                # 등록된 폰트 이름을 기본 폰트로 설정
                plt.rcParams['font.family'] = [font_name, 'sans-serif']
                plt.rcParams['font.sans-serif'] = [font_name] + plt.rcParams.get('font.sans-serif', [])
                plt.rcParams['axes.unicode_minus'] = False
                
                logger.info(f"✅ 한글 폰트 설정 완료: {font_name}")
                
                # Figure의 모든 텍스트 요소에 폰트 적용
                if fig:
                    for ax in fig.get_axes():
                        # 제목
                        ax.title.set_fontfamily(font_name)
                        # 축 라벨
                        ax.xaxis.label.set_fontfamily(font_name)
                        ax.yaxis.label.set_fontfamily(font_name)
                        # 틱 라벨
                        for label in ax.get_xticklabels():
                            label.set_fontfamily(font_name)
                        for label in ax.get_yticklabels():
                            label.set_fontfamily(font_name)
                        # 범례
                        legend = ax.get_legend()
                        if legend:
                            for text in legend.get_texts():
                                text.set_fontfamily(font_name)
                
            else:
                # 폴백: 시스템 폰트
                logger.warning("⚠️ Noto Sans KR 폰트 등록 실패, 시스템 폰트 사용")
                if os.name == 'nt':  # Windows
                    fallback_fonts = ['Malgun Gothic', 'Microsoft YaHei', 'NanumGothic']
                    for fb_font in fallback_fonts:
                        try:
                            plt.rcParams['font.family'] = [fb_font, 'sans-serif']
                            logger.info(f"시스템 폰트 설정: {fb_font}")
                            break
                        except:
                            continue
                else:
                    plt.rcParams['font.family'] = ['DejaVu Sans', 'sans-serif']
                    
                plt.rcParams['axes.unicode_minus'] = False
                
        except Exception as e:
            logger.error(f"❌ 한글 폰트 설정 실패: {e}")
            # 최종 폴백
            try:
                plt.rcParams['font.family'] = ['sans-serif']
                plt.rcParams['axes.unicode_minus'] = False
            except:
                pass
    
    def cleanup(self):
        """리소스 정리"""
        try:
            for fig in self.figures.values():
                plt.close(fig)
            self.figures.clear()
        except Exception as e:
            print(f"Cleanup error: {e}")
    
    def _create_simple_memory_chart(self, memory_values, timestamps, app_package="Unknown Package"):
        """간단한 메모리 차트 생성 (Old 버전 스타일)"""
        try:
            # 스레드 안전 백엔드 설정
            setup_matplotlib_backend()
            
            logger.info(f"간단한 메모리 차트 생성 시작 - {len(memory_values)}개 데이터")
            
            # 차트 생성 (팝업용 더 작은 크기)
            fig, ax = plt.subplots(figsize=(7, 3.5), dpi=100)
            
            # 한글 폰트 설정
            self._set_korean_font(fig)
            
            # 데이터 범위 생성
            x_values = range(len(memory_values))
            
            # 라인 차트 그리기
            ax.plot(x_values, memory_values, '-o', linewidth=2, markersize=3, 
                   color='#2E86C1', label='메모리 사용량')
            
            # 평균선 추가
            if memory_values:
                avg_memory = sum(memory_values) / len(memory_values)
                ax.axhline(y=avg_memory, color='red', linestyle='--', alpha=0.7, 
                          label=f'평균: {avg_memory:.1f}MB')
            
            # 제목과 라벨 설정 (패키지명 포함)
            chart_title = f'메모리 사용량 - {app_package}'
            ax.set_title(chart_title, fontsize=10, fontweight='bold', pad=8)
            ax.set_xlabel('시간', fontsize=8)
            ax.set_ylabel('메모리 (MB)', fontsize=8)
            ax.grid(True, alpha=0.3)
            ax.legend(fontsize=7)
            
            # X축 라벨 설정 (실제 시간 표시) - 메모리 차트
            if timestamps and len(timestamps) > 0:
                if len(timestamps) <= 10:
                    ax.set_xticks(x_values)
                    # timestamps는 이미 HH:MM 형식으로 변환됨
                    ax.set_xticklabels(timestamps, rotation=0, fontsize=8)
                else:
                    # 데이터가 많으면 일부만 표시
                    step = max(1, len(x_values) // 6)
                    indices = list(range(0, len(x_values), step))
                    ax.set_xticks(indices)
                    selected_timestamps = [timestamps[i] for i in indices if i < len(timestamps)]
                    ax.set_xticklabels(selected_timestamps, rotation=45, fontsize=7)
            else:
                # 타임스탬프가 없으면 기본 숫자 표시
                logger.warning("타임스탬프가 없어서 순서 번호로 표시합니다")
                ax.set_xticks(x_values)
                ax.set_xticklabels([f"{i+1}" for i in x_values], fontsize=8)
            
            # 여백 조정 (팝업용 더 타이트하게)
            plt.tight_layout(pad=1.0)
            plt.subplots_adjust(bottom=0.15, top=0.90, left=0.12, right=0.95)
            
            # 통계 계산
            max_mem = max(memory_values) if memory_values else 0
            min_mem = min(memory_values) if memory_values else 0
            avg_mem = sum(memory_values) / len(memory_values) if memory_values else 0
            
            chart_result = {
                'figure': fig,
                'base64_image': self._figure_to_base64(fig),
                'temp_file': self._save_figure_temp(fig, f'simple_memory_{app_package}'),
                'title': chart_title,
                'data': {
                    'max': max_mem,
                    'min': min_mem,
                    'avg': avg_mem,
                    'count': len(memory_values)
                }
            }
            
            logger.info(f"간단한 메모리 차트 생성 성공 - 최대: {max_mem:.1f}MB, 평균: {avg_mem:.1f}MB")
            return chart_result
            
        except Exception as e:
            logger.error(f"간단한 메모리 차트 생성 오류: {e}")
            import traceback
            logger.error(f"상세 오류: {traceback.format_exc()}")
            return None
    
    def _create_simple_cpu_chart(self, cpu_values, timestamps, app_package="Unknown Package"):
        """간단한 CPU 차트 생성 (Old 버전 스타일)"""
        try:
            # 스레드 안전 백엔드 설정
            setup_matplotlib_backend()
            
            logger.info(f"간단한 CPU 차트 생성 시작 - {len(cpu_values)}개 데이터")
            
            # 차트 생성 (팝업용 더 작은 크기)
            fig, ax = plt.subplots(figsize=(7, 3.5), dpi=100)
            
            # 한글 폰트 설정
            self._set_korean_font(fig)
            
            # 데이터 범위 생성
            x_values = range(len(cpu_values))
            
            # 라인 차트 그리기
            ax.plot(x_values, cpu_values, '-s', linewidth=2, markersize=3, 
                   color='#E74C3C', label='CPU 사용률')
            
            # 평균선 추가
            if cpu_values:
                avg_cpu = sum(cpu_values) / len(cpu_values)
                ax.axhline(y=avg_cpu, color='orange', linestyle='--', alpha=0.7, 
                          label=f'평균: {avg_cpu:.1f}%')
            
            # 제목과 라벨 설정 (패키지명 포함)
            chart_title = f'CPU 사용률 - {app_package}'
            ax.set_title(chart_title, fontsize=10, fontweight='bold', pad=8)
            ax.set_xlabel('시간', fontsize=8)
            ax.set_ylabel('CPU (%)', fontsize=8)
            ax.grid(True, alpha=0.3)
            ax.legend(fontsize=7)
            
            # Y축 상한 설정
            max_cpu = max(cpu_values) if cpu_values else 100
            y_max = max(100, max_cpu * 1.1)
            ax.set_ylim(0, y_max)
            
            # X축 라벨 설정 (실제 시간 표시) - CPU 차트
            if timestamps and len(timestamps) > 0:
                if len(timestamps) <= 10:
                    ax.set_xticks(x_values)
                    # timestamps는 이미 HH:MM 형식으로 변환됨
                    ax.set_xticklabels(timestamps, rotation=0, fontsize=8)
                else:
                    # 데이터가 많으면 일부만 표시
                    step = max(1, len(x_values) // 6)
                    indices = list(range(0, len(x_values), step))
                    ax.set_xticks(indices)
                    selected_timestamps = [timestamps[i] for i in indices if i < len(timestamps)]
                    ax.set_xticklabels(selected_timestamps, rotation=45, fontsize=7)
            else:
                # 타임스탬프가 없으면 기본 숫자 표시
                logger.warning("타임스탬프가 없어서 순서 번호로 표시합니다")
                ax.set_xticks(x_values)
                ax.set_xticklabels([f"{i+1}" for i in x_values], fontsize=8)
            
            # 여백 조정 (팝업용 더 타이트하게)
            plt.tight_layout(pad=1.0)
            plt.subplots_adjust(bottom=0.15, top=0.90, left=0.12, right=0.95)
            
            # 통계 계산
            max_cpu_val = max(cpu_values) if cpu_values else 0
            min_cpu_val = min(cpu_values) if cpu_values else 0
            avg_cpu_val = sum(cpu_values) / len(cpu_values) if cpu_values else 0
            
            chart_result = {
                'figure': fig,
                'base64_image': self._figure_to_base64(fig),
                'temp_file': self._save_figure_temp(fig, f'simple_cpu_{app_package}'),
                'title': chart_title,
                'data': {
                    'max': max_cpu_val,
                    'min': min_cpu_val,
                    'avg': avg_cpu_val,
                    'count': len(cpu_values)
                }
            }
            
            logger.info(f"간단한 CPU 차트 생성 성공 - 최대: {max_cpu_val:.1f}%, 평균: {avg_cpu_val:.1f}%")
            return chart_result
            
        except Exception as e:
            logger.error(f"간단한 CPU 차트 생성 오류: {e}")
            import traceback
            logger.error(f"상세 오류: {traceback.format_exc()}")
            return None
    
    def _format_time_for_chart(self, timestamp):
        """시간 정보를 차트용 HH:MM 형식으로 변환"""
        try:
            if isinstance(timestamp, str):
                # "2025-07-28 11:32:13" 형태에서 시간 부분 추출
                if " " in timestamp and len(timestamp) >= 19:
                    time_part = timestamp.split(" ")[1]  # "11:32:13" 부분
                    if ":" in time_part:
                        time_parts = time_part.split(":")
                        if len(time_parts) >= 2:
                            return f"{time_parts[0]}:{time_parts[1]}"  # HH:MM 형식
                # "11:32:13" 형태에서 HH:MM 추출
                elif ":" in timestamp:
                    time_parts = timestamp.split(":")
                    if len(time_parts) >= 2:
                        return f"{time_parts[0]}:{time_parts[1]}"  # HH:MM 형식
                # 숫자로만 이루어진 경우 순서번호로 처리
                elif timestamp.isdigit():
                    return timestamp
                # "데이터1" 형태면 그대로 반환
                else:
                    return timestamp
            elif hasattr(timestamp, 'strftime'):
                # datetime 객체인 경우
                return timestamp.strftime("%H:%M")
            else:
                return str(timestamp)
        except Exception as e:
            logger.warning(f"시간 형식 변환 실패: {timestamp} -> {e}")
            return str(timestamp)
