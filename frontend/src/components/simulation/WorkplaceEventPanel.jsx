import { useState } from "react";
import { motion } from "framer-motion";
import EventResponseModal from "./EventResponseModal";

export default function WorkplaceEventPanel({ events, activeEvent, currentTask, onRespond, isResponding }) {
  const [respondingToEvent, setRespondingToEvent] = useState(null);
  if (!events || events.length === 0) {
    return (
      <div className="card h-full flex flex-col">
        <div className="p-4 border-b border-border">
          <h3 className="font-display text-xs font-semibold uppercase tracking-wide text-text-faint">
            Workplace Events
          </h3>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center text-text-muted p-4">
            <svg className="w-12 h-12 mx-auto mb-3 text-text-faint" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M18 10c0 3.866-3.582 7-8 7a8.841 8.841 0 01-4.083-.98L2 17l1.338-3.123C2.493 12.767 2 11.434 2 10c0-3.866 3.582-7 8-7s8 3.134 8 7z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M14 10h4m0 0v4m0-4h-4" />
            </svg>
            <p className="font-medium">No events yet</p>
            <p className="text-sm mt-1">Workplace events will appear here as you work on tasks.</p>
          </div>
        </div>
      </div>
    );
  }

  const eventTypeIcons = {
    requirement_change: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
      </svg>
    ),
    deadline_warning: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    stakeholder_message: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h4M8 12l4 4m0-4l4-4M8 12v10a2 2 0 002 2h6a2 2 0 002-2v-4M8 12l4-4m0 0l4 4m-4-4v10" />
      </svg>
    ),
    bug_report: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    priority_change: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
      </svg>
    ),
  };

  const eventTypeColors = {
    requirement_change: "border-status-warning text-status-warning bg-status-warning/10",
    deadline_warning: "border-status-blocked text-status-blocked bg-status-blocked/10",
    stakeholder_message: "border-status-todo text-status-todo bg-status-todo/10",
    bug_report: "border-status-blocked text-status-blocked bg-status-blocked/10",
    priority_change: "border-status-review text-status-review bg-status-review/10",
  };

  const eventTypeLabels = {
    requirement_change: "Requirement Change",
    deadline_warning: "Deadline Warning",
    stakeholder_message: "Stakeholder Message",
    bug_report: "Bug Report",
    priority_change: "Priority Change",
  };

  return (
    <div className="card h-full flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-border flex items-center justify-between">
        <h3 className="font-display text-xs font-semibold uppercase tracking-wide text-text-faint">
          Workplace Events
        </h3>
        <span className="px-2 py-0.5 rounded text-xs font-mono bg-surface-2 text-text-muted">
          {events.length}
        </span>
      </div>

      {/* Events List */}
      <div className="flex-1 overflow-y-auto p-2 space-y-2">
        {events.map((event) => (
          <motion.div
            key={event.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className={`p-3 rounded-lg border transition-all ${
              event.id === activeEvent?.id ? "ring-2 ring-status-todo" : ""
            } ${eventTypeColors[event.event_type] || "border-border"}`}
          >
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0"
                style={{ backgroundColor: `var(--color-${eventTypeColors[event.event_type]?.split(" ")[0]?.replace("border-", "") || "status-todo"})/20` }}>
                {eventTypeIcons[event.event_type] || (
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-sm">{eventTypeLabels[event.event_type] || event.event_type}</span>
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-mono uppercase tracking-wide ${event.status === "pending" ? "bg-status-warning/20 text-status-warning" : "bg-status-completed/20 text-status-completed"}`}>
                    {event.status}
                  </span>
                </div>
                <p className="mt-1 text-sm text-text-muted">{event.message}</p>
                <p className="mt-1 text-xs text-text-faint">
                  {new Date(event.occurred_at).toLocaleTimeString()}
                </p>

                {/* Requirement Change Details */}
                {event.event_type === "requirement_change" && (
                  <div className="mt-2 space-y-2">
                    {event.original_requirement && (
                      <div className="p-2 bg-surface-2 rounded border-l-4 border-status-blocked">
                        <p className="text-xs text-text-faint mb-1">Original Requirement</p>
                        <p className="text-sm text-text-muted line-through">{event.original_requirement}</p>
                      </div>
                    )}
                    {event.updated_requirement && (
                      <div className="p-2 bg-surface-2 rounded border-l-4 border-status-todo">
                        <p className="text-xs text-text-faint mb-1">Updated Requirement</p>
                        <p className="text-sm text-text font-medium">{event.updated_requirement}</p>
                      </div>
                    )}
                  </div>
                )}

                {/* Response Button */}
                {event.action_required && event.status === "pending" && (
                  <button
                    onClick={() => setRespondingToEvent(event)}
                    className="mt-2 btn-primary text-sm py-1.5"
                    disabled={isResponding}
                  >
                    {isResponding ? "Responding..." : "Respond"}
                  </button>
                )}

                {/* Response Display */}
                {event.response && (
                  <div className="mt-2 p-2 bg-surface-2 rounded border border-border">
                    <p className="text-xs text-text-faint mb-1">Your Response</p>
                    <p className="text-sm text-text">{event.response}</p>
                    <p className="text-xs text-text-faint mt-1">
                      Responded at {new Date(event.responded_at).toLocaleTimeString()}
                    </p>
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Event Response Modal */}
      {respondingToEvent && respondingToEvent.action_required && respondingToEvent.status === "pending" && (
        <EventResponseModal
          event={respondingToEvent}
          onClose={() => setRespondingToEvent(null)}
          onRespond={(eventId, response) => {
            onRespond(eventId, response);
            setRespondingToEvent(null);
          }}
          isResponding={isResponding}
        />
      )}
    </div>
  );
}