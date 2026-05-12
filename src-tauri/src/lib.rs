#[tauri::command]
fn api_base() -> &'static str {
    "http://127.0.0.1:8765"
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![api_base])
        .run(tauri::generate_context!())
        .expect("error while running ObsidianAI desktop shell");
}
