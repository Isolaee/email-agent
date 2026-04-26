import { useEffect } from "react";

const BASE = import.meta.env.VITE_API_URL ?? "";

interface NewEmailEvent {
  type: "new_email";
  subject: string;
  sender: string;
}

export function useNotifications(onNewEmail?: () => void) {
  useEffect(() => {
    if (!("Notification" in window)) return;

    if (Notification.permission === "default") {
      Notification.requestPermission();
    }

    const es = new EventSource(`${BASE}/api/events`);

    es.onmessage = (e) => {
      try {
        const data: NewEmailEvent = JSON.parse(e.data);
        if (data.type !== "new_email") return;

        if (Notification.permission === "granted") {
          new Notification(data.subject || "(no subject)", {
            body: data.sender,
            icon: "/favicon.ico",
            tag: "email-agent-new",
          });
        }

        onNewEmail?.();
      } catch {}
    };

    es.onerror = () => {
      // Browser will auto-reconnect; no action needed
    };

    return () => es.close();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}
