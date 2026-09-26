import { useCallback, useEffect, useState } from "react";
import { api, hasToken, setToken, type Conversation } from "./api/client";
import Login from "./components/Login";
import Sidebar from "./components/Sidebar";
import ChatPane from "./components/ChatPane";

export default function App() {
  const [loggedIn, setLoggedIn] = useState(hasToken());
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setConversations(await api.listConversations());
  }, []);

  useEffect(() => {
    if (loggedIn) refresh();
  }, [loggedIn, refresh]);

  if (!loggedIn) return <Login onSuccess={() => setLoggedIn(true)} />;

  return (
    <div className="flex h-screen bg-gray-50 text-gray-900">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        onSelect={setActiveId}
        onCreate={async () => {
          const c = await api.createConversation();
          await refresh();
          setActiveId(c.id);
        }}
        onDelete={async (id) => {
          await api.deleteConversation(id);
          if (id === activeId) setActiveId(null);
          await refresh();
        }}
        onLogout={() => {
          setToken("");
          setConversations([]);
          setActiveId(null);
          setLoggedIn(false);
        }}
      />
      {activeId ? (
        <ChatPane key={activeId} conversationId={activeId} onTurnComplete={refresh} />
      ) : (
        <div className="flex flex-1 items-center justify-center text-gray-400">
          Select or create a conversation
        </div>
      )}
    </div>
  );
}
