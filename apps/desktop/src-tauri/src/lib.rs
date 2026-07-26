use std::{collections::HashMap, path::PathBuf, process::Stdio, sync::Arc, time::Duration};

use serde::Serialize;
use serde_json::{json, Value};
use tauri::{AppHandle, Emitter, Manager, State};
use tauri_plugin_dialog::{DialogExt, FilePath};
use tokio::{
    io::{AsyncBufReadExt, AsyncWriteExt, BufReader},
    process::{ChildStdin, Command},
    sync::{oneshot, Mutex},
    time::timeout,
};
use uuid::Uuid;

const PROTOCOL_VERSION: u64 = 1;
const SECRET_SERVICE: &str = "RoundLens";
const SECRET_USER: &str = "openai-compatible-api-key";
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

type PendingMap = Arc<Mutex<HashMap<String, oneshot::Sender<Value>>>>;

#[derive(Debug, Serialize)]
struct CommandError {
    code: &'static str,
    message: String,
}

impl CommandError {
    fn new(code: &'static str, message: impl Into<String>) -> Self {
        Self {
            code,
            message: message.into(),
        }
    }
}

struct SidecarInner {
    stdin: Mutex<Option<ChildStdin>>,
    pending: PendingMap,
    start_lock: Mutex<()>,
}

#[derive(Clone)]
struct SidecarManager {
    inner: Arc<SidecarInner>,
}

impl SidecarManager {
    fn new() -> Self {
        Self {
            inner: Arc::new(SidecarInner {
                stdin: Mutex::new(None),
                pending: Arc::new(Mutex::new(HashMap::new())),
                start_lock: Mutex::new(()),
            }),
        }
    }

    async fn ensure_started(&self, app: &AppHandle) -> Result<(), CommandError> {
        if self.inner.stdin.lock().await.is_some() {
            return Ok(());
        }
        let _guard = self.inner.start_lock.lock().await;
        if self.inner.stdin.lock().await.is_some() {
            return Ok(());
        }
        let executable = sidecar_executable(app)?;
        let data_dir = app
            .path()
            .app_local_data_dir()
            .map_err(|error| CommandError::new("DATA_DIR_ERROR", error.to_string()))?;
        std::fs::create_dir_all(&data_dir)
            .map_err(|error| CommandError::new("DATA_DIR_ERROR", error.to_string()))?;

        let mut command = Command::new(&executable);
        command
            .arg("--data-dir")
            .arg(&data_dir)
            .env("PYTHONUTF8", "1")
            .env("PYTHONIOENCODING", "utf-8")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        #[cfg(windows)]
        command.creation_flags(CREATE_NO_WINDOW);
        let mut child = command.spawn().map_err(|error| {
            CommandError::new(
                "SIDECAR_START_FAILED",
                format!("无法启动本地分析服务：{error}"),
            )
        })?;
        let stdin = child
            .stdin
            .take()
            .ok_or_else(|| CommandError::new("SIDECAR_START_FAILED", "无法连接 Sidecar stdin"))?;
        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| CommandError::new("SIDECAR_START_FAILED", "无法连接 Sidecar stdout"))?;
        let stderr = child
            .stderr
            .take()
            .ok_or_else(|| CommandError::new("SIDECAR_START_FAILED", "无法连接 Sidecar stderr"))?;
        *self.inner.stdin.lock().await = Some(stdin);

