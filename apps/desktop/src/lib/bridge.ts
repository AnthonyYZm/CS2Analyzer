import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";

interface RpcEnvelope<T> {
  protocol_version: number;
  result?: T;
  error?: { code: string; message: string; details?: Record<string, unknown> };
}

export function unwrapRpcEnvelope<T>(envelope: RpcEnvelope<T>): T {
  if (envelope.error) {
    throw new BridgeError(envelope.error.code, envelope.error.message);
  }
  if (envelope.result === undefined) {
    throw new BridgeError("INVALID_RESPONSE", "Sidecar returned no result");
  }
  return envelope.result;
}

export class BridgeError extends Error {
  constructor(public readonly code: string, message: string) {
    super(message);
  }
}

export async function rpc<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
  try {
    const envelope = await invoke<RpcEnvelope<T>>("sidecar_rpc", { method, params });
    return unwrapRpcEnvelope(envelope);
  } catch (error) {
    if (error instanceof BridgeError) throw error;
    throw new BridgeError(
      "SIDECAR_UNAVAILABLE",
      typeof error === "string" ? error : "桌面桥接不可用，请通过 Tauri 启动应用。",
    );
  }
}

export const chooseDemoFiles = () => invoke<string[]>("choose_demo_files");
export const chooseDirectory = () => invoke<string | null>("choose_directory");
export const setApiKey = (apiKey: string) => invoke<void>("set_api_key", { apiKey });
export const clearApiKey = () => invoke<void>("clear_api_key");
export const secretStatus = () => invoke<boolean>("api_key_configured");
export const testProvider = async () =>
  unwrapRpcEnvelope(
    await invoke<RpcEnvelope<Record<string, unknown>>>("test_provider_connection"),
  );
export const generateAiReport = async <T>(analysisId: string) =>
  unwrapRpcEnvelope(
    await invoke<RpcEnvelope<{ analysis_id: string; report: T }>>("generate_ai_report", {
      analysisId,
    }),
  );

export async function onSidecarEvent(
  callback: (event: { event: string; data: Record<string, unknown> }) => void,
): Promise<UnlistenFn> {
  return listen("sidecar-event", (event) => callback(event.payload as any));
}
