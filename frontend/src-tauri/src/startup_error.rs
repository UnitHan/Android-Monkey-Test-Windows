//! Startup failures must be visible even when the release executable has no console.
use std::fs::OpenOptions;
use std::io::Write;
use std::path::PathBuf;
use std::time::SystemTime;
#[cfg(windows)]
use windows::core::{w, PCWSTR};
#[cfg(windows)]
use windows::Win32::UI::WindowsAndMessaging::{MessageBoxW, MB_ICONERROR, MB_OK};

fn message(error: &str) -> String {
    format!(
        "Monkey 테스트 자동화를 시작하지 못했습니다.\n\n{error}\n\n\
         기존 앱이나 개발용 백엔드가 실행 중인지 확인해 주세요.\n\
         실행 중인 테스트가 있다면 종료하지 말고 기존 창을 사용해 주세요.\n\n\
         시작 진단 로그: %LOCALAPPDATA%\\MonkeyTest\\logs\\shell-startup.log\n\
         백엔드 로그: %LOCALAPPDATA%\\MonkeyTest\\logs\\backend-startup.log"
    )
}

fn log_failure(error: &str) {
    let Some(base) = std::env::var_os("LOCALAPPDATA") else {
        eprintln!("[shell] startup failed: {error}");
        return;
    };
    let directory = PathBuf::from(base).join("MonkeyTest/logs");
    let write = || -> std::io::Result<()> {
        std::fs::create_dir_all(&directory)?;
        let mut log = OpenOptions::new().create(true).append(true)
            .open(directory.join("shell-startup.log"))?;
        writeln!(log, "{:?} [shell] startup failed: {error}", SystemTime::now())
    };
    if let Err(cause) = write() {
        eprintln!("[shell] cannot write startup log: {cause}; startup failed: {error}");
    }
}

pub fn show(error: &str) {
    log_failure(error);
    let detail = message(error);
    #[cfg(windows)]
    {
        let text: Vec<u16> = detail.encode_utf16().chain(Some(0)).collect();
        unsafe {
            MessageBoxW(None, PCWSTR(text.as_ptr()), w!("Monkey 시작 오류"), MB_OK | MB_ICONERROR);
        }
    }
    #[cfg(not(windows))]
    eprintln!("{detail}");
}

#[cfg(test)]
mod tests {
    use super::message;

    #[test]
    fn startup_error_explains_cause_preserves_active_tests_and_points_to_logs() {
        let detail = message("8765 포트를 사용 중입니다.");
        assert!(detail.contains("8765 포트를 사용 중입니다."));
        assert!(detail.contains("실행 중인 테스트가 있다면 종료하지 말고"));
        assert!(detail.contains("shell-startup.log"));
        assert!(detail.contains("backend-startup.log"));
    }
}
