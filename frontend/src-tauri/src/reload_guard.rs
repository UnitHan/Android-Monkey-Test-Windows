//! Handle browser reload accelerators even when a sandboxed report iframe has focus.
use tauri::Manager;
use webview2_com::AcceleratorKeyPressedEventHandler;
use windows::Win32::UI::Input::KeyboardAndMouse::{GetKeyState, VK_CONTROL, VK_F5};

pub fn install(app: &tauri::App) -> tauri::Result<()> {
    if let Some(window) = app.get_webview_window("main") {
        window.with_webview(|webview| unsafe {
            let handler = AcceleratorKeyPressedEventHandler::create(Box::new(|_, args| {
                if let Some(args) = args {
                    let mut key = 0;
                    args.VirtualKey(&mut key)?;
                    if key == u32::from(VK_F5.0)
                        || (key == u32::from(b'R') && GetKeyState(i32::from(VK_CONTROL.0)) < 0)
                    {
                        args.SetHandled(true)?;
                    }
                }
                Ok(())
            }));
            let mut token = 0;
            // The controller owns the handler until the webview is destroyed.
            if let Err(error) = webview
                .controller()
                .add_AcceleratorKeyPressed(&handler, &mut token)
            {
                eprintln!("[shell] reload shortcut guard failed: {error}");
            }
        })?;
    }
    Ok(())
}
