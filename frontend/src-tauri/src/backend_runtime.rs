//! Release: bundled executable. Development: repository virtual environment.
use std::fs::OpenOptions;
use std::io;
use std::net::{SocketAddr, TcpStream};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::time::{Duration, Instant};
use tauri::Manager;

const PORT: u16 = 8765;

fn listening() -> bool {
    TcpStream::connect_timeout(
        &SocketAddr::from(([127, 0, 0, 1], PORT)),
        Duration::from_millis(100),
    )
    .is_ok()
}

fn command(app: &tauri::App) -> io::Result<Command> {
    if cfg!(debug_assertions) {
        let dir = std::env::var_os("MONKEY_BACKEND_DIR")
            .map(PathBuf::from)
            .unwrap_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../backend"));
        let mut cmd = Command::new(dir.join(".venv/Scripts/python.exe"));
        cmd.args(["-m", "monkey_api.main"]).current_dir(dir);
        Ok(cmd)
    } else {
        let dir = app
            .path()
            .resource_dir()
            .map_err(io::Error::other)?
            .join("runtime/monkey-backend");
        let exe = dir.join("monkey-backend.exe");
        if !exe.is_file() {
            return Err(io::Error::new(
                io::ErrorKind::NotFound,
                "내장 백엔드가 없습니다. 설치 파일로 다시 설치해 주세요.",
            ));
        }
        let logs = std::env::var_os("LOCALAPPDATA")
            .map(PathBuf::from)
            .ok_or_else(|| io::Error::other("LOCALAPPDATA unavailable"))?
            .join("MonkeyTest/logs");
        std::fs::create_dir_all(&logs)?;
        let output = OpenOptions::new()
            .create(true)
            .append(true)
            .open(logs.join("backend-startup.log"))?;
        let mut cmd = Command::new(exe);
        cmd.current_dir(dir)
            .stdout(Stdio::from(output.try_clone()?))
            .stderr(Stdio::from(output));
        Ok(cmd)
    }
}

pub fn spawn(app: &tauri::App) -> io::Result<Option<Child>> {
    if listening() {
        if cfg!(debug_assertions) {
            return Ok(None);
        }
        return Err(io::Error::new(
            io::ErrorKind::AddrInUse,
            "8765 포트를 사용 중입니다. 기존 Monkey 앱/백엔드를 종료한 뒤 실행해 주세요.",
        ));
    }
    let mut cmd = command(app)?;
    cmd.env("MONKEY_PORT", PORT.to_string())
        .env("PYTHONUNBUFFERED", "1");
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x0800_0000);
    }
    let mut child = cmd.spawn()?;
    let deadline = Instant::now() + Duration::from_secs(30);
    while Instant::now() < deadline {
        if let Some(status) = child.try_wait()? {
            return Err(io::Error::other(format!(
                "백엔드 시작 실패 ({status}). MonkeyTest/logs/backend-startup.log를 확인해 주세요."
            )));
        }
        if listening() {
            return Ok(Some(child));
        }
        std::thread::sleep(Duration::from_millis(100));
    }
    stop(&mut child);
    Err(io::Error::new(
        io::ErrorKind::TimedOut,
        "백엔드 시작 대기 시간이 초과되었습니다.",
    ))
}

pub fn stop(child: &mut Child) {
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        let _ = Command::new("taskkill")
            .args(["/PID", &child.id().to_string(), "/T", "/F"])
            .creation_flags(0x0800_0000)
            .status();
    }
    let _ = child.kill();
    let _ = child.wait();
}
