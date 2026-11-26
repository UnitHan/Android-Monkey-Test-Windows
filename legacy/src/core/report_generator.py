#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
리포트 생성기
"""
import os
import datetime
import webbrowser
from pathlib import Path
from typing import Dict, Any, List
from src.core.test_context import TestContext
from src.config import MONKEY_LOG_DIR
from src.utils.logger import setup_logger
from src.utils.chart_generator import ChartGenerator, TestResultData

logger = setup_logger(__name__)

class ReportGenerator:
    """리포트 생성 클래스"""
    
    def __init__(self, test_context: TestContext):
        self.test_context = test_context
        self.chart_generator = ChartGenerator()
    
    def generate_html_report(self) -> str:
        """HTML 리포트 생성"""
        summary = self.test_context.current_test_report.get("summary", {})
        details = self.test_context.current_test_report.get("details", [])
        issues = self.test_context.current_test_report.get("issues", [])
        
        # 성능 차트 생성 (matplotlib 기반)
        performance_charts_html = self._generate_performance_charts(details)
        
        # Chart.js 데이터 생성 (기존 차트용)
        chart_data = self._generate_chart_data()
        
        html_content = self._get_html_template().format(
            title="Monkey 테스트 리포트",
            test_target=summary.get('test_target', 'N/A'),
            test_period=summary.get('test_period', 'N/A'),
            preset=summary.get('preset', 'N/A'),
            result_summary=summary.get('result_summary', 'N/A'),
            execution_time=summary.get('execution_time', '00분'),
            device=summary.get('device', 'N/A'),
            connection_mode=summary.get('connection_mode', 'N/A'),
            detail_rows=self._generate_detail_rows(details),
            issue_sections=self._generate_issue_sections(issues),
            chart_data=chart_data,
            performance_charts=performance_charts_html
        )
        
        return html_content
    
    def _generate_performance_charts(self, details: List[Dict]) -> str:
        """성능 차트 HTML 생성 (이미지 기반)"""
        try:
            if not details:
                return '<div class="no-charts">성능 데이터가 없습니다.</div>'
            
            logger.info(f"성능 차트 생성 시작 - 테스트 상세 데이터: {len(details)}개")
            
            # 먼저 details에서 직접 메모리/CPU 데이터 추출 시도
            memory_values = []
            cpu_values = []
            timestamps = []
            
            for i, detail in enumerate(details):
                try:
                    # 메모리 피크 값 추출
                    mem_peak = detail.get('mem_peak', detail.get('memory_peak', 0))
                    if isinstance(mem_peak, str):
                        import re
                        mem_match = re.search(r'(\d+(?:\.\d+)?)', str(mem_peak))
                        mem_peak = float(mem_match.group(1)) if mem_match else 0.0
                    else:
                        mem_peak = float(mem_peak) if mem_peak else 0.0
                    
                    # CPU 피크 값 추출  
                    cpu_peak = detail.get('cpu_peak', 0)
                    if isinstance(cpu_peak, str):
                        import re
                        cpu_match = re.search(r'(\d+(?:\.\d+)?)', str(cpu_peak))
                        cpu_peak = float(cpu_match.group(1)) if cpu_peak else 0.0
                    else:
                        cpu_peak = float(cpu_peak) if cpu_peak else 0.0
                    
                    # 타임스탬프 추출
                    timestamp = detail.get('timestamp', f"테스트{i+1}")
                    
                    if mem_peak > 0:
                        memory_values.append(mem_peak)
                    if cpu_peak > 0:
                        cpu_values.append(cpu_peak)
                    timestamps.append(str(timestamp))
                    
                    logger.info(f"테스트 {i+1}: 메모리={mem_peak}MB, CPU={cpu_peak}%")
                    
                except Exception as e:
                    logger.warning(f"테스트 데이터 {i} 처리 실패: {e}")
                    continue
            
            logger.info(f"추출된 성능 데이터 - 메모리: {len(memory_values)}개, CPU: {len(cpu_values)}개")
            
            # 간단한 성능 차트 생성 (데이터가 있는 경우)
            charts = {}
            app_package = self.test_context.app_package_name or "Unknown Package"
            
            if memory_values:
                memory_chart = self.chart_generator._create_simple_memory_chart(memory_values, timestamps[:len(memory_values)], app_package)
                if memory_chart:
                    charts['memory'] = memory_chart
                    logger.info("메모리 차트 생성 성공")
            
            if cpu_values:
                cpu_chart = self.chart_generator._create_simple_cpu_chart(cpu_values, timestamps[:len(cpu_values)], app_package)
                if cpu_chart:
                    charts['cpu'] = cpu_chart  
                    logger.info("CPU 차트 생성 성공")
            
            if charts:
                logger.info(f"성능 차트 생성 완료: {list(charts.keys())}")
                return self._create_side_by_side_charts_html(charts)
            
            # 차트 생성 실패 시 기존 방식으로 fallback
            logger.warning("간단한 차트 생성 실패, 기존 방식으로 fallback")
            
            # 성능 모니터링 데이터 가져오기 (시간대별 차트용)
            performance_data = getattr(self.test_context, 'performance_data', [])
            
            # 시간대별 차트 우선 생성 시도 - 앱 패키지명도 전달
            if performance_data:
                logger.info(f"성능 데이터 {len(performance_data)}개로 시간대별 차트 생성 시도")
                app_package = self.test_context.app_package_name or "Unknown Package"
                charts = self.chart_generator.create_performance_charts_from_data(performance_data, details, app_package)
                
                if charts:
                    logger.info(f"시간대별 차트 {len(charts)}개 생성 성공")
                    return self._create_side_by_side_charts_html(charts)
                else:
                    logger.warning("시간대별 차트 생성 실패, 기존 방식으로 fallback")
            
            # 기존 방식으로 fallback: 테스트 결과 데이터를 TestResultData 객체로 변환
            test_results = []
            for i, detail in enumerate(details):
                try:
                    # 키 매핑 개선 (main_app.py와 동일한 방식)
                    repeat_num = detail.get('repeat', detail.get('repeat_number', i + 1))
                    exec_time = detail.get('time', detail.get('execution_time', 0.0))
                    event_cnt = detail.get('events', detail.get('event_count', 0))
                    crash_cnt = detail.get('crash', detail.get('crash_count', 0))
                    anr_cnt = detail.get('anr', detail.get('anr_count', 0))
                    timeout_cnt = detail.get('timeout', detail.get('timeout_count', 0))
                    mem_peak = detail.get('mem_peak', detail.get('memory_peak', 0.0))
                    cpu_peak = detail.get('cpu_peak', 0.0)
                    
                    # 실행 시간 처리 ("12초" -> 12.0)
                    if isinstance(exec_time, str):
                        import re
                        time_match = re.search(r'(\d+(?:\.\d+)?)', str(exec_time))
                        exec_time = float(time_match.group(1)) if time_match else 0.0
                    
                    # 반복 번호 처리 ("1회차" -> 1)
                    if isinstance(repeat_num, str):
                        import re
                        repeat_match = re.search(r'(\d+)', str(repeat_num))
                        repeat_num = int(repeat_match.group(1)) if repeat_match else i + 1
                    elif repeat_num is None:
                        repeat_num = i + 1
                    
                    # 메모리 값 처리 (MB 단위로 변환)
                    if isinstance(mem_peak, str):
                        # "696MB" 형태의 문자열에서 숫자만 추출
                        import re
                        mem_match = re.search(r'(\d+(?:\.\d+)?)', str(mem_peak))
                        mem_peak = float(mem_match.group(1)) if mem_match else 0.0
                    
                    # CPU 값 처리 (% 제거)
                    if isinstance(cpu_peak, str):
                        import re
                        cpu_match = re.search(r'(\d+(?:\.\d+)?)', str(cpu_peak))
                        cpu_peak = float(cpu_match.group(1)) if cpu_match else 0.0
                    
                    # 이벤트 수 처리 (문자열에서 숫자 추출)
                    if isinstance(event_cnt, str):
                        import re
                        event_match = re.search(r'(\d+)', str(event_cnt))
                        event_cnt = int(event_match.group(1)) if event_match else 0
                    
                    # 오류 수 처리 (문자열에서 숫자 추출)
                    if isinstance(crash_cnt, str):
                        import re
                        crash_match = re.search(r'(\d+)', str(crash_cnt))
                        crash_cnt = int(crash_match.group(1)) if crash_match else 0
                    
                    if isinstance(anr_cnt, str):
                        import re
                        anr_match = re.search(r'(\d+)', str(anr_cnt))
                        anr_cnt = int(anr_match.group(1)) if anr_match else 0
                    
                    if isinstance(timeout_cnt, str):
                        import re
                        timeout_match = re.search(r'(\d+)', str(timeout_cnt))
                        timeout_cnt = int(timeout_match.group(1)) if timeout_match else 0
                    
                    test_results.append(TestResultData(
                        repeat_number=repeat_num,  # 이미 int로 변환된 값 사용
                        execution_time=float(exec_time) if exec_time is not None else 0.0,
                        event_count=int(event_cnt) if event_cnt is not None else 0,
                        crash_count=int(crash_cnt) if crash_cnt is not None else 0,
                        anr_count=int(anr_cnt) if anr_cnt is not None else 0,
                        timeout_count=int(timeout_cnt) if timeout_cnt is not None else 0,
                        memory_peak=float(mem_peak) if mem_peak is not None else 0.0,
                        cpu_peak=float(cpu_peak) if cpu_peak is not None else 0.0,
                        timestamp=detail.get('timestamp')
                    ))
                except (ValueError, TypeError) as e:
                    logger.warning(f"테스트 결과 데이터 변환 실패 (항목 {i}): {e}")
                    continue
            
            if not test_results:
                logger.warning("유효한 테스트 결과 데이터가 없습니다.")
                return '<div class="no-charts">유효한 성능 데이터가 없습니다.</div>'
            
            logger.info(f"테스트 결과 {len(test_results)}개로 차트 생성 시작")
            for i, result in enumerate(test_results[:3]):  # 처음 3개만 로그
                logger.info(f"테스트 결과 {i+1}: 메모리={result.memory_peak}MB, CPU={result.cpu_peak}%")
            
            # 차트 생성 - 앱 패키지명도 함께 전달 (더 확실한 패키지명 가져오기)
            app_package = self.test_context.app_package_name or "Unknown Package"
            logger.info(f"HTML 리포트용 차트 생성 - 패키지명: {app_package}")
            charts = self.chart_generator.create_performance_charts(test_results, app_package)
            
            if not charts:
                logger.warning("차트 생성기에서 차트를 생성하지 못했습니다.")
                return '<div class="no-charts">차트를 생성할 수 없습니다.</div>'
            
            logger.info(f"생성된 차트: {list(charts.keys())}")
            
            # 메모리와 CPU 차트를 나란히 배치하는 HTML 생성
            return self._create_side_by_side_charts_html(charts)
            
        except Exception as e:
            logger.error(f"성능 차트 생성 중 오류: {e}")
            return f'<div class="chart-error">차트 생성 오류: {str(e)}</div>'
    
    def _create_side_by_side_charts_html(self, charts: Dict[str, Any]) -> str:
        """메모리와 CPU 차트를 좌우로 나란히 배치하는 HTML 생성"""
        try:
            logger.info(f"HTML 차트 배치 시작 - 생성된 차트: {list(charts.keys())}")

            # charts['memory'] 또는 charts['cpu']가 None이면 빈 dict로 대체
            memory_chart = charts.get('memory') or {}
            cpu_chart = charts.get('cpu') or {}

            # base64 이미지 가져오기
            memory_img = memory_chart.get('base64_image', '')
            cpu_img = cpu_chart.get('base64_image', '')

            logger.info(f"메모리 차트 이미지: {'있음' if memory_img else '없음'} ({len(memory_img)} 바이트)")
            logger.info(f"CPU 차트 이미지: {'있음' if cpu_img else '없음'} ({len(cpu_img)} 바이트)")

            html_parts = []

            # 메모리와 CPU 차트를 좌우로 배치
            if memory_img and cpu_img:
                html_parts.append('''
                <div class="charts-row">
                    <div class="chart-container">
                        <h3>메모리 사용량 추이</h3>
                        <img src="data:image/png;base64,{memory_img}" alt="메모리 사용량 차트" class="performance-chart">
                    </div>
                    <div class="chart-container">
                        <h3>CPU 사용량 추이</h3>
                        <img src="data:image/png;base64,{cpu_img}" alt="CPU 사용량 차트" class="performance-chart">
                    </div>
                </div>
                '''.format(memory_img=memory_img, cpu_img=cpu_img))
            elif memory_img:
                # 메모리 차트만 있는 경우
                html_parts.append('''
                <div class="chart-container">
                    <h3>메모리 사용량 추이</h3>
                    <img src="data:image/png;base64,{memory_img}" alt="메모리 사용량 차트" class="performance-chart">
                </div>
                '''.format(memory_img=memory_img))
            elif cpu_img:
                # CPU 차트만 있는 경우
                html_parts.append('''
                <div class="chart-container">
                    <h3>CPU 사용량 추이</h3>
                    <img src="data:image/png;base64,{cpu_img}" alt="CPU 사용량 차트" class="performance-chart">
                </div>
                '''.format(cpu_img=cpu_img))

            # 나머지 차트들은 전체 너비로 추가 (오류, 실행시간, 요약 등)
            for chart_name in ['errors', 'execution_time', 'summary']:
                chart = charts.get(chart_name) or {}
                chart_img = chart.get('base64_image', '')
                chart_title = chart.get('title', chart_name.replace('_', ' ').title())

                if chart_img:
                    html_parts.append('''
                    <div class="chart-container full-width">
                        <h3>{title}</h3>
                        <img src="data:image/png;base64,{img}" alt="{title} 차트" class="performance-chart">
                    </div>
                    '''.format(title=chart_title, img=chart_img))

            if not html_parts:
                return '<div class="no-charts">생성된 차트가 없습니다.</div>'

            return '\n'.join(html_parts)

        except Exception as e:
            logger.error(f"나란히 배치 차트 HTML 생성 오류: {e}")
            return f'<div class="chart-error">차트 배치 오류: {str(e)}</div>'
    
    def save_html_report(self) -> str:
        """HTML 리포트 저장 (브라우저 열지 않음)"""
        try:
            html_content = self.generate_html_report()
            package_name = self.test_context.app_package_name or "unknown_package"
            
            # 기존 테스트 폴더 찾기 (가장 최근)
            import glob
            from src.config import MONKEY_LOG_DIR
            
            # 패키지명으로 폴더 검색 패턴
            folder_pattern = str(MONKEY_LOG_DIR / f"{package_name}_*")
            matching_folders = glob.glob(folder_pattern)
            
            if matching_folders:
                # 가장 최근 폴더 선택 (폴더명에서 타임스탬프 기준)
                report_folder = Path(max(matching_folders))
                logger.info(f"기존 테스트 폴더 사용: {report_folder}")
            else:
                # 폴더가 없으면 새로 생성
                from src.config import create_test_report_folder
                report_folder = create_test_report_folder(package_name)
                logger.info(f"새 테스트 폴더 생성: {report_folder}")
            
            # HTML 파일 경로 설정 (패키지명 포함)
            safe_package_name = package_name.replace('.', '_') if package_name else "unknown_package"
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            report_filename = report_folder / f"monkey_test_report_{safe_package_name}_{timestamp}.html"
            
            with open(report_filename, "w", encoding="utf-8") as f:
                f.write(html_content)
            
            logger.info(f"HTML 리포트 저장 완료: {report_filename}")
            
            # 저장된 파일 경로 반환
            return str(report_filename)
            
        except Exception as e:
            logger.error(f"HTML 리포트 저장 실패: {e}")
            return ""

    def save_html_report_to_path(self, file_path: str) -> bool:
        """지정된 경로에 HTML 리포트 저장"""
        try:
            # HTML 내용 생성 (기존 메서드 사용)
            html_content = self.generate_html_report()
            
            # 지정된 경로에 HTML 파일 저장
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            
            logger.info(f"HTML 리포트 저장 완료: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"HTML 리포트 저장 실패: {e}")
            return False

    def save_and_open_html_report(self) -> str:
        """HTML 리포트 저장 및 열기 - 기존 테스트 폴더 사용"""
        html_path = self.save_html_report()
        if html_path:
            try:
                # 경로 정규화 및 브라우저에서 열기
                abs_path = os.path.abspath(html_path)
                file_url = f"file:///{abs_path.replace(os.sep, '/')}"
                
                logger.info(f"브라우저에서 HTML 리포트 열기 시도: {file_url}")
                
                # Windows에서 webbrowser.open() 개선
                import sys
                if sys.platform.startswith('win'):
                    # Windows에서는 기본 브라우저로 열기
                    try:
                        os.startfile(abs_path)
                        logger.info("✅ Windows 기본 브라우저로 HTML 리포트 열기 성공")
                    except Exception as e:
                        logger.warning(f"os.startfile 실패, webbrowser 사용: {e}")
                        webbrowser.open(file_url)
                else:
                    # 다른 OS에서는 webbrowser 사용
                    webbrowser.open(file_url)
                    
            except Exception as e:
                logger.error(f"브라우저에서 HTML 리포트 열기 실패: {e}")
                logger.info(f"수동으로 다음 파일을 열어주세요: {html_path}")
                
        return html_path
    
    def generate_excel_report(self, file_path: str) -> bool:
        """엑셀 리포트 생성"""
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill
            
            wb = Workbook()
            ws = wb.active
            if ws is None:
                return False
                
            ws.title = "Monkey Test Report"  # type: ignore
            
            # 헤더 스타일
            header_font = Font(bold=True)
            header_fill = PatternFill(start_color="E0E0E0", end_color="E0E0E0", fill_type="solid")
            
            # 요약 정보
            ws.append(["Monkey 테스트 요약"])  # type: ignore
            ws.append([])  # type: ignore
            
            summary = self.test_context.current_test_report.get("summary", {})
            
            # 기본 요약 정보 표시
            summary_items = [
                ("Test target", summary.get('test_target', 'N/A')),
                ("Test tool", summary.get('test_tool', 'Android Monkey')),
                ("Test period", summary.get('test_period', 'N/A')),
                ("Test start time", summary.get('test_start_time', 'N/A')),
                ("Preset", summary.get('preset', 'N/A')),
                ("Total events", summary.get('total_events', 'N/A')),
                ("Device", summary.get('device', 'N/A')),
                ("Connection mode", summary.get('connection_mode', 'N/A')),
                ("Result summary", summary.get('result_summary', 'N/A')),
                ("Execution time", summary.get('execution_time', 'N/A')),
                ("Seed", getattr(self.test_context, 'seed', 'N/A')),
                ("Events per repeat", getattr(self.test_context, 'events', 'N/A')),
                ("Total repeats", getattr(self.test_context, 'repeats', 'N/A')),
                ("Throttle (ms)", getattr(self.test_context, 'throttle', 'N/A'))
            ]
            
            for key, value in summary_items:
                ws.append([key, value])  # type: ignore
            
            ws.append([])  # type: ignore
            
            # 상세 결과
            headers = ["반복", "실행시간", "이벤트수", "Crash", "ANR", "메모리피크", "CPU피크"]
            ws.append(headers)  # type: ignore
            
            # 헤더 스타일 적용
            for col_num, _ in enumerate(headers, 1):
                cell = ws.cell(row=ws.max_row, column=col_num)  # type: ignore
                cell.font = header_font  # type: ignore
                cell.fill = header_fill  # type: ignore
            
            # 데이터 추가
            for detail in self.test_context.current_test_report.get("details", []):
                ws.append([  # type: ignore
                    detail.get("repeat", ""),
                    detail.get("time", ""),
                    detail.get("events", ""),
                    detail.get("crash", ""),
                    detail.get("anr", ""),
                    detail.get("mem_peak", ""),
                    detail.get("cpu_peak", "")
                ])
            
            # 이슈 섹션
            ws.append([])  # type: ignore
            ws.append(["개선 제안"])  # type: ignore
            for issue in self.test_context.current_test_report.get("issues", []):
                ws.append([issue])  # type: ignore
            
            # 성능 데이터 시트
            perf_ws = wb.create_sheet("Performance Data")  # type: ignore
            perf_headers = ["시간", "회차", "메모리(MB)", "CPU(%)"]
            perf_ws.append(perf_headers)  # type: ignore
            
            for col_num, _ in enumerate(perf_headers, 1):
                cell = perf_ws.cell(row=1, column=col_num)  # type: ignore
                cell.font = header_font  # type: ignore
                cell.fill = header_fill  # type: ignore
            
            # 성능 데이터 추가 (디버그 정보 포함)
            performance_data = self.test_context.current_performance_data
            logger.info(f"엑셀 리포트용 성능 데이터: {len(performance_data)}개")
            
            if performance_data:
                logger.info(f"성능 데이터 첫 번째 항목: {performance_data[0]}")
                
                for i, data in enumerate(performance_data):
                    # 데이터 검증
                    timestamp = data.get("timestamp", "")
                    run_num = data.get("run", "")
                    mem_mb = data.get("memory_mb", "")  # 올바른 키 사용
                    cpu_percent = data.get("cpu_percent", "")
                    
                    # 타임스탬프를 HH:MM 형식으로 변환
                    if isinstance(timestamp, str) and ":" in timestamp:
                        try:
                            # "HH:MM:SS" 또는 "YYYY-MM-DD HH:MM:SS" 형식 처리
                            if len(timestamp.split(":")) == 3:  # HH:MM:SS 형식
                                timestamp_parts = timestamp.split(":")
                                timestamp = f"{timestamp_parts[0]}:{timestamp_parts[1]}"
                            elif " " in timestamp and len(timestamp.split(" ")) == 2:  # YYYY-MM-DD HH:MM:SS 형식
                                date_part, time_part = timestamp.split(" ")
                                if ":" in time_part:
                                    time_parts = time_part.split(":")
                                    timestamp = f"{time_parts[0]}:{time_parts[1]}"
                        except Exception as e:
                            logger.warning(f"타임스탬프 변환 오류: {e}")
                    
                    perf_ws.append([timestamp, run_num, mem_mb, cpu_percent])  # type: ignore
                    
                    if i < 3:  # 첫 3개 항목만 로깅
                        logger.info(f"엑셀 성능 데이터 {i}: 시간={timestamp}, 회차={run_num}, 메모리={mem_mb}MB, CPU={cpu_percent}%")
            else:
                logger.warning("엑셀 리포트: 성능 데이터가 없습니다")
                # 빈 데이터 표시
                perf_ws.append(["데이터 없음", "N/A", "N/A", "N/A"])  # type: ignore
            
            wb.save(file_path)  # type: ignore
            logger.info(f"엑셀 리포트 생성 완료: {file_path}")
            return True
            
        except ImportError:
            logger.error("openpyxl 라이브러리가 필요합니다. 'pip install openpyxl'로 설치해주세요.")
            return False
        except Exception as e:
            logger.error(f"엑셀 리포트 생성 실패: {e}")
            return False
    
    def _generate_chart_data(self) -> str:
        """Chart.js 데이터 생성"""
        logger.info(f"성능 데이터 차트 생성 시작 - 데이터 개수: {len(getattr(self.test_context, 'current_performance_data', []))}")
        
        if not hasattr(self.test_context, 'current_performance_data') or not self.test_context.current_performance_data:
            logger.warning("성능 데이터가 없어 차트를 생성하지 않습니다")
            return """
            // 성능 데이터가 없습니다
            console.log('⚠️  성능 데이터가 없어 차트를 생성하지 않습니다.');
            console.log('테스트 실행 중 성능 모니터링이 활성화되지 않았을 수 있습니다.');
            
            document.addEventListener('DOMContentLoaded', function() {
                const memoryChart = document.getElementById('memoryChart');
                const cpuChart = document.getElementById('cpuChart');
                const performanceSection = document.querySelector('.section h2');
                
                if (memoryChart) memoryChart.style.display = 'none';
                if (cpuChart) cpuChart.style.display = 'none';
                
                if (performanceSection && performanceSection.textContent.includes('성능 그래프')) {
                    performanceSection.innerHTML = '📊 성능 그래프 (데이터 없음)';
                    const noDataMsg = '<div style="text-align:center; padding:40px; background:#fff3cd; border-radius:8px; color:#856404;">'
                        + '<h3>📈 성능 데이터 없음</h3>'
                        + '<p>이 테스트 실행에서는 성능 모니터링 데이터가 수집되지 않았습니다.</p>'
                        + '<p><small>다음 테스트 시 성능 모니터링을 활성화해보세요.</small></p>'
                        + '</div>';
                    performanceSection.insertAdjacentHTML('afterend', noDataMsg);
                }
            });
            """
        
        # 성능 데이터 샘플 로깅
        if len(self.test_context.current_performance_data) > 0:
            sample = self.test_context.current_performance_data[0]
            logger.info(f"성능 데이터 샘플: {sample}")
        
        # 타임스탬프, 회차, 값 추출 및 가공
        import datetime as dt
        timestamps = []
        memory_values = []
        cpu_values = []
        run_labels = []
        
        # 데이터 정렬 (타임스탬프 순)
        sorted_data = sorted(self.test_context.current_performance_data, key=lambda x: x.get('timestamp', ''))
        logger.info(f"정렬된 성능 데이터 개수: {len(sorted_data)}")
        
        for data in sorted_data:
            ts = data.get('timestamp')
            run = data.get('run', '')
            if ts:
                # HH:MM:SS 포맷으로 변환
                try:
                    # 여러 타임스탬프 포맷 지원
                    if len(ts) > 8:  # YYYY-MM-DD HH:MM:SS 형식
                        tstr = dt.datetime.strptime(ts, '%Y-%m-%d %H:%M:%S').strftime('%H:%M:%S')
                    else:  # HH:MM:SS 형식
                        tstr = ts
                except Exception:
                    tstr = ts
                timestamps.append(f"'{tstr}'")
                memory_values.append(data.get('mem_mb', 0) or 0)
                cpu_values.append(data.get('cpu_percent', 0) or 0)
                run_labels.append(str(run))

        # 통계 계산
        def stat(values):
            if not values:
                return 0, 0, 0
            return min(values), max(values), round(sum(values)/len(values), 1)
            
        mem_min, mem_max, mem_avg = stat(memory_values)
        cpu_min, cpu_max, cpu_avg = stat(cpu_values)

        return f"""
        // 성능 데이터 디버깅 정보
        console.log('성능 데이터 개수: {len(sorted_data)}');
        console.log('타임스탬프 개수: {len(timestamps)}');
        console.log('메모리 데이터 개수: {len(memory_values)}');
        console.log('CPU 데이터 개수: {len(cpu_values)}');
        console.log('메모리 통계 - 최소: {mem_min}MB, 최대: {mem_max}MB, 평균: {mem_avg}MB');
        console.log('CPU 통계 - 최소: {cpu_min}%, 최대: {cpu_max}%, 평균: {cpu_avg}%');
        
        // 성능 통계 정보 표시
        const statsHtml = '<div style="margin-bottom:15px; background:#f0f8ff; padding:15px; border-radius:8px; border-left:4px solid #2196F3;">'
            + '<h3 style="margin:0 0 10px 0; color:#1976D2;">📊 성능 데이터 요약</h3>'
            + '<div style="display:grid; grid-template-columns:1fr 1fr; gap:10px;">'
            + '<div><b>메모리(MB)</b><br>최소: {mem_min} | 최대: {mem_max} | 평균: {mem_avg}</div>'
            + '<div><b>CPU(%)</b><br>최소: {cpu_min} | 최대: {cpu_max} | 평균: {cpu_avg}</div>'
            + '</div>'
            + '<div style="margin-top:10px;"><small>📈 총 데이터 포인트: {len(sorted_data)}개</small></div>'
            + '</div>';
        
        const performanceSection = document.querySelector('.section h2');
        if (performanceSection && performanceSection.textContent.includes('성능 그래프')) {{
            performanceSection.insertAdjacentHTML('afterend', statsHtml);
        }}

        // 차트 생성이 실행되었는지 추적
        let chartsCreated = false;
        
        // 차트 생성 함수
        function createPerformanceCharts() {{
            if (chartsCreated) {{
                console.log('차트가 이미 생성되었습니다. 중복 실행 방지');
                return true;
            }}
            
            console.log('createPerformanceCharts 함수 시작');
            
            try {{
                // Chart.js 사용 가능 여부 확인
                if (typeof Chart === 'undefined') {{
                    console.error('Chart.js가 로드되지 않았습니다.');
                    showChartError('Chart.js 라이브러리가 로드되지 않았습니다. 인터넷 연결을 확인하세요.');
                    return false;
                }}
                
                // 메모리 차트 엘리먼트 확인
                const memoryCtx = document.getElementById('memoryChart');
                if (!memoryCtx) {{
                    console.error('memoryChart 엘리먼트를 찾을 수 없습니다.');
                    showChartError('차트 엘리먼트를 찾을 수 없습니다.');
                    return false;
                }}
                
                // CPU 차트 엘리먼트 확인
                const cpuCtx = document.getElementById('cpuChart');
                if (!cpuCtx) {{
                    console.error('cpuChart 엘리먼트를 찾을 수 없습니다.');
                    showChartError('차트 엘리먼트를 찾을 수 없습니다.');
                    return false;
                }}
                
                console.log('메모리 차트 생성 시작');
                const memoryChart = new Chart(memoryCtx.getContext('2d'), {{
                    type: 'line',
                    data: {{
                        labels: [{', '.join(timestamps)}],
                        datasets: [{{
                            label: '메모리 사용량 (MB)',
                            data: {memory_values},
                            borderColor: 'rgb(75, 192, 192)',
                            backgroundColor: 'rgba(75, 192, 192, 0.2)',
                            tension: 0.1,
                            pointRadius: 3,
                            pointHoverRadius: 6,
                            pointStyle: 'circle',
                            spanGaps: true,
                            fill: true
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            title: {{
                                display: true,
                                text: '메모리 사용량 추이',
                                font: {{ size: 16 }}
                            }},
                            legend: {{
                                display: true,
                                position: 'top'
                            }},
                            tooltip: {{
                                callbacks: {{
                                    label: function(context) {{
                                        let idx = context.dataIndex;
                                        return '메모리: ' + context.parsed.y + ' MB (회차: ' + {run_labels}[idx] + ')';
                                    }}
                                }}
                            }}
                        }},
                        scales: {{
                            x: {{
                                title: {{
                                    display: true,
                                    text: '시간'
                                }}
                            }},
                            y: {{
                                beginAtZero: true,
                                title: {{
                                    display: true,
                                    text: 'Memory (MB)'
                                }}
                            }}
                        }}
                    }}
                }});
                console.log('✅ 메모리 차트 생성 완료');
                
                console.log('CPU 차트 생성 시작');
                const cpuChart = new Chart(cpuCtx.getContext('2d'), {{
                    type: 'line',
                    data: {{
                        labels: [{', '.join(timestamps)}],
                        datasets: [{{
                            label: 'CPU 사용률 (%)',
                            data: {cpu_values},
                            borderColor: 'rgb(255, 99, 132)',
                            backgroundColor: 'rgba(255, 99, 132, 0.2)',
                            tension: 0.1,
                            pointRadius: 3,
                            pointHoverRadius: 6,
                            pointStyle: 'circle',
                            spanGaps: true,
                            fill: true
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            title: {{
                                display: true,
                                text: 'CPU 사용률 추이',
                                font: {{ size: 16 }}
                            }},
                            legend: {{
                                display: true,
                                position: 'top'
                            }},
                            tooltip: {{
                                callbacks: {{
                                    label: function(context) {{
                                        let idx = context.dataIndex;
                                        return 'CPU: ' + context.parsed.y + ' % (회차: ' + {run_labels}[idx] + ')';
                                    }}
                                }}
                            }}
                        }},
                        scales: {{
                            x: {{
                                title: {{
                                    display: true,
                                    text: '시간'
                                }}
                            }},
                            y: {{
                                beginAtZero: true,
                                max: Math.max(100, Math.max(...{cpu_values}) + 10),
                                title: {{
                                    display: true,
                                    text: 'CPU (%)'
                                }}
                            }}
                        }}
                    }}
                }});
                console.log('✅ CPU 차트 생성 완료');
                
                chartsCreated = true;
                console.log('✅ 모든 차트 생성 완료 - 메모리:', {len(memory_values)}개, 'CPU:', {len(cpu_values)}개 데이터 포인트');
                return true;
                
            }} catch (error) {{
                console.error('❌ 차트 생성 중 오류:', error);
                console.error('오류 상세:', error.stack);
                showChartError(error.message);
                return false;
            }}
        }}
        
        function showChartError(errorMsg) {{
            const performanceSection = document.querySelector('.section h2');
            if (performanceSection && performanceSection.textContent.includes('성능 그래프')) {{
                const errorDiv = document.createElement('div');
                errorDiv.style.cssText = 'text-align:center; padding:20px; background:#f8d7da; border-radius:8px; color:#721c24; margin:15px 0;';
                errorDiv.innerHTML = '<h4>⚠️ 차트 생성 오류</h4>' +
                    '<p>차트를 생성하는 중 오류가 발생했습니다: ' + (errorMsg || '알 수 없는 오류') + '</p>' +
                    '<p><small>브라우저 개발자 도구(F12)에서 자세한 오류 정보를 확인할 수 있습니다.</small></p>' +
                    '<p><small>인터넷 연결이 불안정하거나 Chart.js CDN에 접근할 수 없을 수 있습니다.</small></p>';
                performanceSection.insertAdjacentElement('afterend', errorDiv);
            }}
        }}
        
        // Chart.js 로드 확인 및 차트 생성 시작
        function initializeCharts() {{
            console.log('초기화 함수 실행 - Chart.js 상태:', typeof Chart !== 'undefined' ? '로드됨' : '로드되지 않음');
            
            if (typeof Chart !== 'undefined') {{
                console.log('Chart.js 이미 로드됨, 즉시 차트 생성');
                createPerformanceCharts();
            }} else {{
                console.log('Chart.js 로드 대기 중...');
                
                let attempts = 0;
                const maxAttempts = 50; // 5초 대기 (100ms * 50)
                
                const checkChartJs = setInterval(function() {{
                    attempts++;
                    console.log('Chart.js 로드 확인 시도:', attempts + '/' + maxAttempts);
                    
                    if (typeof Chart !== 'undefined') {{
                        console.log('Chart.js 로드 완료 (시도 ' + attempts + '), 차트 생성 시작');
                        clearInterval(checkChartJs);
                        createPerformanceCharts();
                    }} else if (attempts >= maxAttempts) {{
                        console.error('Chart.js 로드 타임아웃 (5초 초과)');
                        clearInterval(checkChartJs);
                        showChartError('Chart.js 라이브러리 로드 타임아웃. 인터넷 연결을 확인하세요.');
                    }}
                }}, 100); // 100ms마다 확인
            }}
        }}
        """
    
    def _generate_detail_rows(self, details: List[Dict[str, Any]]) -> str:
        """상세 결과 테이블 행 생성"""
        rows = ""
        for detail in details:
            rows += f"""
                <tr>
                    <td>{detail.get('repeat', '')}</td>
                    <td>{detail.get('time', '')}</td>
                    <td>{detail.get('seed', '')}</td>
                    <td>{detail.get('events', '')}</td>
                    <td>{detail.get('crash', '')}</td>
                    <td>{detail.get('anr', '')}</td>
                    <td>{detail.get('mem_peak', '')}</td>
                    <td>{detail.get('cpu_peak', '')}</td>
                </tr>"""
        return rows
    
    def _generate_issue_sections(self, issues: List[str]) -> str:
        """이슈 섹션 생성"""
        sections = ""
        for issue in issues:
            sections += f'<div class="issue">{issue}</div>\n'
        return sections
    
    def _get_html_template(self) -> str:
        """HTML 템플릿 반환"""
        return '''<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
        // 디버깅을 위한 로드 확인
        console.log('HTML 리포트 로드 시작');
        window.addEventListener('load', function() {{
            console.log('HTML 리포트 로드 완료');
            console.log('Chart.js 로드 상태:', typeof Chart !== 'undefined');
            
            // Chart.js 로드 확인
            if (typeof Chart === 'undefined') {{
                console.error('❌ Chart.js가 로드되지 않았습니다. 인터넷 연결을 확인하세요.');
                // Chart.js 로드 실패 시 대체 메시지 표시
                const chartContainers = document.querySelectorAll('.chart-container');
                chartContainers.forEach(container => {{
                    container.innerHTML = '<div style="text-align:center; padding:40px; background:#ffe6e6; border-radius:8px; color:#d32f2f;">' +
                        '<h3>📊 차트 로드 실패</h3>' +
                        '<p>Chart.js 라이브러리를 로드할 수 없습니다.</p>' +
                        '<p>인터넷 연결을 확인하고 페이지를 새로고침하세요.</p>' +
                        '</div>';
                }});
            }}
        }});
        
        // 네트워크 오류 처리
        window.addEventListener('error', function(e) {{
            if (e.filename && e.filename.includes('chart.js')) {{
                console.error('Chart.js 로드 오류:', e.message);
            }}
        }});
    </script>
    <style>
        body {{ 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            margin: 20px; 
            background: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .header {{ 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px; 
            border-radius: 10px; 
            margin-bottom: 30px; 
            text-align: center;
        }}
        .header h1 {{ margin: 0; font-size: 2.5em; }}
        .info-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .info-card {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }}
        .info-card h3 {{ 
            margin: 0 0 10px 0; 
            color: #2c3e50; 
            font-size: 1.1em;
        }}
        .info-card p {{ 
            margin: 5px 0; 
            color: #34495e;
        }}
        .section {{ 
            margin: 30px 0; 
            padding: 25px; 
            background: white; 
            border-radius: 8px; 
            box-shadow: 0 1px 5px rgba(0,0,0,0.05);
        }}
        .section h2 {{ 
            color: #2c3e50; 
            border-bottom: 2px solid #ecf0f1; 
            padding-bottom: 10px; 
            margin-bottom: 20px;
        }}
        
        /* 차트 관련 스타일 */
        .charts-row {{
            display: flex; 
            justify-content: space-between; 
            margin: 20px 0; 
            gap: 20px;
        }}
        .chart-container {{
            flex: 1; 
            text-align: center;
            background: #fff;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            border: 1px solid #e9ecef;
        }}
        .chart-container.full-width {{
            width: 100%;
            margin: 20px 0;
        }}
        .chart-container h3 {{
            color: #2c3e50; 
            margin-bottom: 15px;
            font-size: 1.3em;
            font-weight: 600;
            border-bottom: 2px solid #3498db;
            padding-bottom: 8px;
        }}
        .performance-chart {{
            max-width: 100%; 
            height: auto; 
            border: 1px solid #ddd; 
            border-radius: 8px; 
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            background: white;
        }}
        .chart-section {{
            margin: 30px 0; 
            text-align: center;
            background: #fff;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .performance-charts-section {{
            margin: 30px 0;
            padding: 25px;
            background: #f8f9fa;
            border-radius: 12px;
            border: 1px solid #e9ecef;
        }}
        .performance-charts-section h3 {{
            text-align: center; 
            margin: 20px 0; 
            color: #2c3e50; 
            font-size: 24px;
            font-weight: 700;
        }}
        .no-charts, .chart-error {{
            text-align: center;
            padding: 40px;
            color: #7f8c8d;
            background: #ecf0f1;
            border-radius: 8px;
            margin: 20px 0;
        }}
        .chart-error {{
            background: #ffe6e6;
            color: #d32f2f;
        }}
        
        /* 반응형 디자인 */
        @media (max-width: 768px) {{
            .charts-row {{
                flex-direction: column;
                gap: 15px;
            }}
            .chart-container {{
                margin-bottom: 20px;
            }}
            .container {{
                margin: 10px;
                padding: 15px;
            }}
            .header {{
                padding: 20px;
            }}
            .header h1 {{
                font-size: 2em;
            }}
            .info-grid {{
                grid-template-columns: 1fr;
                gap: 15px;
            }}
        }}
        
        @media (max-width: 480px) {{
            .performance-chart {{
                width: 100%;
                height: auto;
            }}
            .header h1 {{
                font-size: 1.5em;
            }}
        }}
        
        .section {{ 
            margin-bottom: 40px; 
            background: #fafafa;
            padding: 25px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }}
        .section h2 {{
            color: #333;
            margin-top: 0;
            font-size: 1.8em;
        }}
        table {{ 
            width: 100%; 
            border-collapse: collapse; 
            margin-bottom: 20px; 
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        th, td {{ 
            border: 1px solid #e0e0e0; 
            padding: 12px 8px; 
            text-align: center; 
        }}
        th {{ 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            font-weight: 600;
        }}
        tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        .issue {{ 
            background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%);
            border: 1px solid #ffeaa7; 
            padding: 15px; 
            margin: 10px 0; 
            border-radius: 8px;
            border-left: 4px solid #f39c12;
        }}
        .summary-stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            border-top: 3px solid #667eea;
        }}
        .stat-value {{
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
        }}
        .stat-label {{
            color: #666;
            margin-top: 5px;
        }}
        
        /* 성능 차트 스타일 */
        .performance-charts-section {{
            margin-top: 20px;
        }}
        .charts-row {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin: 20px 0;
        }}
        .chart-container {{
            background: white;
            margin: 20px 0;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            text-align: center;
        }}
        .chart-container.full-width {{
            grid-column: 1 / -1; /* 전체 너비 사용 */
        }}
        .chart-container h3 {{
            color: #333;
            margin-bottom: 15px;
            font-size: 1.2em;
        }}
        .performance-chart {{
            max-width: 100%;
            height: auto;
            border-radius: 4px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.2);
        }}
        .chart-placeholder {{
            background: #f8f9fa;
            padding: 40px;
            border-radius: 8px;
            color: #6c757d;
            font-style: italic;
        }}
        .chart-error {{
            background: #ffe6e6;
            padding: 20px;
            border-radius: 8px;
            color: #d32f2f;
            border-left: 4px solid #d32f2f;
        }}
        .no-charts {{
            background: #fff3cd;
            padding: 30px;
            border-radius: 8px;
            color: #856404;
            text-align: center;
            font-size: 1.1em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🐒 Android Monkey 테스트 리포트</h1>
            <div class="info-grid">
                <div class="info-item">
                    <strong>📱 테스트 대상:</strong> {test_target}
                </div>
                <div class="info-item">
                    <strong>📅 테스트 기간:</strong> {test_period}
                </div>
                <div class="info-item">
                    <strong>⚙️ 테스트 설정:</strong> {preset}
                </div>
                <div class="info-item">
                    <strong>📊 결과 요약:</strong> {result_summary}
                </div>
                <div class="info-item">
                    <strong>⏰ 수행 시간:</strong> {execution_time}
                </div>
                <div class="info-item">
                    <strong>📲 디바이스:</strong> {device}
                </div>
                <div class="info-item">
                    <strong>🔗 연결 방식:</strong> {connection_mode}
                </div>
            </div>
        </div>
        
        <div class="section">
            <h2> 상세 결과</h2>
            <table>
                <thead>
                    <tr>
                        <th>반복</th>
                        <th>실행시간</th>
                        <th>Seed</th>
                        <th>이벤트수</th>
                        <th>Crash</th>
                        <th>ANR</th>
                        <th>메모리피크</th>
                        <th>CPU피크</th>
                    </tr>
                </thead>
                <tbody>
                    {detail_rows}
                </tbody>
            </table>
        </div>
        
        <div class="section">
            <h2>🔍 이슈 및 개선 제안</h2>
            {issue_sections}
        </div>
        
        <div class="section">
            <h2>📊 성능 분석 차트</h2>
            {performance_charts}
        </div>
    </div>
    
    <script>
        console.log('HTML 리포트 로드 완료');
    </script>
</body>
</html>'''
