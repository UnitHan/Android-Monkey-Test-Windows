//! Desktop shell with an owned, self-contained backend in release builds.
use std::process::Child;
use std::sync::Mutex;
use tauri::{Manager, RunEvent};

mod backend_runtime;
#[cfg(windows)]
mod reload_guard;

struct Backend(Mutex<Option<Child>>);

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .setup(|app| {
            app.manage(Backend(Mutex::new(backend_runtime::spawn(app)?)));
            #[cfg(windows)]
            reload_guard::install(app)?;
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

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
