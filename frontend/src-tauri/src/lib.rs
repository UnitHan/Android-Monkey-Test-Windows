//! Desktop shell: starts the Python REST backend from its venv, shows the web UI, stops the backend on exit.
//!
//! Backend location: `MONKEY_BACKEND_DIR` env var, else `<repo>/backend` (resolved from this crate's path).
//! Interpreter: `<backend>/.venv/Scripts/python.exe` (create it with `python backend/scripts/setup_venv.py`).

use std::net::{SocketAddr, TcpStream};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::Duration;

use tauri::{Manager, RunEvent};

const PORT: u16 = 8765;

struct Backend(Mutex<Option<Child>>);

fn backend_dir() -> PathBuf {
    std::env::var_os("MONKEY_BACKEND_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..").join("..").join("backend"))
}

fn venv_python(dir: &PathBuf) -> PathBuf {
    if cfg!(windows) {
        dir.join(".venv").join("Scripts").join("python.exe")
    } else {
        dir.join(".venv").join("bin").join("python")
    }
}

fn port_in_use() -> bool {
    let addr = SocketAddr::from(([127, 0, 0, 1], PORT));
    TcpStream::connect_timeout(&addr, Duration::from_millis(300)).is_ok()
}

fn spawn_backend() -> Option<Child> {
    if port_in_use() {
        eprintln!("[shell] backend already listening on {PORT}; reusing it");
        return None;
    }
    let dir = backend_dir();
    let python = venv_python(&dir);
    if !python.exists() {
        eprintln!(
            "[shell] venv python not found: {} (run: python backend/scripts/setup_venv.py)",
            python.display()
        );
        return None;
    }
    let mut cmd = Command::new(&python);
    cmd.args(["-m", "monkey_api.main"])
        .current_dir(&dir)
        .env("MONKEY_PORT", PORT.to_string())
        .env("PYTHONUNBUFFERED", "1");
    if cfg!(debug_assertions) {
        cmd.stdout(Stdio::inherit()).stderr(Stdio::inherit());
    } else {
        cmd.stdout(Stdio::null()).stderr(Stdio::null());
    }
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    match cmd.spawn() {
        Ok(child) => {
            eprintln!("[shell] backend started: pid {} ({})", child.id(), python.display());
            Some(child)
        }
        Err(err) => {
            eprintln!("[shell] failed to start backend: {err}");
            None
        }
    }
}

fn stop_backend(child: &mut Child) {
    #[cfg(windows)]
    {
        // kill the whole tree (uvicorn + adb monkey/logcat streams it spawned)
        use std::os::windows::process::CommandExt;
        let _ = Command::new("taskkill")
            .args(["/PID", &child.id().to_string(), "/T", "/F"])
            .creation_flags(0x0800_0000)
            .status();
    }
    let _ = child.kill();
    let _ = child.wait();
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .setup(|app| {
            app.manage(Backend(Mutex::new(spawn_backend())));
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    app.run(|handle, event| {
        if let RunEvent::Exit = event {
            if let Some(state) = handle.try_state::<Backend>() {
                if let Some(mut child) = state.0.lock().ok().and_then(|mut g| g.take()) {
                    stop_backend(&mut child);
                    eprintln!("[shell] backend stopped");
                }
            }
        }
    });
}
