import { useEffect, useState } from "react";
import { getEmail, type EmailDetail as TEmailDetail } from "../api";
import { format } from "date-fns";

interface Props {
  emailId: number;
  onClose: () => void;
}

export default function EmailDetail({ emailId, onClose }: Props) {
  const [email, setEmail] = useState<TEmailDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getEmail(emailId).then((e) => { setEmail(e); setLoading(false); });
  }, [emailId]);

  if (loading) return <div className="flex items-center justify-center h-full text-gray-600 text-sm">Loading…</div>;
  if (!email) return null;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-800 bg-gray-900/50">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <h2 className="text-base font-semibold text-gray-100 mb-1">{email.subject || "(no subject)"}</h2>
            <div className="text-xs text-gray-400 space-y-0.5">
              <div><span className="text-gray-600">From:</span> {email.sender}</div>
              <div><span className="text-gray-600">To:</span> {email.recipients.join(", ")}</div>
              <div>
                <span className="text-gray-600">Date:</span>{" "}
                {email.date ? format(new Date(email.date), "PPpp") : "unknown"}
              </div>
              <div>
                <span className="text-gray-600">Account:</span>{" "}
                <span className="text-blue-400">{email.account_email}</span>
              </div>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-600 hover:text-gray-300 text-lg shrink-0">✕</button>
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        <pre className="text-sm text-gray-300 whitespace-pre-wrap font-sans leading-relaxed">
          {email.body_text || "(empty)"}
        </pre>
      </div>
    </div>
  );
}
