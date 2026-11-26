#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UI 유틸리티 함수들
"""
import tkinter as tk
from tkinter import ttk
from typing import Dict, Any, Callable, Optional

def create_labeled_entry(parent, label_text: str, var: tk.StringVar, width: int = 15, 
                        state: str = "normal") -> tuple[ttk.Label, ttk.Entry]:
    """라벨과 엔트리를 생성하여 반환"""
    label = ttk.Label(parent, text=label_text)
    entry = ttk.Entry(parent, textvariable=var, width=width, state=state)
    return label, entry

def create_section_frame(parent, title: str, padding: str = "10") -> ttk.LabelFrame:
    """섹션 프레임 생성"""
    frame = ttk.LabelFrame(parent, text=title, padding=padding)
    return frame

def create_preset_radiobutton(parent, preset_name: str, preset_config: Dict[str, Any], 
                             var: tk.StringVar, command: Callable, row: int, col: int) -> ttk.Radiobutton:
    """프리셋 라디오버튼 생성"""
    text = f"{preset_name}\n({preset_config['events']} events x {preset_config['repeats']}회)"
    rb = ttk.Radiobutton(
        parent, 
        text=text, 
        variable=var, 
        value=preset_name,
        command=command
    )
    rb.grid(row=row, column=col, sticky="w", padx=10, pady=2)
    return rb

def create_treeview_with_headers(parent, columns: tuple, headers: Dict[str, str]) -> ttk.Treeview:
    """헤더가 있는 Treeview 생성"""
    tree = ttk.Treeview(parent, columns=columns, show="headings")
    
    # 헤더 설정
    for col in columns:
        tree.heading(col, text=headers.get(col, col))
        tree.column(col, width=100, anchor="center")
    
    return tree

def safe_ui_update(root: tk.Tk, func: Callable, *args, **kwargs):
    """안전한 UI 업데이트를 위한 래퍼"""
    def wrapped_func():
        try:
            func(*args, **kwargs)
        except tk.TclError as e:
            # UI가 이미 파괴된 경우 무시
            if "invalid command name" not in str(e):
                print(f"UI 업데이트 오류: {e}")
        except Exception as e:
            print(f"UI 업데이트 중 예외 발생: {e}")
    
    try:
        root.after(0, wrapped_func)
    except tk.TclError:
        # 루트 위젯이 파괴된 경우
        pass

def calculate_estimated_time(events: int, repeats: int, throttle: int) -> str:
    """실제 테스트 결과 기반 시간 계산 (Smoke Test 3000x5회=30분 기준)"""
    try:
        # 실제 테스트 기준: Smoke Test (3000 events x 5 repeats) = 30분
        # 기준값: 1회당 평균 6분 (30분 ÷ 5회)
        base_minutes_per_repeat = 6.0
        
        # 이벤트 수에 따른 비례 계산
        # 3000 이벤트 기준으로 비례
        event_ratio = events / 3000.0
        
        # throttle 영향 계산 (throttle이 높을수록 시간 증가)
        # 기준 throttle: 300ms
        throttle_ratio = throttle / 300.0
        
        # 실제 소요 시간 계산
        minutes_per_repeat = base_minutes_per_repeat * event_ratio * throttle_ratio
        total_minutes = minutes_per_repeat * repeats
        
        # 사용자 친화적 형태로 변환
        if total_minutes < 60:
            return f"{int(total_minutes)}분"
        else:
            hours = int(total_minutes // 60)
            minutes = int(total_minutes % 60)
            if minutes == 0:
                return f"{hours}시간"
            else:
                return f"{hours}시간 {minutes}분"
    
    except Exception as e:
        print(f"시간 계산 오류: {e}")
        return "계산 불가"

def calculate_precise_duration(events: int, repeats: int, throttle: int) -> tuple[int, str]:
    """정밀한 지속 시간 계산 (초 단위 반환 + 설명)"""
    import datetime
    from src.config import TIME_OVERHEAD
    
    try:
        # 기본 계산 (실제 테스트 기반 보정)
        total_events = events * repeats
        effective_throttle = throttle * TIME_OVERHEAD["throttle_efficiency"]
        basic_event_time = total_events * effective_throttle / 1000
        
        # 오버헤드 계산
        per_repeat_overhead = (
            TIME_OVERHEAD["app_restart_per_repeat"] +
            TIME_OVERHEAD["logcat_setup"] +
            TIME_OVERHEAD["monkey_startup"] +
            TIME_OVERHEAD["performance_monitoring"] +
            TIME_OVERHEAD["cleanup_per_repeat"]
        )
        total_repeat_overhead = repeats * per_repeat_overhead
        final_overhead = TIME_OVERHEAD["final_report_generation"]
        
        # 총 시간 (버퍼 포함)
        base_time = basic_event_time + total_repeat_overhead + final_overhead
        buffer_time = base_time * TIME_OVERHEAD["buffer_percentage"]
        total_seconds = int(base_time + buffer_time)
        
        # 상세 설명
        breakdown = (
            f"이벤트 실행: {int(basic_event_time)}초 | "
            f"반복 오버헤드: {int(total_repeat_overhead)}초 | "
            f"최종 처리: {int(final_overhead)}초 | "
            f"버퍼: {int(buffer_time)}초"
        )
        
        return total_seconds, breakdown
    
    except Exception as e:
        return 0, f"계산 오류: {e}"

def configure_treeview_scrollbar(parent, treeview: ttk.Treeview) -> ttk.Scrollbar:
    """Treeview용 스크롤바 구성"""
    scrollbar = ttk.Scrollbar(parent, orient="vertical", command=treeview.yview)
    treeview.configure(yscrollcommand=scrollbar.set)
    return scrollbar

def create_button_frame(parent, buttons_config: list) -> ttk.Frame:
    """버튼 프레임 생성
    
    Args:
        parent: 부모 위젯
        buttons_config: [{"text": "버튼텍스트", "command": 콜백함수, "state": "normal"}, ...]
    """
    frame = ttk.Frame(parent)
    
    for config in buttons_config:
        btn = ttk.Button(
            frame,
            text=config["text"],
            command=config["command"],
            state=config.get("state", "normal")
        )
        btn.pack(side="left", padx=5)
    
    return frame
