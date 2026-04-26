import { useState } from "react";
import Sidebar from "./components/Sidebar";
import EmailList from "./components/EmailList";
import EmailDetail from "./components/EmailDetail";
import CalendarView from "./components/CalendarView";
import ChatPanel from "./components/ChatPanel";
import AuthSetup from "./components/AuthSetup";
import { useNotifications } from "./hooks/useNotifications";

export type View = "inbox" | "calendar" | "auth";

function App() {
  const [view, setView] = useState<View>("inbox");
  const [selectedEmailId, setSelectedEmailId] = useState<number | null>(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [emailRefreshKey, setEmailRefreshKey] = useState(0);

  useNotifications(() => setEmailRefreshKey((k) => k + 1));

  return (
    <div className="flex h-screen bg-gray-950 text-gray-100 overflow-hidden">
      <Sidebar view={view} setView={setView} chatOpen={chatOpen} setChatOpen={setChatOpen} />

      <div className="flex flex-1 overflow-hidden">
        {view === "inbox" && (
          <>
            <EmailList selectedId={selectedEmailId} onSelect={setSelectedEmailId} refreshKey={emailRefreshKey} />
            <div className="flex-1 overflow-hidden">
              {selectedEmailId ? (
                <EmailDetail emailId={selectedEmailId} onClose={() => setSelectedEmailId(null)} />
              ) : (
                <div className="flex items-center justify-center h-full text-gray-500 text-sm">
                  Select an email to read
                </div>
              )}
            </div>
          </>
        )}
        {view === "calendar" && <CalendarView />}
        {view === "auth" && <AuthSetup />}
      </div>

      {chatOpen && <ChatPanel onClose={() => setChatOpen(false)} />}
    </div>
  );
}

export default App;
