import os
import re
import datetime

# Monkey 리포트 폴더 경로
REPORTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../monkey_reports'))

# 프리셋별 실제 측정값 집계
# { (events, repeats, throttle): [duration_seconds, ...] }
def collect_preset_time_stats():
    stats = {}
    for root, dirs, files in os.walk(REPORTS_DIR):
        for fname in files:
            if not fname.endswith('.log'):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, encoding='utf-8') as f:
                    lines = f.readlines()
                
                # Monkey 시작/종료 라인 찾기
                start_time, end_time = None, None
                events, seed, throttle = None, None, None
                
                for line in lines:
                    # Monkey 시작 패턴: :Monkey: seed=1111 count=3000
                    m = re.search(r':Monkey: seed=(\d+) count=(\d+)', line)
                    if m:
                        seed = int(m.group(1))
                        events = int(m.group(2))
                    
                    # Throttle 패턴
                    m2 = re.search(r'-throttle (\d+)', line)
                    if m2:
                        throttle = int(m2.group(1))
                    
                    # 시작 시각 (첫 번째 타임스탬프)
                    m3 = re.match(r'^(\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                    if m3 and start_time is None and ':Monkey: seed=' in line:
                        start_time = m3.group(1)
                    
                    # 종료 시각 (Monkey finished)
                    if '// Monkey finished' in line:
                        m4 = re.match(r'^(\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                        if m4:
                            end_time = m4.group(1)
                
                if events and throttle and start_time and end_time:
                    # 시간 파싱 (MM-DD HH:MM:SS)
                    try:
                        t1 = datetime.datetime.strptime(start_time, '%m-%d %H:%M:%S')
                        t2 = datetime.datetime.strptime(end_time, '%m-%d %H:%M:%S')
                        
                        # 날짜가 넘어가면 보정
                        if t2 < t1:
                            t2 += datetime.timedelta(days=1)
                            
                        duration = (t2 - t1).total_seconds()
                        
                        # 단일 실행 시간 저장 (반복 횟수는 별도 처리)
                        key = (events, throttle)
                        stats.setdefault(key, []).append(duration)
                        
                    except ValueError:
                        continue
                        
            except Exception:
                continue
    return stats

def get_recommended_time(events, throttle, repeats=1):
    """실측 데이터 기반 추천 시간 계산"""
    stats = collect_preset_time_stats()
    key = (events, throttle)
    
    # 실측 데이터가 있으면 사용
    if key in stats and stats[key]:
        # 평균 단일 실행 시간
        avg_single = sum(stats[key]) / len(stats[key])
        # 반복 횟수 적용
        total_avg = avg_single * repeats
        
        total_minutes = int(total_avg // 60)
        total_seconds = int(total_avg % 60)
        
        if total_minutes == 0:
            return f"실측 약 {total_seconds}초"
        elif total_minutes < 60:
            return f"실측 약 {total_minutes}분"
        else:
            hours = total_minutes // 60
            minutes = total_minutes % 60
            if minutes == 0:
                return f"실측 약 {hours}시간"
            else:
                return f"실측 약 {hours}시간 {minutes}분"
    
    # 실측 데이터가 없으면 Smoke Test 기준으로 추정
    # Smoke Test: 3000 events, throttle 300ms, 5회 반복 = 40분 (실측)
    smoke_events = 3000
    smoke_throttle = 300
    smoke_repeats = 5
    smoke_time_minutes = 40
    
    # 단위 시간 계산 (이벤트당 시간)
    smoke_total_events = smoke_events * smoke_repeats
    time_per_event = smoke_time_minutes / smoke_total_events  # 분/이벤트
    
    # throttle 보정 계수 (throttle이 작을수록 빨라짐)
    throttle_factor = throttle / smoke_throttle
    
    # 예상 시간 계산
    total_events = events * repeats
    estimated_minutes = int(total_events * time_per_event * throttle_factor)
    
    if estimated_minutes < 60:
        return f"예상 약 {estimated_minutes}분"
    else:
        hours = estimated_minutes // 60
        minutes = estimated_minutes % 60
        if minutes == 0:
            return f"예상 약 {hours}시간"
        else:
            return f"예상 약 {hours}시간 {minutes}분"
