#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
성능 그래프 팝업 윈도우
테스트 완료 후 메모리 사용량과 CPU 사용량 그래프를 팝업으로 표시
"""

import tkinter as tk
from tkinter import ttk, filedialog
from src.utils.gui_utils import messagebox
import logging
from typing import Dict, Any, Optional
import os
from datetime import datetime

# 폰트 매니저 import
from src.utils.font_manager import get_font_manager

# matplotlib 스레딩 안전성을 위한 설정
try:
    import matplotlib
    matplotlib.use('TkAgg')  # 팝업 윈도우용으로는 TkAgg 사용
    matplotlib.rcParams['figure.max_open_warning'] = 0
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    import io
    from PIL import Image, ImageTk
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

logger = logging.getLogger(__name__)

class PerformanceGraphPopup:
    """성능 그래프 팝업 윈도우 클래스"""
    
    def __init__(self, parent: tk.Tk, chart_data: Dict[str, Any], test_info: Dict[str, Any]):
        """
        팝업 윈도우 초기화
        
        Args:
            parent: 부모 윈도우
            chart_data: 차트 데이터 (memory, cpu 차트 정보)
            test_info: 테스트 정보 (패키지명, 시간 등)
        """
        self.parent = parent
        self.chart_data = chart_data
        self.test_info = test_info
        
        # 한글 폰트 설정
        korean_font_family = get_font_manager().get_font_family()
        self.gui_font_title = (korean_font_family or "맑은 고딕", 14, "bold") if korean_font_family else ("맑은 고딕", 14, "bold")
        self.gui_font_normal = (korean_font_family or "맑은 고딕", 10) if korean_font_family else ("맑은 고딕", 10)
        self.gui_font_small = (korean_font_family or "맑은 고딕", 9) if korean_font_family else ("맑은 고딕", 9)
        self.gui_font_large = (korean_font_family or "맑은 고딕", 12) if korean_font_family else ("맑은 고딕", 12)
        
        # 팝업 윈도우 생성
        self.popup = tk.Toplevel(parent)
        self.popup.title("성능 그래프 보기")
        self.popup.geometry("1000x700")
        self.popup.resizable(True, True)
        
        # 아이콘 설정 (부모와 동일)
        try:
            # 부모 윈도우의 아이콘 경로 사용
            import os
            icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "icon.ico")
            if os.path.exists(icon_path):
                self.popup.iconbitmap(icon_path)
                logger.info(f"팝업 아이콘 설정 성공: {icon_path}")
            else:
                logger.warning(f"아이콘 파일을 찾을 수 없음: {icon_path}")
        except Exception as e:
            logger.warning(f"팝업 아이콘 설정 실패: {e}")
            
        # 모달 윈도우로 설정
        self.popup.transient(parent)
        self.popup.grab_set()
        
        # 창 위치를 부모 윈도우 중앙에 설정
        self._center_window()
        
        # UI 구성
        self._create_widgets()
        
        # 차트 표시
        self._display_charts()
        
        logger.info("성능 그래프 팝업 윈도우 생성 완료")
    
    def _center_window(self):
        """팝업 윈도우를 부모 윈도우 중앙에 위치시킴"""
        try:
            # 부모 윈도우 위치와 크기 가져오기
            parent_x = self.parent.winfo_x()
            parent_y = self.parent.winfo_y()
            parent_width = self.parent.winfo_width()
            parent_height = self.parent.winfo_height()
            
            # 팝업 윈도우 크기
            popup_width = 1000
            popup_height = 700
            
            # 중앙 위치 계산
            x = parent_x + (parent_width - popup_width) // 2
            y = parent_y + (parent_height - popup_height) // 2
            
            self.popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")
        except Exception as e:
            logger.warning(f"팝업 윈도우 중앙 정렬 실패: {e}")
    
    def _create_widgets(self):
        """위젯 생성"""
        # 메인 프레임
        main_frame = ttk.Frame(self.popup)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 제목 프레임
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill="x", pady=(0, 10))
        
        # 제목 라벨
        package_name = self.test_info.get('package_name', 'Unknown Package')
        logger.info(f"🔍 팝업 제목에 사용할 패키지명: '{package_name}'")
        logger.info(f"🔍 전체 test_info: {self.test_info}")
        
        # 패키지명이 Unknown Package인 경우 제목에서 제외
        if package_name == 'Unknown Package':
            title_text = "성능 그래프"
        else:
            title_text = f"성능 그래프 - {package_name}"
        
        title_label = ttk.Label(title_frame, text=title_text, font=self.gui_font_title)
        title_label.pack(side="left")
        
        # 저장 버튼
        save_button = ttk.Button(title_frame, text="그래프 이미지 저장", command=self._save_charts)
        save_button.pack(side="right")
        
        # 차트 표시 프레임
        self.chart_frame = ttk.Frame(main_frame)
        self.chart_frame.pack(fill="both", expand=True)
        
        # 하단 정보 프레임
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill="x", pady=(10, 0))
        
        # 테스트 정보 표시
        test_time = self.test_info.get('test_time', 'Unknown')
        info_text = f"테스트 시간: {test_time} | 총 반복: {self.test_info.get('total_repeats', 'N/A')}회"
        info_label = ttk.Label(info_frame, text=info_text, font=self.gui_font_small)
        info_label.pack(side="left")
        
        # 닫기 버튼
        close_button = ttk.Button(info_frame, text="닫기", command=self.popup.destroy)
        close_button.pack(side="right")
    
    def _display_charts(self):
        """차트 표시"""
        try:
            logger.info(f"차트 표시 시작 - chart_data 타입: {type(self.chart_data)}")
            logger.info(f"chart_data 내용: {self.chart_data}")
            
            # 차트가 있는지 확인
            if not self.chart_data or ('memory' not in self.chart_data and 'cpu' not in self.chart_data):
                logger.warning("차트 데이터가 없거나 memory/cpu 키가 없음")
                if self.chart_data:
                    logger.info(f"사용 가능한 차트 키: {list(self.chart_data.keys())}")
                self._show_no_data_message()
                return
            
            # 그리드 설정
            self.chart_frame.grid_rowconfigure(0, weight=1)
            self.chart_frame.grid_rowconfigure(1, weight=1)
            self.chart_frame.grid_columnconfigure(0, weight=1)
            
            # 2x1 그리드로 차트 배치 (메모리 위, CPU 아래)
            if 'memory' in self.chart_data:
                logger.info("메모리 차트 표시 시작")
                self._display_chart(self.chart_data['memory'], 0, "메모리 사용량")
            
            if 'cpu' in self.chart_data:
                logger.info("CPU 차트 표시 시작")
                self._display_chart(self.chart_data['cpu'], 1, "CPU 사용량")
                
            logger.info("성능 그래프 표시 완료")
            
        except Exception as e:
            logger.error(f"차트 표시 오류: {e}")
            import traceback
            logger.error(f"상세 오류: {traceback.format_exc()}")
            self._show_error_message(str(e))
    
    def _display_chart(self, chart_info: Dict[str, Any], row: int, title: str):
        """개별 차트 표시 (matplotlib figure 또는 기본 데이터 지원)"""
        try:
            logger.info(f"{title} 차트 표시 시작, 데이터 타입: {type(chart_info)}")
            
            # None 체크 먼저 수행
            if chart_info is None:
                logger.warning(f"{title} 차트 - 데이터가 None입니다")
                chart_container = ttk.LabelFrame(self.chart_frame, text=title, padding=5)
                chart_container.grid(row=row, column=0, sticky="nsew", padx=5, pady=5)
                self._show_fallback_message(chart_container, title, "차트 데이터가 생성되지 않았습니다")
                return
            
            logger.info(f"{title} 차트 내용: {chart_info if isinstance(chart_info, dict) else str(chart_info)[:200]}")
            
            # matplotlib figure가 있는 경우 (chart_generator에서 생성)
            if isinstance(chart_info, dict) and 'figure' in chart_info:
                logger.info(f"{title} 차트 - matplotlib figure 사용")
                
                # 차트 프레임 생성
                chart_container = ttk.LabelFrame(self.chart_frame, text=title, padding=5)
                chart_container.grid(row=row, column=0, sticky="nsew", padx=5, pady=5)
                
                # 그리드 가중치 설정
                self.chart_frame.grid_rowconfigure(row, weight=1)
                self.chart_frame.grid_columnconfigure(0, weight=1)
                
                # matplotlib figure를 안전하게 처리
                if MATPLOTLIB_AVAILABLE:
                    try:
                        # ChartGenerator를 통해 팝업 안전 figure 생성
                        try:
                            from src.utils.chart_generator import ChartGenerator
                            chart_gen = ChartGenerator()
                            safe_figure = chart_gen.create_popup_safe_figure(chart_info)
                            
                            if safe_figure:
                                # 안전한 figure로 캔버스 생성
                                canvas = FigureCanvasTkAgg(safe_figure, chart_container)
                                canvas.draw()
                                
                                # 캔버스 위젯 배치
                                canvas.get_tk_widget().pack(fill="both", expand=True)
                                
                                # 차트 정보 저장 (저장 기능을 위해)
                                if not hasattr(self, 'canvas_widgets'):
                                    self.canvas_widgets = {}
                                self.canvas_widgets[title] = canvas
                                
                                logger.info(f"✅ {title} 안전한 팝업 차트 표시 성공")
                                return
                            
                        except Exception as chart_gen_error:
                            logger.warning(f"ChartGenerator 사용 실패: {chart_gen_error}")
                        
                        # 기본 방법으로 시도
                        figure = chart_info['figure']
                        canvas = FigureCanvasTkAgg(figure, chart_container)
                        canvas.draw()
                        
                        # 캔버스 위젯 배치
                        canvas.get_tk_widget().pack(fill="both", expand=True)
                        
                        # 차트 정보 저장 (저장 기능을 위해)
                        if not hasattr(self, 'canvas_widgets'):
                            self.canvas_widgets = {}
                        self.canvas_widgets[title] = canvas
                        
                        logger.info(f"✅ {title} matplotlib 차트 표시 성공")
                        
                    except Exception as canvas_error:
                        logger.error(f"matplotlib 캔버스 생성 실패: {canvas_error}")
                        import traceback
                        logger.error(f"상세 오류: {traceback.format_exc()}")
                        # 기본 메시지 표시
                        self._show_fallback_message(chart_container, title, f"차트 표시 오류: {str(canvas_error)}")
                else:
                    logger.warning("matplotlib 사용 불가")
                    chart_container = ttk.LabelFrame(self.chart_frame, text=title, padding=5)
                    chart_container.grid(row=row, column=0, sticky="nsew", padx=5, pady=5)
                    self._show_fallback_message(chart_container, title, "matplotlib 사용 불가")
            
            # 기본 데이터 형식인 경우 (기본 차트 생성)
            elif isinstance(chart_info, dict) and ('data' in chart_info or 'labels' in chart_info):
                logger.info(f"{title} 차트 - 기본 데이터로 차트 생성")
                self._create_basic_chart(chart_info, row, title)
            
            # 리스트 형태의 데이터인 경우 (성능 데이터)
            elif isinstance(chart_info, list) and len(chart_info) > 0:
                logger.info(f"{title} 차트 - 리스트 데이터로 차트 생성 ({len(chart_info)}개 항목)")
                self._create_chart_from_performance_data(chart_info, row, title)
            
            # 딕셔너리이지만 figure가 없는 경우
            elif isinstance(chart_info, dict):
                logger.warning(f"{title} 차트 - 딕셔너리 형태이지만 figure가 없음. 키: {list(chart_info.keys())}")
                chart_container = ttk.LabelFrame(self.chart_frame, text=title, padding=5)
                chart_container.grid(row=row, column=0, sticky="nsew", padx=5, pady=5)
                self._show_fallback_message(chart_container, title, f"figure 키가 없음\n사용 가능한 키: {list(chart_info.keys())}")
            
            else:
                logger.warning(f"{title} 차트 - 지원되지 않는 데이터 형식: {type(chart_info)}")
                # 오류 메시지 표시
                chart_container = ttk.LabelFrame(self.chart_frame, text=title, padding=5)
                chart_container.grid(row=row, column=0, sticky="nsew", padx=5, pady=5)
                self._show_fallback_message(chart_container, title, f"지원되지 않는 데이터 형식: {type(chart_info)}")
                return
            
        except Exception as e:
            logger.error(f"{title} 차트 표시 오류: {e}")
            import traceback
            logger.error(f"상세 오류: {traceback.format_exc()}")
            # 오류 발생 시 기본 메시지 표시
            try:
                chart_container = ttk.LabelFrame(self.chart_frame, text=title, padding=5)
                chart_container.grid(row=row, column=0, sticky="nsew", padx=5, pady=5)
                self._show_fallback_message(chart_container, title, f"오류: {str(e)[:50]}...")
            except:
                pass
    
    def _create_basic_chart(self, chart_info: Dict[str, Any], row: int, title: str):
        """기본 데이터로 matplotlib 차트 생성"""
        try:
            import matplotlib.pyplot as plt
            
            # 데이터 추출
            data = chart_info.get('data', [])
            labels = chart_info.get('labels', [])
            ylabel = chart_info.get('ylabel', title)
            chart_title = chart_info.get('title', title)
            
            if not data:
                logger.warning(f"{title} - 데이터가 비어있음")
                return
            
            # matplotlib figure 생성 (크기 조정하여 제목이 잘리지 않도록)
            fig, ax = plt.subplots(figsize=(8, 3.5))  # 높이를 4에서 3.5로 줄임
            
            # 라인 차트 생성
            ax.plot(range(len(data)), data, marker='o', linewidth=2, markersize=6)
            ax.set_xlabel('반복 횟수')
            ax.set_ylabel(ylabel)
            ax.set_title(chart_title, fontsize=11, pad=10)  # 폰트 크기 줄이고 패딩 조정
            ax.grid(True, alpha=0.3)
            
            # x축 라벨 설정
            if labels and len(labels) == len(data):
                ax.set_xticks(range(len(labels)))
                ax.set_xticklabels(labels, rotation=45 if len(labels) > 5 else 0)
            
            # 레이아웃 조정 (여백 최적화)
            fig.tight_layout(pad=1.5)
            
            # 차트 프레임 생성
            chart_container = ttk.LabelFrame(self.chart_frame, text=title, padding=5)
            chart_container.grid(row=row, column=0, sticky="nsew", padx=5, pady=5)
            
            # 그리드 가중치 설정
            self.chart_frame.grid_rowconfigure(row, weight=1)
            self.chart_frame.grid_columnconfigure(0, weight=1)
            
            # matplotlib 캔버스 생성
            canvas = FigureCanvasTkAgg(fig, chart_container)
            canvas.draw()
            
            # 캔버스 위젯 배치
            canvas.get_tk_widget().pack(fill="both", expand=True)
            
            # 차트 정보 저장 (저장 기능을 위해)
            if not hasattr(self, 'canvas_widgets'):
                self.canvas_widgets = {}
            self.canvas_widgets[title] = canvas
            
            logger.info(f"{title} 기본 차트 생성 완료: {len(data)}개 데이터 포인트")
            
        except Exception as e:
            logger.error(f"{title} 기본 차트 생성 오류: {e}")
            import traceback
            logger.error(f"상세 오류: {traceback.format_exc()}")

    def _create_chart_from_performance_data(self, performance_data: list, row: int, title: str):
        """성능 데이터 리스트로부터 차트 생성"""
        try:
            import matplotlib.pyplot as plt
            
            logger.info(f"{title} 성능 데이터 차트 생성 시작: {len(performance_data)}개 데이터")
            
            if not performance_data:
                logger.warning(f"{title} - 성능 데이터가 비어있음")
                return
            
            # 데이터 추출
            times = []
            values = []
            
            # 메모리 또는 CPU 데이터 추출
            for i, data in enumerate(performance_data):
                if isinstance(data, dict):
                    if 'memory' in title.lower():
                        value = data.get('memory_mb', 0)
                    elif 'cpu' in title.lower():
                        value = data.get('cpu_percent', 0)
                    else:
                        value = data.get('value', 0)  # 일반적인 값
                    
                    values.append(value)
                    times.append(i + 1)  # 시간 순서
                else:
                    # 단순 숫자 배열인 경우
                    values.append(float(data) if data is not None else 0)
                    times.append(i + 1)
            
            if not values or all(v == 0 for v in values):
                logger.warning(f"{title} - 유효한 데이터가 없음")
                chart_container = ttk.LabelFrame(self.chart_frame, text=title, padding=5)
                chart_container.grid(row=row, column=0, sticky="nsew", padx=5, pady=5)
                self._show_fallback_message(chart_container, title, "유효한 데이터가 없습니다")
                return
            
            # matplotlib figure 생성
            fig, ax = plt.subplots(figsize=(8, 3.5))
            
            # 라인 차트 생성
            color = 'blue' if 'memory' in title.lower() else 'green'
            ax.plot(times, values, marker='o', linewidth=2, markersize=4, color=color)
            
            # 제목과 라벨 설정
            ax.set_title(title, fontsize=11, pad=10)
            ax.set_xlabel('시간 순서')
            
            if 'memory' in title.lower():
                ax.set_ylabel('메모리 (MB)')
                # 통계 정보 추가
                max_val = max(values)
                min_val = min(values)
                avg_val = sum(values) / len(values)
                ax.text(0.02, 0.98, f'최대: {max_val:.1f}MB\n평균: {avg_val:.1f}MB\n최소: {min_val:.1f}MB', 
                       transform=ax.transAxes, verticalalignment='top', fontsize=8,
                       bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
            elif 'cpu' in title.lower():
                ax.set_ylabel('CPU (%)')
                ax.set_ylim(0, 100)
                # 통계 정보 추가
                max_val = max(values)
                avg_val = sum(values) / len(values)
                ax.text(0.02, 0.98, f'최대: {max_val:.1f}%\n평균: {avg_val:.1f}%', 
                       transform=ax.transAxes, verticalalignment='top', fontsize=8,
                       bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.5))
            else:
                ax.set_ylabel('값')
            
            ax.grid(True, alpha=0.3)
            
            # 레이아웃 조정
            fig.tight_layout(pad=1.5)
            
            # 차트 프레임 생성
            chart_container = ttk.LabelFrame(self.chart_frame, text=title, padding=5)
            chart_container.grid(row=row, column=0, sticky="nsew", padx=5, pady=5)
            
            # 그리드 가중치 설정
            self.chart_frame.grid_rowconfigure(row, weight=1)
            self.chart_frame.grid_columnconfigure(0, weight=1)
            
            # matplotlib 캔버스 생성
            canvas = FigureCanvasTkAgg(fig, chart_container)
            canvas.draw()
            
            # 캔버스 위젯 배치
            canvas.get_tk_widget().pack(fill="both", expand=True)
            
            # 차트 정보 저장 (저장 기능을 위해)
            if not hasattr(self, 'canvas_widgets'):
                self.canvas_widgets = {}
            self.canvas_widgets[title] = canvas
            
            logger.info(f"✅ {title} 성능 데이터 차트 생성 완료: {len(values)}개 데이터 포인트")
            
        except Exception as e:
            logger.error(f"{title} 성능 데이터 차트 생성 오류: {e}")
            import traceback
            logger.error(f"상세 오류: {traceback.format_exc()}")
            # 오류 메시지 표시
            chart_container = ttk.LabelFrame(self.chart_frame, text=title, padding=5)
            chart_container.grid(row=row, column=0, sticky="nsew", padx=5, pady=5)
            self._show_fallback_message(chart_container, title, f"차트 생성 오류: {str(e)[:50]}...")
    
    def _show_fallback_message(self, container, title: str, message: str):
        """차트 생성 실패 시 대체 메시지 표시"""
        try:
            # 메시지 라벨 생성
            message_label = ttk.Label(
                container,
                text=f"{title}\n\n{message}",
                font=self.gui_font_normal,
                foreground="gray",
                justify="center"
            )
            message_label.pack(expand=True, pady=20)
            logger.info(f"{title} 대체 메시지 표시: {message}")
        except Exception as e:
            logger.error(f"대체 메시지 표시 오류: {e}")
    
    def _show_no_data_message(self):
        """데이터가 없을 때 메시지 표시"""
        message_label = ttk.Label(
            self.chart_frame, 
            text="표시할 성능 데이터가 없습니다.\n테스트를 실행하고 완료한 후 다시 시도해주세요.",
            font=self.gui_font_large,
            anchor="center"
        )
        message_label.pack(expand=True)
    
    def _show_error_message(self, error_msg: str):
        """오류 메시지 표시"""
        error_label = ttk.Label(
            self.chart_frame,
            text=f"차트 표시 중 오류가 발생했습니다:\n{error_msg}",
            font=self.gui_font_normal,
            foreground="red",
            anchor="center"
        )
        error_label.pack(expand=True)
    
    def _save_charts(self):
        """차트를 이미지로 저장"""
        try:
            if not hasattr(self, 'canvas_widgets') or not self.canvas_widgets:
                messagebox.showwarning("저장 실패", "저장할 차트가 없습니다.")
                return
            
            # 파일 저장 대화상자
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 패키지명 우선순위로 가져오기
            package_name = 'unknown_app'
            
            # 1. test_info에서 package_name 확인
            if self.test_info.get('package_name') and self.test_info['package_name'] not in ['Unknown Package', 'unknown', '']:
                package_name = self.test_info['package_name']
                logger.info(f"test_info에서 패키지명 획득: {package_name}")
            
            # 2. parent의 test_context에서 app_package_name 확인 (가장 정확)
            elif hasattr(self.parent, 'test_context') and hasattr(self.parent.test_context, 'app_package_name'):
                if self.parent.test_context.app_package_name:
                    package_name = self.parent.test_context.app_package_name
                    logger.info(f"parent test_context.app_package_name에서 패키지명 획득: {package_name}")
            
            # 3. parent의 test_context에서 package_name 확인
            elif hasattr(self.parent, 'test_context') and hasattr(self.parent.test_context, 'package_name'):
                if self.parent.test_context.package_name:
                    package_name = self.parent.test_context.package_name
                    logger.info(f"parent test_context.package_name에서 패키지명 획득: {package_name}")
            
            # 4. chart_data에서 확인 (차트 생성 시 포함된 패키지명)
            elif hasattr(self, 'chart_data') and isinstance(self.chart_data, dict):
                for chart_key in ['memory', 'cpu']:
                    if chart_key in self.chart_data and isinstance(self.chart_data[chart_key], dict):
                        chart_title = self.chart_data[chart_key].get('title', '')
                        if ' - ' in chart_title and 'com.' in chart_title:
                            # "메모리 사용량 - com.example.app" 형태에서 패키지명 추출
                            package_name = chart_title.split(' - ')[-1]
                            logger.info(f"차트 제목에서 패키지명 추출: {package_name}")
                            break
            
            # 5. parent의 app_var에서 확인 (현재 선택된 앱)
            elif hasattr(self.parent, 'app_var') and self.parent.app_var:
                selected_app = self.parent.app_var.get()
                if selected_app and ' - ' in selected_app and 'com.' in selected_app:
                    package_name = selected_app.split(' - ')[-1]
                    logger.info(f"parent app_var에서 패키지명 추출: {package_name}")
            
            logger.info(f"최종 추출된 패키지명: {package_name}")
            
            # 패키지명에서 파일명에 사용할 수 없는 문자 제거
            if package_name in ['Unknown Package', 'unknown', '', 'unknown_app']:
                # Unknown Package인 경우 현재 시간을 기반으로 더 명확한 이름 생성
                safe_package_name = f"app_{timestamp}"
                logger.warning(f"패키지명을 알 수 없어서 타임스탬프 기반 이름 사용: {safe_package_name}")
            else:
                safe_package_name = package_name.replace('.', '_').replace(' ', '_').replace('-', '_')
                # 파일명에 사용할 수 없는 문자들 제거
                import re
                safe_package_name = re.sub(r'[<>:"/\\|?*]', '_', safe_package_name)
                logger.info(f"파일명용 패키지명 변환: {package_name} -> {safe_package_name}")
            
            logger.info(f"최종 파일명용 패키지명: {safe_package_name}")
            
            default_filename = f"performance_charts_{safe_package_name}_{timestamp}.png"
            
            file_path = filedialog.asksaveasfilename(
                title="성능 차트 저장",
                defaultextension=".png",
                initialfile=default_filename,
                filetypes=[
                    ("PNG files", "*.png"),
                    ("JPEG files", "*.jpg"),
                    ("All files", "*.*")
                ]
            )
            
            if not file_path:
                return
            
            # 차트들을 하나의 이미지로 합치기
            self._save_combined_charts(file_path)
            
            messagebox.showinfo("저장 완료", f"성능 차트가 저장되었습니다:\n{file_path}")
            logger.info(f"성능 차트 저장 완료: {file_path}")
            
        except Exception as e:
            error_msg = f"차트 저장 중 오류 발생: {e}"
            logger.error(error_msg)
            messagebox.showerror("저장 실패", error_msg)
    
    def _save_combined_charts(self, file_path: str):
        """여러 차트를 하나의 이미지로 합쳐서 저장"""
        try:
            # 새로운 figure 생성 (합친 차트용, 크기 조정)
            fig, axes = plt.subplots(2, 1, figsize=(10, 7), dpi=150)  # 높이를 8에서 7로 줄임
            
            # 패키지명이 Unknown Package인 경우 제목에서 제외
            package_name = self.test_info.get('package_name', 'Unknown')
            if package_name == 'Unknown Package':
                title = "성능 차트"
            else:
                title = f"성능 차트 - {package_name}"
            
            fig.suptitle(title, fontsize=14, fontweight='bold')
            
            # 메모리 차트
            if 'memory' in self.chart_data:
                memory_fig = self.chart_data['memory']['figure']
                self._copy_chart_to_subplot(memory_fig, axes[0])
                axes[0].set_title("메모리 사용량", fontsize=11, fontweight='bold')
            
            # CPU 차트
            if 'cpu' in self.chart_data:
                cpu_fig = self.chart_data['cpu']['figure']
                self._copy_chart_to_subplot(cpu_fig, axes[1])
                axes[1].set_title("CPU 사용량", fontsize=11, fontweight='bold')
            
            # 레이아웃 조정 (여백 최적화)
            plt.tight_layout(pad=1.5)
            plt.subplots_adjust(top=0.92)  # 상단 여백 조정
            
            # 파일 저장
            plt.savefig(file_path, dpi=150, bbox_inches='tight', facecolor='white')
            plt.close(fig)
            
        except Exception as e:
            logger.error(f"합친 차트 저장 오류: {e}")
            # 개별 차트 저장 시도
            self._save_individual_charts(file_path)
    
    def _copy_chart_to_subplot(self, source_fig, target_ax):
        """원본 차트의 데이터를 새로운 subplot으로 복사"""
        try:
            # 원본 figure의 첫 번째 axes 가져오기
            source_ax = source_fig.axes[0]
            
            # 라인 플롯 복사
            for line in source_ax.get_lines():
                target_ax.plot(line.get_xdata(), line.get_ydata(), 
                             color=line.get_color(), label=line.get_label(), 
                             linewidth=line.get_linewidth())
            
            # 축 라벨 복사
            target_ax.set_xlabel(source_ax.get_xlabel())
            target_ax.set_ylabel(source_ax.get_ylabel())
            
            # X축 설정 완전 복사 (시간 정보 유지)
            try:
                # X축 틱 위치와 라벨 모두 복사
                source_xticks = source_ax.get_xticks()
                source_xticklabels = source_ax.get_xticklabels()
                
                # 라벨이 있는 경우에만 설정
                if source_xticklabels:
                    label_texts = [tick.get_text() for tick in source_xticklabels]
                    if any(label.strip() for label in label_texts):
                        target_ax.set_xticks(source_xticks)
                        target_ax.set_xticklabels(label_texts, rotation=45, ha='right')
                        logger.info(f"X축 시간 라벨 복사 완료: {label_texts[:3]}...")
                    
                # X축 범위도 복사
                target_ax.set_xlim(source_ax.get_xlim())
                
            except Exception as tick_error:
                logger.warning(f"X축 설정 복사 실패: {tick_error}")
                # 기본 X축 설정 적용
                try:
                    target_ax.tick_params(axis='x', rotation=45)
                except:
                    pass
            
            # Y축 범위 복사
            target_ax.set_ylim(source_ax.get_ylim())
            
            # 그리드 설정
            target_ax.grid(True, alpha=0.3)
            
            # 범례 설정
            if source_ax.get_legend():
                target_ax.legend()
                
        except Exception as e:
            logger.error(f"차트 복사 오류: {e}")
    
    def _save_individual_charts(self, base_path: str):
        """개별 차트들을 따로 저장 (fallback)"""
        try:
            base_name = os.path.splitext(base_path)[0]
            extension = os.path.splitext(base_path)[1]
            
            for chart_type, chart_info in self.chart_data.items():
                if 'figure' in chart_info:
                    individual_path = f"{base_name}_{chart_type}{extension}"
                    chart_info['figure'].savefig(individual_path, dpi=150, bbox_inches='tight')
                    logger.info(f"개별 차트 저장: {individual_path}")
                    
        except Exception as e:
            logger.error(f"개별 차트 저장 오류: {e}")
            raise
