import { useEffect, useRef, useState } from "react";
import { api, sendMessage, type ChatMessage } from "../api/client";
import MessageBubble from "./MessageBubble";

const TOOL_LABELS: Record<string, string> = {
  billing_agent: "Đang hỏi chuyên viên billing…",
  tech_support_agent: "Đang hỏi chuyên viên kỹ thuật…",
};

type Props = { conversationId: string; onTurnComplete: () => void };

export default function ChatPane({ conversationId, onTurnComplete }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [activity, setActivity] = useState<string[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.getMessages(conversationId).then(setMessages);
  }, [conversationId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, activity]);

  const appendToLast = (text: string) =>
    setMessages((prev) => {
      const copy = [...prev];
      const last = copy[copy.length - 1];
      copy[copy.length - 1] = { ...last, content: last.content + text };
      return copy;
    });

  // The orchestrator may write an intro before calling an agent; split paragraphs like reloaded history
  const breakParagraph = () =>
    setMessages((prev) => {
      const last = prev[prev.length - 1];
      if (!last.content || last.content.endsWith("\n\n")) return prev;
      return [...prev.slice(0, -1), { ...last, content: last.content + "\n\n" }];
    });

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setBusy(true);
    setActivity([]);
    setMessages((prev) => [...prev, { role: "user", content: text }, { role: "assistant", content: "" }]);

    await sendMessage(conversationId, text, {
      onToken: appendToLast,
      onToolStart: (tool) => {
        breakParagraph();
        setActivity((prev) => [...prev, TOOL_LABELS[tool] ?? `Đang chạy ${tool}…`]);
      },
      onDone: onTurnComplete,
      onError: (msg) => appendToLast(`\n\n⚠️ ${msg}`),
    });

    setBusy(false);
    setActivity([]);
  };

  const last = messages[messages.length - 1];
  const waiting = busy && activity.length === 0 && last?.content === "";

  return (
    <main className="flex flex-1 flex-col">
      <div className="flex-1 space-y-3 overflow-y-auto p-6">
        {messages.map((m, i) =>
          m.content ? <MessageBubble key={i} message={m} /> : null)}
        {waiting && <p className="text-sm italic text-gray-500">Đang suy nghĩ…</p>}
        {busy && activity.map((a, i) => (
          <p key={i} className="text-sm italic text-gray-500">{a}</p>
        ))}
        <div ref={bottomRef} />
      </div>
      <div className="flex gap-2 border-t bg-white p-4">
        <textarea
          className="flex-1 resize-none rounded border p-2"
          rows={2}
          value={input}
          disabled={busy}
          placeholder="Nhập câu hỏi…"
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(); }
          }}
        />
        <button onClick={send} disabled={busy} className="rounded bg-blue-600 px-4 text-white disabled:opacity-50">
          Gửi
        </button>
      </div>
    </main>
  );
}
