//! Desktop shell with an owned, self-contained backend in release builds.
use std::process::Child;
use std::sync::Mutex;
use tauri::{Manager, RunEvent};

mod backend_runtime;
mod startup_error;
#[cfg(windows)]
mod reload_guard;

struct Backend(Mutex<Option<Child>>);

impl Drop for Backend {
    fn drop(&mut self) {
        if let Some(mut child) = self.0.get_mut().ok().and_then(|child| child.take()) {
            backend_runtime::stop(&mut child);
        }
    }
}

fn setup(app: &mut tauri::App) -> Result<(), Box<dyn std::error::Error>> {
    app.manage(Backend(Mutex::new(backend_runtime::spawn(app)?)));
    #[cfg(windows)]
    reload_guard::install(app)?;
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let result = tauri::Builder::default()
        .setup(|app| {
            // Tauri invokes setup inside its event loop, after Builder::build returns.
            // Returning Err here would panic in run(), bypassing build error handling.
            if let Err(error) = setup(app) {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.hide();
                }
                startup_error::show(&error.to_string());
                app.handle().exit(1);
            }
            Ok(())
        })
        .build(tauri::generate_context!());
    let app = match result {
        Ok(app) => app,
        Err(error) => {
            startup_error::show(&error.to_string());
            return;
        }
    };

    app.run(|handle, event| {
        if let RunEvent::Exit = event {
            if let Some(state) = handle.try_state::<Backend>() {
                if let Some(mut child) = state.0.lock().ok().and_then(|mut g| g.take()) {
                    backend_runtime::stop(&mut child);
                }
            }
        }
    });
}