        let pending = self.inner.pending.clone();
        let reader_app = app.clone();
        let manager = self.clone();
        tauri::async_runtime::spawn(async move {
            let mut lines = BufReader::new(stdout).lines();
            while let Ok(Some(line)) = lines.next_line().await {
                match parse_protocol_line(&line) {
                    Ok(message) => {
                        if let Some(id) = message.get("id").and_then(Value::as_str) {
                            if let Some(sender) = pending.lock().await.remove(id) {
                                let _ = sender.send(message);
                            }
                        } else if let Some(event) = message.get("event").and_then(Value::as_str) {
                            let payload = json!({
                                "event": event,
                                "data": message.get("data").cloned().unwrap_or_else(|| json!({}))
                            });
                            let _ = reader_app.emit("sidecar-event", payload);
                        }
                    }
                    Err(error) => tracing::error!("Invalid Sidecar protocol line: {}", error),
                }
            }
            *manager.inner.stdin.lock().await = None;
            let mut waiting = manager.inner.pending.lock().await;
            for (_, sender) in waiting.drain() {
                let _ = sender.send(json!({
                    "protocol_version": PROTOCOL_VERSION,
                    "error": {"code": "SIDECAR_CRASHED", "message": "本地分析服务已退出", "details": {}}
                }));
            }
            let _ = reader_app.emit(
                "sidecar-event",
                json!({"event": "sidecar.exited", "data": {}}),
            );
        });
        tauri::async_runtime::spawn(async move {
            let mut lines = BufReader::new(stderr).lines();
            while let Ok(Some(line)) = lines.next_line().await {
                tracing::warn!("sidecar: {}", redact_log(&line));
            }
        });
        tauri::async_runtime::spawn(async move {
            match child.wait().await {
                Ok(status) => tracing::info!("Sidecar exited with {status}"),
                Err(error) => tracing::error!("Sidecar wait failed: {error}"),
            }
        });
        Ok(())
    }

    async fn request(
        &self,
        app: &AppHandle,
        method: &str,
        params: Value,
    ) -> Result<Value, CommandError> {
        self.ensure_started(app).await?;
        let id = Uuid::new_v4().to_string();
        let request = json!({
            "protocol_version": PROTOCOL_VERSION,
            "id": id,
            "method": method,
            "params": params,
        });
        let (sender, receiver) = oneshot::channel();
        self.inner.pending.lock().await.insert(id.clone(), sender);
        let line = serde_json::to_vec(&request)
            .map_err(|error| CommandError::new("IPC_SERIALIZE_FAILED", error.to_string()))?;
        let write_result = async {
            let mut guard = self.inner.stdin.lock().await;
            let stdin = guard
                .as_mut()
                .ok_or_else(|| CommandError::new("SIDECAR_CRASHED", "Sidecar 未运行"))?;
            stdin
                .write_all(&line)
                .await
                .map_err(|error| CommandError::new("SIDECAR_CRASHED", error.to_string()))?;
            stdin
                .write_all(b"\n")
                .await
                .map_err(|error| CommandError::new("SIDECAR_CRASHED", error.to_string()))?;
            stdin
                .flush()
                .await
                .map_err(|error| CommandError::new("SIDECAR_CRASHED", error.to_string()))
        }
        .await;
        if let Err(error) = write_result {
            self.inner.pending.lock().await.remove(&id);
            *self.inner.stdin.lock().await = None;
            return Err(error);
        }
        match timeout(Duration::from_secs(130), receiver).await {
            Ok(Ok(response)) => Ok(response),
            Ok(Err(_)) => Err(CommandError::new(
                "SIDECAR_CRASHED",
                "Sidecar 响应通道已关闭",
            )),
            Err(_) => {
                self.inner.pending.lock().await.remove(&id);
                Err(CommandError::new("IPC_TIMEOUT", "本地分析请求超时"))
            }
        }
    }
}

fn parse_protocol_line(line: &str) -> Result<Value, &'static str> {
    let value: Value = serde_json::from_str(line).map_err(|_| "invalid JSON")?;
    if value.get("protocol_version").and_then(Value::as_u64) != Some(PROTOCOL_VERSION) {
        return Err("protocol version mismatch");
    }
    if value.get("id").is_none() && value.get("event").is_none() {
        return Err("message has neither id nor event");
    }
    Ok(value)
}

fn sidecar_executable(app: &AppHandle) -> Result<PathBuf, CommandError> {
    if let Some(configured) = std::env::var_os("ROUNDLENS_SIDECAR_PATH") {
        return validate_executable(PathBuf::from(configured));
    }
    let mut candidates = Vec::new();
    if cfg!(debug_assertions) {
        candidates.push(
            PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                .join("../../../.venv/Scripts/roundlens-analyzer.exe"),
        );
    }
    if let Ok(resource_dir) = app.path().resource_dir() {
        candidates.push(resource_dir.join("binaries/roundlens-analyzer/roundlens-analyzer.exe"));
        candidates.push(resource_dir.join("roundlens-analyzer/roundlens-analyzer.exe"));
    }
    for candidate in candidates {
        if candidate.is_file() {
            return Ok(candidate);
        }
    }
    Err(CommandError::new(
        "SIDECAR_NOT_FOUND",
        "未找到 RoundLens Python Sidecar；开发环境请先运行 uv sync",
    ))
}

fn validate_executable(path: PathBuf) -> Result<PathBuf, CommandError> {
    let canonical = path
        .canonicalize()
        .map_err(|_| CommandError::new("SIDECAR_NOT_FOUND", "配置的 Sidecar 路径不存在"))?;
    if !canonical.is_file() || canonical.extension().and_then(|item| item.to_str()) != Some("exe") {
        return Err(CommandError::new(
            "SIDECAR_NOT_FOUND",
            "Sidecar 必须是 .exe 文件",
        ));
    }
    Ok(canonical)
}

fn redact_log(line: &str) -> String {
    let mut output = line.to_owned();
    for marker in ["api_key", "authorization", "bearer", "secret", "token"] {
        if output.to_ascii_lowercase().contains(marker) {
            return "[REDACTED SENSITIVE LOG LINE]".to_string();
        }
    }
    if output.len() > 2_000 {
        output.truncate(2_000);
    }
    output
}

