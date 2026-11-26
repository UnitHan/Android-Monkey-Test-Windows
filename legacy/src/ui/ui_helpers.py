#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UI 헬퍼 함수들
main_app.py에서 분리된 UI 관련 유틸리티 함수들
"""
import logging
import logging.handlers
import queue
import time
import tkinter as tk
from tkinter import filedialog
from src.utils.gui_utils import messagebox

logger = logging.getLogger(__name__)

class UIHelpers:
    """UI 관련 헬퍼 함수들을 담당하는 클래스"""
    
    def __init__(self, main_app):
        self.main_app = main_app
        self.running = True  # 로그 처리 상태 플래그
        self.after_id = None  # after 작업 ID 저장
    
    def setup_logging(self):
        """로깅 설정"""
        # 큐 핸들러 설정
        queue_handler = logging.handlers.QueueHandler(self.main_app.log_queue)
        
        # 루트 로거에 큐 핸들러 추가
        root_logger = logging.getLogger()
        root_logger.addHandler(queue_handler)
        
        # 큐에서 로그 메시지를 주기적으로 확인
        self.process_log_queue()
    
    def process_log_queue(self):
        """로그 큐에서 메시지를 처리하여 GUI에 표시"""
        if not self.running:
            return
            
        try:
            while True:
                record = self.main_app.log_queue.get_nowait()
                message = logging.getLogger().handlers[0].format(record)
                self.add_log_message(message)
        except queue.Empty:
            pass
        except Exception as e:
            print(f"로그 큐 처리 오류: {e}")
        finally:
            # 여전히 실행 중이고 main_app이 유효한 경우에만 다시 스케줄링
            if self.running and hasattr(self.main_app, 'after'):
                try:
                    # 위젯이 아직 존재하는지 확인
                    if hasattr(self.main_app, 'winfo_exists') and self.main_app.winfo_exists():
                        self.after_id = self.main_app.after(100, self.process_log_queue)
                    else:
                        self.running = False
                except tk.TclError:
                    # 위젯이 이미 삭제된 경우
                    self.running = False
    
    def add_log_message(self, message):
        """로그 메시지를 GUI에 추가"""
        if not self.running:
            return
            
        try:
            # 위젯이 아직 존재하는지 확인
            if hasattr(self.main_app, 'log_text') and hasattr(self.main_app.log_text, 'insert'):
                self.main_app.log_text.insert(tk.END, f"{message}\n")
                self.main_app.log_text.see(tk.END)
                
                # 로그가 너무 많아지면 앞부분 삭제 (최근 1000줄만 유지)
                line_count = int(self.main_app.log_text.index('end-1c').split('.')[0])
                if line_count > 1000:
                    self.main_app.log_text.delete('1.0', f'{line_count-1000}.0')
        except (tk.TclError, AttributeError) as e:
            # 위젯이 삭제된 경우 로그 처리 중지
            self.running = False
        except Exception as e:
            print(f"로그 추가 오류: {e}")
    
    def clear_log(self):
        """로그 지우기"""
        self.main_app.log_text.delete(1.0, tk.END)
    
    def stop(self):
        """UI 헬퍼 정리 - 백그라운드 작업 중지"""
        self.running = False
        if self.after_id:
            try:
                self.main_app.after_cancel(self.after_id)
            except (tk.TclError, AttributeError):
                pass
            self.after_id = None
    
    def save_log(self):
        """로그 저장"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("텍스트 파일", "*.txt"), ("모든 파일", "*.*")]
            )
            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.main_app.log_text.get(1.0, tk.END))
                messagebox.showinfo("저장 완료", f"로그가 저장되었습니다: {filename}")
        except Exception as e:
            messagebox.showerror("저장 오류", f"로그 저장 중 오류가 발생했습니다: {e}")
    
    def export_results(self):
        """결과 내보내기"""
        try:
            if not hasattr(self.main_app, 'test_context') or not self.main_app.test_context:
                messagebox.showwarning("내보내기 오류", "내보낼 테스트 결과가 없습니다.")
                return
            
            filename = filedialog.asksaveasfilename(
                defaultextension=".html",
                filetypes=[("HTML 파일", "*.html"), ("모든 파일", "*.*")]
            )
            
            if filename:
                # HTML 리포트 생성 (여기서는 간단한 구현)
                self._generate_html_report(filename)
                messagebox.showinfo("내보내기 완료", f"결과가 내보내기되었습니다: {filename}")
                
        except Exception as e:
            logger.error(f"결과 내보내기 오류: {e}")
            messagebox.showerror("내보내기 오류", f"결과 내보내기 중 오류가 발생했습니다: {e}")
    
    def _generate_html_report(self, filename):
        """HTML 리포트 생성"""
        try:
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Monkey Test Report</title>
                <style>
                    body {{ font-family: Noto Sans KR, sans-serif; margin: 20px; }}
                    .header {{ background-color: #f0f0f0; padding: 10px; }}
                    .content {{ margin: 20px 0; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>🐒 Monkey Test Report</h1>
                    <p>패키지: {self.main_app.test_context.package_name if self.main_app.test_context else 'Unknown'}</p>
                </div>
                <div class="content">
                    <p>테스트 완료 시간: {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
                    <p>이 리포트는 기본 템플릿입니다.</p>
                </div>
            </body>
            </html>
            """
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(html_content)
                
        except Exception as e:
            logger.error(f"HTML 리포트 생성 오류: {e}")
            raise
    
    def safe_method_call_wrapper(self, method_name):
        """메서드 호출을 안전하게 래핑"""
        def wrapper():
            try:
                if hasattr(self.main_app, method_name):
                    method = getattr(self.main_app, method_name)
                    method()
                elif hasattr(self.main_app.package_handler, method_name):
                    method = getattr(self.main_app.package_handler, method_name)
                    method()
                elif hasattr(self.main_app.test_handler, method_name):
                    method = getattr(self.main_app.test_handler, method_name)
                    method()
                elif hasattr(self, method_name):
                    method = getattr(self, method_name)
                    method()
                else:
                    logger.error(f"메서드를 찾을 수 없음: {method_name}")
            except Exception as e:
                logger.error(f"메서드 실행 오류 ({method_name}): {e}")
                logger.exception(f"상세 오류 ({method_name}):")
        return wrapper
