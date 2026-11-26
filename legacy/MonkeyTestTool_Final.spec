# -*- mode: python ; coding: utf-8 -*-
"""
Monkey Test Tool - 최종 PyInstaller 스펙 파일
CMD 창 완전 숨김 및 최적화 설정
"""

# 필수 임포트 모듈 리스트 (완전한 의존성 포함)
hidden_imports = [
    # 핵심 모듈
    'src.core.adb_client',
    'src.core.monkey_runner', 
    'src.core.test_context',
    'src.core.report_generator',
    'src.core.performance_monitor',
    'src.core.network_monitor',
    'src.core.adaptive_tuner',
    'src.core.monkey_test_executor',
    'src.core.monkey_test_manager',
    
    # UI 모듈
    'src.ui.main_app',
    'src.ui.connection_wizard',
    'src.ui.progress_bar_manager',
    'src.ui.app_info_handler',
    'src.ui.chart_handler',
    'src.ui.package_handler', 
    'src.ui.test_handler',
    'src.ui.performance_graph_popup',
    'src.ui.button_manager',
    'src.ui.app_info_display',
    'src.ui.gui_builder',
    'src.ui.ui_helpers',
    'src.ui.ui_utils',
    'src.ui.alternative_app_selector',
    'src.ui.custom_seed_manager',
    'src.ui.preset_time_stats',
    
    # 유틸리티 모듈
    'src.utils.logger',
    'src.utils.chart_generator',
    'src.utils.performance_processor', 
    'src.utils.font_manager',
    'src.utils.subprocess_utils',
    'src.utils.app_foreground_monitor',
    'src.utils.gemini_adaptive_controller',
    'src.utils.app_info_fetcher',
    'src.utils.exe_utils',
    'src.utils.execution_timer',
    'src.utils.gui_utils',
    'src.utils.random_seed_generator',
    'src.utils.custom_font_setup',
    'src.utils.vc_redist_checker',
    
    # 설정
    'src.config',
    
    # PIL/Pillow
    'PIL',
    'PIL.Image',
    'PIL.ImageTk',
    'PIL._tkinter_finder',
    
    # Tkinter
    'tkinter',
    'tkinter.ttk',
    'tkinter.messagebox',
    'tkinter.filedialog',
    'tkinter.font',
    'tkinter.scrolledtext',
    '_tkinter',
    
    # 네트워킹
    'urllib3',
    'urllib3.util',
    'urllib3.util.retry',
    'urllib3.util.connection',
    'urllib3.exceptions',
    'requests',
    'requests.adapters',
    'requests.auth',
    'requests.cookies',
    'requests.exceptions',
    'requests.models',
    'requests.sessions',
    'requests.utils',
    'email.mime',
    'email.mime.text',
    'email.mime.multipart',
    'email.utils',
    'certifi',
    'charset_normalizer',
    'idna',
    
    # 웹 스크래핑
    'beautifulsoup4',
    'bs4',
    'bs4.builder',
    'google_play_scraper',
    
    # 파일 처리
    'openpyxl',
    'openpyxl.workbook',
    'openpyxl.worksheet', 
    'openpyxl.styles',
    'openpyxl.utils',
    
    # 시스템 모니터링
    'psutil',
    
    # 데이터 분석 및 시각화
    'matplotlib',
    'matplotlib.pyplot',
    'matplotlib.backends.backend_tkagg',
    'matplotlib.backends.backend_agg',
    'matplotlib.backends._backend_agg',
    'matplotlib.figure',
    'matplotlib.font_manager',
    'matplotlib._pylab_helpers',
    'matplotlib.dates',
    'matplotlib.ticker',
    'numpy',
    'numpy._core',
    'numpy._core.multiarray',
    'numpy._core.umath',
    'numpy._core.overrides',
    'numpy.linalg',
    'numpy.fft',
    'numpy.random',
    'numpy.ma',
    'pandas',
    'seaborn',
    
    # JSON 및 데이터
    'json',
    'csv',
    'sqlite3',
    'xml.etree.ElementTree',
    
    # 날짜/시간
    'datetime',
    'time',
    'calendar',
    
    # 시스템/OS
    'os',
    'sys',
    'platform',
    'subprocess',
    'threading',
    'multiprocessing',
    'queue',
    'io',
    'pathlib',
    'shutil',
    'tempfile',
    'glob',
    'fnmatch',
    
    # 정규표현식
    're',
    
    # 로깅
    'logging',
    'logging.handlers',
    
    # 암호화/해시
    'hashlib',
    'hmac',
    'base64',
    
    # 네트워크
    'socket',
    'ssl',
    'http.client',
    'urllib.parse',
    'urllib.request',
    'urllib.error',
]

# 제외할 모듈들 (용량 최적화)
excludes = [
    'PyQt5',
    'PyQt6', 
    'PySide2',
    'PySide6',
    'IPython',
    'jupyter',
    'pytest',
    'unittest',
    'test',
    'distutils',
    'setuptools',
    'pip',
    'wheel',
    'sphinx',
    'docutils',
]

# 데이터 파일들 포함
datas = [
    ('adb.exe', '.'),
    ('AdbWinApi.dll', '.'),
    ('AdbWinUsbApi.dll', '.'),
    ('icon.ico', '.'),
    ('icon.png', '.'),
    ('Gemini_logo.png', '.'),
    ('apps.json', '.'),      # 앱 정보 JSON 파일 포함
    ('src', 'src'),
    ('fonts', 'fonts'),     # 폰트 파일들 포함
]

# 바이너리 파일들
binaries = []

a = Analysis(
    ['monkey.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MonkeyTestTool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,             # strip 비활성화 (Windows에서 strip 명령어 없음)
    upx=False,              # UPX도 비활성화 (안전한 빌드)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # 콘솔 창 완전 숨김 (가장 중요!)
    disable_windowed_traceback=True,  # 오류 창 비활성화
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.ico'],      # 애플리케이션 아이콘
    version=None,
    uac_admin=False,        # 관리자 권한 불필요
    uac_uiaccess=False
)
