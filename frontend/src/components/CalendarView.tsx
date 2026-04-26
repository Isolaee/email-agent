import { useEffect, useState } from "react";
import { listEvents, deleteEvent, syncCalendar, type CalendarEvent } from "../api";
import { format, startOfMonth, endOfMonth, addMonths, subMonths, eachDayOfInterval, isSameDay, startOfWeek, endOfWeek, parseISO } from "date-fns";

export default function CalendarView() {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [month, setMonth] = useState(new Date());
  const [selectedDay, setSelectedDay] = useState<Date | null>(null);
  const [syncing, setSyncing] = useState(false);

  const load = async (m: Date) => {
    const start = startOfMonth(m).toISOString();
    const end = endOfMonth(m).toISOString();
    setEvents(await listEvents(start, end));
  };

  useEffect(() => { load(month); }, [month]);

  const handleSync = async () => {
    setSyncing(true);
    await syncCalendar();
    await load(month);
    setSyncing(false);
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this event?")) return;
    await deleteEvent(id);
    await load(month);
  };

  const calStart = startOfWeek(startOfMonth(month), { weekStartsOn: 1 });
  const calEnd = endOfWeek(endOfMonth(month), { weekStartsOn: 1 });
  const days = eachDayOfInterval({ start: calStart, end: calEnd });

  const eventsForDay = (day: Date) =>
    events.filter((e) => e.start_time && isSameDay(parseISO(e.start_time), day));

  const selectedEvents = selectedDay ? eventsForDay(selectedDay) : [];

  return (
    <div className="flex flex-1 overflow-hidden">
      {/* Calendar grid */}
      <div className="flex-1 flex flex-col p-4 overflow-hidden">
        {/* Nav */}
        <div className="flex items-center justify-between mb-4">
          <button onClick={() => setMonth(subMonths(month, 1))} className="text-gray-400 hover:text-gray-100 px-2">←</button>
          <h2 className="text-sm font-semibold">{format(month, "MMMM yyyy")}</h2>
          <button onClick={() => setMonth(addMonths(month, 1))} className="text-gray-400 hover:text-gray-100 px-2">→</button>
          <button
            onClick={handleSync}
            className="ml-4 text-xs px-3 py-1 bg-blue-600 hover:bg-blue-500 rounded-lg text-white"
            disabled={syncing}
          >
            {syncing ? "Syncing…" : "Sync"}
          </button>
        </div>

        {/* Weekday headers */}
        <div className="grid grid-cols-7 mb-1">
          {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
            <div key={d} className="text-center text-[10px] text-gray-600 py-1">{d}</div>
          ))}
        </div>

        {/* Day cells */}
        <div className="grid grid-cols-7 flex-1 overflow-hidden">
          {days.map((day) => {
            const dayEvents = eventsForDay(day);
            const isCurrentMonth = day.getMonth() === month.getMonth();
            const isSelected = selectedDay && isSameDay(day, selectedDay);
            const isToday = isSameDay(day, new Date());
            return (
              <button
                key={day.toISOString()}
                onClick={() => setSelectedDay(day)}
                className={`border border-gray-800/50 p-1 text-left overflow-hidden transition-colors ${
                  isSelected ? "bg-gray-800" : "hover:bg-gray-900"
                }`}
              >
                <span className={`text-xs block mb-1 w-5 h-5 flex items-center justify-center rounded-full ${
                  isToday ? "bg-blue-500 text-white" : isCurrentMonth ? "text-gray-300" : "text-gray-700"
                }`}>
                  {format(day, "d")}
                </span>
                {dayEvents.slice(0, 2).map((e) => (
                  <div key={e.id} className="text-[9px] bg-blue-900/60 text-blue-300 rounded px-0.5 truncate mb-0.5">
                    {e.title}
                  </div>
                ))}
                {dayEvents.length > 2 && (
                  <div className="text-[9px] text-gray-600">+{dayEvents.length - 2}</div>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Event detail panel */}
      <div className="w-72 border-l border-gray-800 p-4 overflow-y-auto">
        {selectedDay ? (
          <>
            <h3 className="text-sm font-semibold mb-3 text-gray-300">
              {format(selectedDay, "EEEE, MMMM d")}
            </h3>
            {selectedEvents.length === 0 ? (
              <p className="text-xs text-gray-600">No events</p>
            ) : (
              <div className="space-y-2">
                {selectedEvents.map((e) => (
                  <div key={e.id} className="bg-gray-900 rounded-lg p-3 border border-gray-800">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-100 mb-1">{e.title}</div>
                        {e.start_time && (
                          <div className="text-xs text-gray-500">
                            {format(parseISO(e.start_time), "HH:mm")}
                            {e.end_time && ` – ${format(parseISO(e.end_time), "HH:mm")}`}
                          </div>
                        )}
                        {e.location && <div className="text-xs text-gray-500 mt-0.5">📍 {e.location}</div>}
                        {e.description && <div className="text-xs text-gray-600 mt-1 line-clamp-3">{e.description}</div>}
                        {e.attendees.length > 0 && (
                          <div className="text-xs text-gray-600 mt-1">
                            👥 {e.attendees.slice(0, 3).join(", ")}
                            {e.attendees.length > 3 && ` +${e.attendees.length - 3}`}
                          </div>
                        )}
                      </div>
                      <button
                        onClick={() => handleDelete(e.id)}
                        className="text-gray-700 hover:text-red-400 text-sm shrink-0"
                        title="Delete event"
                      >
                        🗑
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        ) : (
          <p className="text-xs text-gray-600">Click a day to see events</p>
        )}
      </div>
    </div>
  );
}
