import type { Conversation } from "../api/client";

type Props = {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onCreate: () => void;
  onDelete: (id: string) => void;
  onLogout: () => void;
};

export default function Sidebar({ conversations, activeId, onSelect, onCreate, onDelete, onLogout }: Props) {
  return (
    <aside className="flex w-72 flex-col border-r bg-white">
      <button onClick={onCreate} className="m-3 rounded bg-blue-600 p-2 text-white">
        + Cuộc hội thoại mới
      </button>
      <ul className="flex-1 overflow-y-auto">
        {conversations.map((c) => (
          <li key={c.id}
            className={`group flex cursor-pointer items-center justify-between px-4 py-2 hover:bg-gray-100 ${
              c.id === activeId ? "bg-gray-100 font-medium" : ""}`}
            onClick={() => onSelect(c.id)}>
            <span className="truncate">{c.title}</span>
            <button className="hidden text-gray-400 hover:text-red-600 group-hover:block"
              title="Xóa hội thoại"
              onClick={(e) => { e.stopPropagation(); onDelete(c.id); }}>
              ✕
            </button>
          </li>
        ))}
      </ul>
      <button onClick={onLogout} className="m-3 text-sm text-gray-500 hover:underline">
        Đăng xuất
      </button>
    </aside>
  );
}
