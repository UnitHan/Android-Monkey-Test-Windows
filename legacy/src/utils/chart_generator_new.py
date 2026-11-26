import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter
import numpy as np
import seaborn as sns
import base64
import io
import tempfile
import os
from datetime import datetime

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

    def _create_memory_timeline_chart_simple(self, test_results, app_package="Unknown Package"):
        """간단한 메모리 시간대별 차트 생성"""
        try:
            # 데이터 추출
            memory_usage = []
            times = []
            
            for i, result in enumerate(test_results):
                if hasattr(result, 'performance_data') and result.performance_data:
                    # start_time이 있으면 사용, 없으면 인덱스 기반 시간 계산
                    if hasattr(result, 'start_time') and result.start_time:
                        try:
                            # start_time을 파싱하여 분 단위로 변환
                            start_time = datetime.strptime(result.start_time, "%Y-%m-%d %H:%M:%S")
                            if i == 0:
                                base_time = start_time
                            elapsed_minutes = (start_time - base_time).total_seconds() / 60
                            times.append(elapsed_minutes)
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
            
            # 데이터 플롯
            ax.plot(times, memory_usage, 'b-', linewidth=2, marker='o', markersize=3)
            
            # 차트 스타일링
            app_name = app_package if app_package != "Unknown Package" else "앱"
            ax.set_title(f'{app_name} 메모리 사용량 시간대별 추이', fontsize=10, fontweight='bold')
            ax.set_ylabel('메모리 (MB)', fontsize=9)
            ax.grid(True, alpha=0.3)
            
            # 통계 정보
            max_memory = max(memory_usage)
            min_memory = min(memory_usage)
            avg_memory = sum(memory_usage) / len(memory_usage)
            
            # X축 시간 포맷 설정
            if times and max(times) > 60:
                # 1시간 이상인 경우 시:분 형식
                ax.set_xlabel('경과 시간 (시:분)', fontsize=10)
                ax.xaxis.set_major_formatter(FuncFormatter(lambda x, p: f'{int(x//60)}:{int(x%60):02d}'))
            else:
                # 1시간 미만인 경우 분:초 형식
                ax.set_xlabel('경과 시간 (분)', fontsize=10)
                ax.xaxis.set_major_formatter(FuncFormatter(lambda x, p: f'{int(x)}분'))
        
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
            
            for i, result in enumerate(test_results):
                if hasattr(result, 'performance_data') and result.performance_data:
                    # start_time이 있으면 사용, 없으면 인덱스 기반 시간 계산
                    if hasattr(result, 'start_time') and result.start_time:
                        try:
                            # start_time을 파싱하여 분 단위로 변환
                            start_time = datetime.strptime(result.start_time, "%Y-%m-%d %H:%M:%S")
                            if i == 0:
                                base_time = start_time
                            elapsed_minutes = (start_time - base_time).total_seconds() / 60
                            times.append(elapsed_minutes)
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
            
            # 데이터 플롯
            ax.plot(times, cpu_usage, 'g-', linewidth=2, marker='s', markersize=3)
            
            # 차트 스타일링
            app_name = app_package if app_package != "Unknown Package" else "앱"
            ax.set_title(f'{app_name} CPU 사용률 시간대별 추이', fontsize=10, fontweight='bold')
            ax.set_ylabel('CPU (%)', fontsize=9)
            ax.grid(True, alpha=0.3)
            ax.set_ylim(0, 100)
            
            # 통계 정보
            max_cpu = max(cpu_usage)
            min_cpu = min(cpu_usage)
            avg_cpu = sum(cpu_usage) / len(cpu_usage)
            
            # X축 시간 포맷 설정
            if times and max(times) > 60:
                # 1시간 이상인 경우 시:분 형식
                ax.set_xlabel('경과 시간 (시:분)', fontsize=10)
                ax.xaxis.set_major_formatter(FuncFormatter(lambda x, p: f'{int(x//60)}:{int(x%60):02d}'))
            else:
                # 1시간 미만인 경우 분:초 형식
                ax.set_xlabel('경과 시간 (분)', fontsize=10)
                ax.xaxis.set_major_formatter(FuncFormatter(lambda x, p: f'{int(x)}분'))
        
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
        """Figure를 임시 파일로 저장"""
        try:
            temp_file = tempfile.NamedTemporaryFile(
                suffix='.png', 
                prefix=f'{prefix}_',
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
    
    def cleanup(self):
        """리소스 정리"""
        try:
            for fig in self.figures.values():
                plt.close(fig)
            self.figures.clear()
        except Exception as e:
            print(f"Cleanup error: {e}")
