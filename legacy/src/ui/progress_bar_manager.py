#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""            self.progress_bar = ttk.Progressbar(
                progress_container,
                style="Green.Horizontal.TProgressbar",
                mode='determinate',
                length=300
            )행 프로그래스바 관리자
"""
import tkinter as tk
from tkinter import ttk
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class ProgressBarManager:
    """테스트 진행 프로그래스바 관리 클래스"""
    
    def __init__(self, parent):  # 타입 힌트 제거
        self.parent = parent
        self.progress_frame: Optional[ttk.Frame] = None
        self.progress_bar: Optional[ttk.Progressbar] = None
        self.progress_label: Optional[ttk.Label] = None
        self.current_value = 0
        self.max_value = 100
        self.is_visible = False
        
    def set_progress_frame(self, frame: ttk.Frame):
        """버튼 매니저에서 생성된 프로그래스 프레임을 설정하고 프로그래스바를 생성"""
        try:
            self.create_progress_bar(frame)
            logger.info("프로그래스 프레임 설정 완료")
        except Exception as e:
            logger.error(f"프로그래스 프레임 설정 실패: {e}")
        
    def create_progress_bar(self, container: ttk.Frame) -> ttk.Frame:
        """프로그래스바 위젯 생성"""
        try:
            # 프로그래스바 컨테이너 프레임 (버튼 사이에 배치)
            self.progress_frame = ttk.Frame(container)
            self.progress_frame.pack(side="left", padx=(10, 10))  # 버튼들 사이에 배치
            
            # 프로그래스바 라벨
            self.progress_label = ttk.Label(
                self.progress_frame, 
                text="테스트 대기 중...",
                font=("", 9)
            )
            self.progress_label.pack()  # 항상 표시
            
            # 프로그래스바 위젯 (녹색 스타일)
            style = ttk.Style()
            
            # 녹색 프로그래스바 스타일 설정
            style.theme_use('clam')  # 스타일 커스터마이징이 가능한 테마
            style.configure(
                "Green.Horizontal.TProgressbar",
                troughcolor='#E0E0E0',  # 배경색
                background='#4CAF50',   # 진행바 색상 (녹색)
                borderwidth=1,
                lightcolor='#4CAF50',
                darkcolor='#388E3C'
            )
            
            self.progress_bar = ttk.Progressbar(
                self.progress_frame,
                style="Green.Horizontal.TProgressbar",
                mode='determinate',
                length=200  # 버튼 사이 공간에 맞게 조정
            )
            self.progress_bar.pack()  # 항상 표시
            
            # 초기에는 프로그래스바와 라벨만 숨김 (프레임은 유지)
            self.reset_progress()
            
            logger.info("✅ 프로그래스바 위젯 생성 완료")
            return self.progress_frame
            
        except Exception as e:
            logger.error(f"프로그래스바 생성 실패: {e}")
            return ttk.Frame(container)  # 빈 프레임 반환
    
    def show_progress(self):
        """프로그래스바 표시 (항상 표시되므로 초기화만 수행)"""
        try:
            if self.progress_bar:
                self.progress_bar['value'] = 0
            if self.progress_label:
                self.progress_label.config(text="테스트 준비 중...")
            self.is_visible = True
            logger.debug("프로그래스바 초기화 완료")
        except Exception as e:
            logger.error(f"프로그래스바 초기화 실패: {e}")
    
    def hide_progress(self):
        """프로그래스바 완료 (항상 표시되므로 완료 상태로만 변경)"""
        try:
            if self.progress_bar:
                self.progress_bar['value'] = 100
            if self.progress_label:
                self.progress_label.config(text="테스트 완료!")
            logger.debug("프로그래스바 완료 상태로 변경")
        except Exception as e:
            logger.error(f"프로그래스바 완료 처리 실패: {e}")
    
    def start_progress(self, total_steps: int = 100, initial_text: str = "테스트 시작..."):
        """프로그래스바 시작"""
        try:
            self.max_value = total_steps
            self.current_value = 0
            
            if self.progress_bar:
                self.progress_bar.configure(maximum=total_steps, value=0)
            
            self.update_progress_text(initial_text)
            self.show_progress()
            
            logger.info(f"프로그래스바 시작: 총 {total_steps}단계")
            
        except Exception as e:
            logger.error(f"프로그래스바 시작 실패: {e}")
    
    def update_progress(self, current_step: int, status_text: str = ""):
        """프로그래스바 업데이트"""
        try:
            self.current_value = min(current_step, self.max_value)
            
            if self.progress_bar:
                self.progress_bar.configure(value=self.current_value)
            
            # 텍스트 업데이트
            if status_text:
                progress_percent = int((self.current_value / self.max_value) * 100) if self.max_value > 0 else 0
                display_text = f"{status_text} ({progress_percent}%)"
                self.update_progress_text(display_text)
            
            # UI 업데이트 강제 실행
            if self.progress_frame:
                self.progress_frame.update_idletasks()
            
            logger.debug(f"프로그래스바 업데이트: {self.current_value}/{self.max_value} - {status_text}")
            
        except Exception as e:
            logger.error(f"프로그래스바 업데이트 실패: {e}")
    
    def update_progress_text(self, text: str):
        """프로그래스바 텍스트 업데이트"""
        try:
            if self.progress_label:
                self.progress_label.configure(text=text)
        except Exception as e:
            logger.error(f"프로그래스바 텍스트 업데이트 실패: {e}")
    
    def set_indeterminate_mode(self, text: str = "처리 중..."):
        """불확정 모드로 설정 (애니메이션)"""
        try:
            if self.progress_bar:
                self.progress_bar.configure(mode='indeterminate')
                self.progress_bar.start(10)  # 10ms 간격으로 애니메이션
            
            self.update_progress_text(text)
            self.show_progress()
            
            logger.debug(f"프로그래스바 불확정 모드: {text}")
            
        except Exception as e:
            logger.error(f"불확정 모드 설정 실패: {e}")
    
    def set_determinate_mode(self):
        """확정 모드로 설정"""
        try:
            if self.progress_bar:
                self.progress_bar.stop()  # 애니메이션 중지
                self.progress_bar.configure(mode='determinate')
            
            logger.debug("프로그래스바 확정 모드로 변경")
            
        except Exception as e:
            logger.error(f"확정 모드 설정 실패: {e}")
    
    def complete_progress(self, completion_text: str = "테스트 완료!"):
        """프로그래스바 완료"""
        try:
            self.current_value = self.max_value
            
            if self.progress_bar:
                self.progress_bar.configure(value=self.max_value)
            
            self.update_progress_text(completion_text)
            
            logger.info(f"프로그래스바 완료: {completion_text}")
            
        except Exception as e:
            logger.error(f"프로그래스바 완료 처리 실패: {e}")
    
    def reset_progress(self):
        """프로그래스바 리셋"""
        try:
            self.current_value = 0
            self.max_value = 100
            
            if self.progress_bar:
                self.progress_bar.stop()  # 애니메이션 중지
                self.progress_bar.configure(mode='determinate', value=0, maximum=100)
            
            self.update_progress_text("테스트 대기 중...")
            
            logger.debug("프로그래스바 리셋 완료")
            
        except Exception as e:
            logger.error(f"프로그래스바 리셋 실패: {e}")
    
    def get_current_progress(self) -> tuple[int, int]:
        """현재 진행 상태 반환"""
        return self.current_value, self.max_value
    
    def is_progress_visible(self) -> bool:
        """프로그래스바 표시 상태 반환"""
        return self.is_visible
    
    def destroy(self):
        """프로그래스바 위젯 제거"""
        try:
            if self.progress_frame:
                self.progress_frame.destroy()
                self.progress_frame = None
                self.progress_bar = None
                self.progress_label = None
                self.is_visible = False
            
            logger.debug("프로그래스바 위젯 제거 완료")
            
        except Exception as e:
            logger.error(f"프로그래스바 제거 실패: {e}")
