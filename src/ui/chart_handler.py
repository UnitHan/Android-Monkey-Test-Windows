#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
차트 처리 핸들러
main_app.py에서 분리된 차트 관련 기능들
"""
import logging
import tkinter as tk
from tkinter import ttk

# matplotlib 스레딩 문제 방지
try:
    import matplotlib
    matplotlib.use('TkAgg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

logger = logging.getLogger(__name__)

def _log_error(message):
    """EXE 모드를 고려한 오류 로깅"""
    import sys
    if not getattr(sys, 'frozen', False):
        logger.error(message)
    else:
        logger.debug(f"[EXE모드] {message}")

class ChartHandler:
    """차트 처리를 담당하는 핸들러"""
    
    def __init__(self, main_app):
        self.main_app = main_app
        
        # ChartGenerator 인스턴스 생성
        try:
            from src.utils.chart_generator import ChartGenerator
            self.chart_generator = ChartGenerator()
            logger.info("ChartGenerator 초기화 완료")
        except ImportError as e:
            logger.error(f"ChartGenerator import 실패: {e}")
            self.chart_generator = None
        
    def add_charts_to_visualization(self, charts):
        """차트들을 시각화 탭에 추가 - 시각화 탭이 비활성화되어 있으면 건너뜀"""
        # 시각화 탭이 없으면 작동하지 않음
        if not hasattr(self.main_app, 'visualization_frame'):
            logger.debug("시각화 탭이 비활성화되어 있어 차트 추가를 건너뜁니다")
            return
            
        try:
            # 기존 차트들 모두 제거
            self.clear_existing_charts()
            
            if not charts:
                logger.warning("추가할 차트가 없습니다")
                self.show_placeholder("📊 차트 없음", "생성된 차트가 없습니다.")
                return
            
            logger.info(f"📊 차트 추가 시작: {len(charts)}개 차트")
            
            # 차트 데이터 타입 검증 및 필터링
            valid_charts = {}
            for chart_name, chart_data in charts.items():
                logger.info(f"차트 '{chart_name}' 데이터 타입: {type(chart_data)}")
                if isinstance(chart_data, dict):
                    valid_charts[chart_name] = chart_data
                    logger.info(f"✅ 유효한 차트: {chart_name}")
                else:
                    logger.warning(f"⚠️ 무효한 차트 타입 ({chart_name}): {type(chart_data)} - 건너뛰기")
            
            if not valid_charts:
                logger.warning("유효한 차트 데이터가 없습니다")
                self.show_placeholder("📊 차트 데이터 없음", "유효한 차트 데이터가 생성되지 않았습니다.")
                return
            
            # 메모리와 CPU 차트를 좌우로 배치 (첫 번째 행)
            memory_chart = valid_charts.get('memory')
            cpu_chart = valid_charts.get('cpu')
            
            logger.info(f"메모리 차트 존재: {memory_chart is not None}")
            logger.info(f"CPU 차트 존재: {cpu_chart is not None}")
            
            current_row = 0
            
            if memory_chart and cpu_chart:
                self._add_side_by_side_charts(memory_chart, cpu_chart, current_row)
                current_row += 1
            elif memory_chart:
                self._add_single_chart('memory', memory_chart, current_row)
                current_row += 1
            elif cpu_chart:
                self._add_single_chart('cpu', cpu_chart, current_row)
                current_row += 1
            
            # 나머지 차트들은 개별적으로 추가
            other_charts = [(k, v) for k, v in valid_charts.items() 
                           if k not in ['memory', 'cpu']]
            
            for chart_name, chart_data in other_charts:
                self._add_single_chart(chart_name, chart_data, current_row)
                current_row += 1
            
            # 시각화 프레임의 그리드 가중치 설정
            if hasattr(self.main_app, 'visualization_frame'):
                self.main_app.visualization_frame.grid_columnconfigure(0, weight=1)
                self.main_app.visualization_frame.grid_columnconfigure(1, weight=1)
            
            # 스크롤 영역 업데이트 - 차트가 추가된 후 프레임 크기 변경을 감지
            if hasattr(self.main_app, 'visualization_canvas'):
                # 프레임 업데이트를 위해 잠시 대기
                self.main_app.after(100, self._update_scroll_region)
            
            logger.info(f"✅ 모든 차트 추가 완료")
            
        except Exception as e:
            _log_error(f"차트 추가 중 오류: {e}")
            logger.exception("차트 추가 상세 오류:")
            self.show_placeholder("❌ 차트 추가 실패", f"차트를 추가하는 중 오류가 발생했습니다: {str(e)}")

    def clear_existing_charts(self):
        """기존 차트들 제거"""
        # 시각화 탭이 없으면 작동하지 않음
        if not hasattr(self.main_app, 'visualization_frame'):
            logger.debug("시각화 탭이 없어 차트 제거를 건너뜁니다")
            return
            
        try:
            if hasattr(self.main_app, 'chart_canvases'):
                for canvas in self.main_app.chart_canvases.values():
                    try:
                        if canvas and hasattr(canvas, 'get_tk_widget'):
                            widget = canvas.get_tk_widget()
                            if widget and widget.winfo_exists():
                                widget.destroy()
                        # matplotlib figure도 정리
                        if hasattr(canvas, 'figure'):
                            try:
                                import matplotlib.pyplot as plt
                                plt.close(canvas.figure)
                            except:
                                pass
                    except Exception as e:
                        logger.debug(f"차트 캔버스 제거 중 오류 (무시): {e}")
                
                self.main_app.chart_canvases.clear()
            
            if hasattr(self.main_app, 'current_charts'):
                self.main_app.current_charts.clear()
            
            # 시각화 프레임 내부 위젯들 제거 (안내 메시지 제외하고)
            if hasattr(self.main_app, 'visualization_frame'):
                for widget in self.main_app.visualization_frame.winfo_children():
                    try:
                        # 안내 메시지는 유지
                        if widget != getattr(self.main_app, 'visualization_placeholder', None):
                            widget.destroy()
                    except Exception as e:
                        logger.debug(f"위젯 제거 중 오류 (무시): {e}")
            
            # 플레이스홀더 제거
            if hasattr(self.main_app, 'visualization_placeholder'):
                self.main_app.visualization_placeholder.destroy()
                delattr(self.main_app, 'visualization_placeholder')
                
        except Exception as e:
            logger.debug(f"차트 제거 중 오류: {e}")

    def _add_side_by_side_charts(self, left_chart, right_chart, row):
        """메모리와 CPU 차트를 좌우로 배치"""
        # 시각화 탭이 없으면 작동하지 않음
        if not hasattr(self.main_app, 'visualization_frame'):
            logger.debug("시각화 탭이 없어 좌우 차트 배치를 건너뜁니다")
            return
            
        try:
            logger.info("차트 좌우 배치 시작")
            logger.info(f"왼쪽 차트(메모리): {left_chart.get('title', 'N/A') if left_chart else 'None'}")
            logger.info(f"오른쪽 차트(CPU): {right_chart.get('title', 'N/A') if right_chart else 'None'}")
            
            # 플레이스홀더 제거
            if hasattr(self.main_app, 'visualization_placeholder'):
                self.main_app.visualization_placeholder.destroy()
                delattr(self.main_app, 'visualization_placeholder')
            
            # 좌우 배치를 위한 프레임 생성
            side_by_side_frame = ttk.Frame(self.main_app.visualization_frame)
            side_by_side_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=10, pady=10)
            
            # 좌우 프레임 생성
            left_frame = ttk.LabelFrame(side_by_side_frame, text="메모리 사용량", padding=10)
            left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
            
            right_frame = ttk.LabelFrame(side_by_side_frame, text="CPU 사용률", padding=10)
            right_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
            
            # 그리드 가중치 설정
            side_by_side_frame.grid_columnconfigure(0, weight=1)
            side_by_side_frame.grid_columnconfigure(1, weight=1)
            
            # 각 프레임에 차트 추가
            left_success = self._add_chart_to_frame(left_frame, left_chart, "memory") if left_chart else False
            right_success = self._add_chart_to_frame(right_frame, right_chart, "cpu") if right_chart else False
            
            if left_success or right_success:
                # 시각화 프레임 업데이트
                self.main_app.visualization_frame.update_idletasks()
                logger.info("✅ 좌우 차트 배치 완료")
            else:
                logger.warning("⚠️ 좌우 차트 배치 실패 - 차트 생성 실패")
                
        except Exception as e:
            _log_error(f"좌우 차트 배치 실패: {e}")
            logger.exception("좌우 차트 배치 상세 오류:")

    def _add_single_chart(self, chart_name, chart_data, row):
        """단일 차트를 시각화 탭에 추가"""
        # 시각화 탭이 없으면 작동하지 않음
        if not hasattr(self.main_app, 'visualization_frame'):
            logger.debug(f"시각화 탭이 없어 단일 차트({chart_name}) 추가를 건너뜁니다")
            return
            
        try:
            logger.info(f"단일 차트 추가 시도: {chart_name}, 데이터 타입: {type(chart_data)}")
            
            # 차트 데이터 타입 검증
            if not isinstance(chart_data, dict):
                logger.warning(f"⚠️ 차트 데이터가 딕셔너리가 아님: {type(chart_data)}")
                return
            
            # 플레이스홀더 제거
            if hasattr(self.main_app, 'visualization_placeholder'):
                self.main_app.visualization_placeholder.destroy()
                delattr(self.main_app, 'visualization_placeholder')
            
            # 차트 제목 결정
            chart_title = chart_data.get('title', chart_name)
            
            # 단일 차트 프레임 생성
            chart_frame = ttk.LabelFrame(
                self.main_app.visualization_frame, 
                text=chart_title, 
                padding=10
            )
            chart_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=10, pady=10)
            
            # 차트 추가
            success = self._add_chart_to_frame(chart_frame, chart_data, chart_name)
            
            if success:
                # 시각화 프레임 업데이트
                self.main_app.visualization_frame.update_idletasks()
                logger.info(f"✅ 단일 차트 추가 완료: {chart_name}")
            else:
                logger.warning(f"⚠️ 단일 차트 추가 실패: {chart_name}")
                
        except Exception as e:
            _log_error(f"단일 차트 추가 실패 ({chart_name}): {e}")
            logger.exception(f"차트 추가 상세 오류 ({chart_name}):")

    def _add_chart_to_frame(self, frame, chart_data, chart_name):
        """프레임에 차트 추가"""
        try:
            logger.info(f"차트 프레임 추가 시작: {chart_name}")
            logger.info(f"차트 데이터 키: {list(chart_data.keys()) if chart_data else 'None'}")
            
            if not MATPLOTLIB_AVAILABLE:
                logger.error("matplotlib을 사용할 수 없습니다")
                return False
            
            if not isinstance(chart_data, dict) or 'figure' not in chart_data:
                logger.error(f"차트 데이터에 'figure' 키가 없습니다. 키: {list(chart_data.keys()) if isinstance(chart_data, dict) else 'Not dict'}")
                return False
            
            # ChartGenerator를 사용하여 GUI 캔버스 생성
            if self.chart_generator:
                canvas = self.chart_generator.create_gui_canvas(frame, chart_data)
                if canvas:
                    # 캔버스를 프레임에 배치
                    canvas_widget = canvas.get_tk_widget()
                    canvas_widget.pack(fill="both", expand=True, padx=5, pady=5)
                    
                    # 캔버스 저장 (나중에 정리용)
                    if not hasattr(self.main_app, 'chart_canvases'):
                        self.main_app.chart_canvases = {}
                    self.main_app.chart_canvases[chart_name] = canvas
                    
                    logger.info(f"✅ 차트 프레임 추가 성공: {chart_name}")
                    return True
                else:
                    logger.error(f"❌ GUI 캔버스 생성 실패: {chart_name}")
                    return False
            else:
                logger.error("ChartGenerator가 초기화되지 않았습니다")
                return False
                
        except Exception as e:
            logger.error(f"❌ 차트 프레임 추가 실패 ({chart_name}): {e}")
            logger.exception(f"차트 프레임 추가 상세 오류 ({chart_name}):")
            return False

    def show_placeholder(self, title, message):
        """테스트 진행 중 메시지 표시"""
        # 시각화 탭이 없으면 작동하지 않음
        if not hasattr(self.main_app, 'visualization_frame'):
            logger.debug("시각화 탭이 없어 플레이스홀더 표시를 건너뜁니다")
            return
            
        try:
            # 기존 플레이스홀더 제거
            if hasattr(self.main_app, 'visualization_placeholder'):
                self.main_app.visualization_placeholder.destroy()
            
            # 새 플레이스홀더 프레임 생성
            placeholder_frame = ttk.Frame(self.main_app.visualization_frame)
            placeholder_frame.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=20, pady=50)
            
            # 제목 라벨
            title_label = ttk.Label(
                placeholder_frame,
                text=title,
                font=("맑은 고딕", 16, "bold"),
                anchor="center"
            )
            title_label.pack(pady=(0, 10))
            
            # 메시지 라벨
            message_label = ttk.Label(
                placeholder_frame,
                text=message,
                font=("맑은 고딕", 11),
                anchor="center",
                foreground="gray"
            )
            message_label.pack()
            
            # 프레임 중앙 정렬
            self.main_app.visualization_frame.grid_rowconfigure(0, weight=1)
            self.main_app.visualization_frame.grid_columnconfigure(0, weight=1)
            
            # 플레이스홀더 저장
            self.main_app.visualization_placeholder = placeholder_frame
            
            logger.info(f"플레이스홀더 표시: {title}")
            
        except Exception as e:
            logger.error(f"플레이스홀더 표시 실패: {e}")

    def _update_scroll_region(self):
        """스크롤 영역 업데이트"""
        # 시각화 탭이 없으면 작동하지 않음
        if not hasattr(self.main_app, 'visualization_frame') or not hasattr(self.main_app, 'visualization_canvas'):
            return
            
        try:
            if hasattr(self.main_app, 'visualization_canvas') and hasattr(self.main_app, 'visualization_frame'):
                # 프레임 업데이트
                self.main_app.visualization_frame.update_idletasks()
                
                # bbox 계산
                canvas = self.main_app.visualization_canvas
                if canvas.winfo_exists():
                    try:
                        bbox = canvas.bbox("all")
                        if bbox:
                            canvas.configure(scrollregion=bbox)
                        # 프레임 크기 재계산
                        self.main_app.visualization_frame.update_idletasks()
                    except Exception as bbox_error:
                        logger.debug(f"bbox 계산 오류 (무시): {bbox_error}")
                        
        except Exception as e:
            logger.debug(f"스크롤 영역 업데이트 오류 (무시): {e}")

    def cleanup_charts(self):
        """모든 차트 리소스 정리"""
        try:
            if hasattr(self.main_app, 'chart_canvases'):
                for canvas in self.main_app.chart_canvases.values():
                    try:
                        if canvas and hasattr(canvas, 'figure'):
                            plt.close(canvas.figure)
                    except:
                        pass
                self.main_app.chart_canvases.clear()
                
            if self.chart_generator:
                self.chart_generator.cleanup()
                
        except Exception as e:
            logger.debug(f"차트 정리 중 오류 (무시): {e}")