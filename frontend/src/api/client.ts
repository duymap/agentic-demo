export type Conversation = { id: string; title: string; updated_at: string };
export type ChatMessage = { role: "user" | "assistant"; content: string };

let token = localStorage.getItem("token") ?? "";

export function setToken(value: string) {
  token = value;
  if (value) localStorage.setItem("token", value);
  else localStorage.removeItem("token");
}

export function hasToken() {
  return token !== "";
}

function handleUnauthorized(path: string) {
  // A 401 on /auth/login means a wrong password, not an expired token
  if (path === "/auth/login") return;
  setToken("");
  window.location.reload();
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...init.headers,
    },
  });
  if (res.status === 401) handleUnauthorized(path);
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return (res.status === 204 ? undefined : await res.json()) as T;
}

export const api = {
  login: (username: string, password: string) =>
    request<{ token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  listConversations: () => request<Conversation[]>("/conversations"),
  createConversation: () => request<Conversation>("/conversations", { method: "POST" }),
  getMessages: (id: string) => request<ChatMessage[]>(`/conversations/${id}/messages`),
  deleteConversation: (id: string) => request<void>(`/conversations/${id}`, { method: "DELETE" }),
};

export type StreamHandlers = {
  onToken: (text: string) => void;
  onToolStart: (tool: string) => void;
  onDone: () => void;
  onError: (message: string) => void;
};

export async function sendMessage(id: string, message: string, h: StreamHandlers) {
  let res: Response;
  try {
    res = await fetch(`/api/conversations/${id}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ message }),
    });
  } catch {
    h.onError("Không kết nối được server");
    return;
  }
  if (res.status === 401) handleUnauthorized("");
  if (!res.ok || !res.body) {
    h.onError(res.status === 409 ? "Đang xử lý tin nhắn trước, vui lòng đợi" : `Lỗi ${res.status}`);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finished = false;

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? ""; // the last frame may be incomplete
      for (const frame of frames) {
        const event = frame.match(/^event: (.*)$/m)?.[1];
        const data = JSON.parse(frame.match(/^data: (.*)$/m)?.[1] ?? "{}");
        if (event === "token") h.onToken(data.text);
        else if (event === "tool_start") h.onToolStart(data.tool);
        else if (event === "done") { finished = true; h.onDone(); }
        else if (event === "error") { finished = true; h.onError(data.message); }
      }
    }
  } catch {
    // network dropped mid-stream; handled below
  }
  if (!finished) h.onError("Mất kết nối tới server giữa chừng");
}