fn credential_entry() -> Result<keyring::Entry, CommandError> {
    keyring::Entry::new(SECRET_SERVICE, SECRET_USER)
        .map_err(|error| CommandError::new("SECRET_STORE_FAILED", error.to_string()))
}

fn read_api_key() -> Result<String, CommandError> {
    credential_entry()?
        .get_password()
        .map_err(|error| CommandError::new("LLM_NOT_CONFIGURED", error.to_string()))
}

#[tauri::command]
async fn sidecar_rpc(
    app: AppHandle,
    manager: State<'_, SidecarManager>,
    method: String,
    params: Value,
) -> Result<Value, CommandError> {
    const ALLOWED: &[&str] = &[
        "health",
        "initialize",
        "get_settings",
        "update_profile",
        "update_provider",
        "scan_demos",
        "import_demos",
        "list_demos",
        "parse_demo",
        "cancel_job",
        "list_jobs",
        "list_matches",
        "relink_demo",
        "create_analysis",
        "list_analyses",
        "get_analysis",
        "delete_report",
        "delete_match_data",
    ];
    if !ALLOWED.contains(&method.as_str()) {
        return Err(CommandError::new(
            "METHOD_NOT_ALLOWED",
            "前端无权调用该方法",
        ));
    }
    manager.request(&app, &method, params).await
}

#[tauri::command]
fn choose_demo_files(app: AppHandle) -> Result<Vec<String>, CommandError> {
    let files = app
        .dialog()
        .file()
        .add_filter("CS2 Demo", &["dem"])
        .blocking_pick_files()
        .unwrap_or_default();
    files.into_iter().map(file_path_to_string).collect()
}

#[tauri::command]
fn choose_directory(app: AppHandle) -> Result<Option<String>, CommandError> {
    app.dialog()
        .file()
        .blocking_pick_folder()
        .map(file_path_to_string)
        .transpose()
}

fn file_path_to_string(path: FilePath) -> Result<String, CommandError> {
    path.into_path()
        .map_err(|error| CommandError::new("INVALID_PATH", error.to_string()))
        .map(|path| path.to_string_lossy().into_owned())
}

#[tauri::command]
fn set_api_key(api_key: String) -> Result<(), CommandError> {
    if api_key.trim().len() < 8 {
        return Err(CommandError::new("SECRET_STORE_FAILED", "API Key 格式无效"));
    }
    credential_entry()?
        .set_password(api_key.trim())
        .map_err(|error| CommandError::new("SECRET_STORE_FAILED", error.to_string()))
}

#[tauri::command]
fn clear_api_key() -> Result<(), CommandError> {
    match credential_entry()?.delete_credential() {
        Ok(()) | Err(keyring::Error::NoEntry) => Ok(()),
        Err(error) => Err(CommandError::new("SECRET_STORE_FAILED", error.to_string())),
    }
}

#[tauri::command]
fn api_key_configured() -> bool {
    read_api_key().is_ok()
}

#[tauri::command]
async fn test_provider_connection(
    app: AppHandle,
    manager: State<'_, SidecarManager>,
) -> Result<Value, CommandError> {
    let api_key = read_api_key()?;
    manager
        .request(&app, "test_provider", json!({"api_key": api_key}))
        .await
}

#[tauri::command]
async fn generate_ai_report(
    app: AppHandle,
    manager: State<'_, SidecarManager>,
    analysis_id: String,
) -> Result<Value, CommandError> {
    let api_key = read_api_key()?;
    manager
        .request(
            &app,
            "generate_ai_report",
            json!({"analysis_id": analysis_id, "api_key": api_key}),
        )
        .await
}

pub fn run() {
    tracing_subscriber::fmt()
        .with_target(false)
        .with_writer(std::io::stderr)
        .init();
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(SidecarManager::new())
        .invoke_handler(tauri::generate_handler![
            sidecar_rpc,
            choose_demo_files,
            choose_directory,
            set_api_key,
            clear_api_key,
            api_key_configured,
            test_provider_connection,
            generate_ai_report,
        ])
        .run(tauri::generate_context!())
        .expect("error while running RoundLens");
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::Path;

    #[test]
    fn parses_protocol_response_and_event() {
        assert!(parse_protocol_line(r#"{"protocol_version":1,"id":"a","result":{}}"#).is_ok());
        assert!(parse_protocol_line(r#"{"protocol_version":1,"event":"ready","data":{}}"#).is_ok());
        assert!(parse_protocol_line(r#"{"protocol_version":2,"id":"a"}"#).is_err());
    }

    #[test]
    fn redacts_secret_like_log_lines() {
        assert_eq!(
            redact_log("Authorization: Bearer secret"),
            "[REDACTED SENSITIVE LOG LINE]"
        );
        assert_eq!(redact_log("parser started"), "parser started");
    }

    #[test]
    fn validates_executable_extension() {
        let path = Path::new("sidecar.py");
        assert_ne!(path.extension().and_then(|item| item.to_str()), Some("exe"));
    }
}
