import type { View } from "../App";

interface Props {
  view: View;
  setView: (v: View) => void;
  chatOpen: boolean;
  setChatOpen: (open: boolean) => void;
}

const navItems: { id: View; label: string; icon: string }[] = [
  { id: "inbox", label: "Inbox", icon: "✉" },
  { id: "calendar", label: "Calendar", icon: "📅" },
  { id: "auth", label: "Accounts", icon: "🔑" },
];

export default function Sidebar({ view, setView, chatOpen, setChatOpen }: Props) {
  return (
    <div className="w-14 bg-gray-900 border-r border-gray-800 flex flex-col items-center py-4 gap-1 shrink-0">
      <div className="text-blue-400 font-bold text-lg mb-4">EA</div>
      {navItems.map((item) => (
        <button
          key={item.id}
          title={item.label}
          onClick={() => setView(item.id)}
          className={`w-10 h-10 rounded-lg flex items-center justify-center text-lg transition-colors ${
            view === item.id ? "bg-blue-600 text-white" : "text-gray-400 hover:bg-gray-800"
          }`}
        >
          {item.icon}
        </button>
      ))}
      <div className="flex-1" />
      <button
        title="AI Assistant"
        onClick={() => setChatOpen(!chatOpen)}
        className={`w-10 h-10 rounded-lg flex items-center justify-center text-lg transition-colors ${
          chatOpen ? "bg-violet-600 text-white" : "text-gray-400 hover:bg-gray-800"
        }`}
      >
        🤖
      </button>
    </div>
  );
}
