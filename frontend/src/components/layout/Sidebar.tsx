import { NavLink } from "react-router-dom";
import {
  MessageSquare,
  FileText,
  Cpu,
  History,
  Plus,
  Trash2,
  X,
} from "lucide-react";
import { Logo } from "@/components/brand/Logo";
import { cn, formatRelative } from "@/lib/utils";
import type { Conversation } from "@/types/api";

interface SidebarProps {
  conversations: Conversation[];
  activeId: string | null;
  onNew: () => void;
  onSelect: (id: string) => void;
  onRemove: (id: string) => void;
  chunkCount: number | null;
  open: boolean;
  onClose: () => void;
}

const NAV = [
  { to: "/", label: "Chat", icon: MessageSquare, end: true },
  { to: "/policies", label: "Policies", icon: FileText },
  { to: "/system", label: "System", icon: Cpu },
];

export function Sidebar({
  conversations,
  activeId,
  onNew,
  onSelect,
  onRemove,
  chunkCount,
  open,
  onClose,
}: SidebarProps) {
  return (
    <>
      {/* Scrim, mobile only. */}
      {open && (
        <div
          className="fixed inset-0 z-30 bg-black/40 md:hidden"
          onClick={onClose}
          aria-hidden
        />
      )}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-[264px] flex-col",
          "border-r transition-transform duration-200",
          "md:static md:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
        style={{
          background: "var(--app-surface)",
          borderColor: "var(--app-border)",
        }}
      >
        <div className="flex items-center justify-between px-4 pt-4 pb-3">
          <div className="flex items-center gap-2">
            <Logo size={30} />
            <span className="text-[15px] font-semibold tracking-tight">
              HR
              <span style={{ color: "var(--app-accent)" }}>
                360
              </span>
              &nbsp;Bot
            </span>
          </div>

          <button
            onClick={onClose}
            className="rounded-md p-1 md:hidden"
            style={{ color: "var(--app-ink-muted)" }}
            aria-label="Close navigation"
          >
            <X size={18} />
          </button>
        </div>

        <div className="px-3 pb-3">
          <button
            onClick={onNew}
            className="flex w-full items-center justify-center gap-2 rounded-lg px-3 py-2 text-[13px] font-medium text-white transition-colors"
            style={{ background: "var(--app-accent)" }}
            onMouseEnter={(event) => {
              event.currentTarget.style.background =
                "var(--app-accent-hover)";
            }}
            onMouseLeave={(event) => {
              event.currentTarget.style.background =
                "var(--app-accent)";
            }}
          >
            <Plus size={15} />
            New chat
          </button>
        </div>

        <nav className="px-2">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={onClose}
              className={({ isActive }) =>
                cn(
                  "mb-0.5 flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13.5px] transition-colors",
                  isActive ? "font-medium" : "font-normal",
                )
              }
              style={({ isActive }) => ({
                background: isActive
                  ? "var(--app-accent-soft)"
                  : "transparent",
                color: isActive
                  ? "var(--app-accent)"
                  : "var(--app-ink-muted)",
              })}
            >
              <item.icon size={16} />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="mt-4 flex min-h-0 flex-1 flex-col px-2">
          <div
            className="flex items-center gap-1.5 px-3 pb-2 text-[10.5px] font-semibold tracking-wider uppercase"
            style={{ color: "var(--app-ink-faint)" }}
          >
            <History size={11} />
            History
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto pb-2">
            {conversations.length === 0 ? (
              <p
                className="px-3 py-2 text-[12.5px] leading-relaxed"
                style={{ color: "var(--app-ink-faint)" }}
              >
                No conversations yet. Ask a question to start
                one.
              </p>
            ) : (
              conversations.map((conversation) => (
                <div
                  key={conversation.id}
                  className="group relative mb-0.5"
                >
                  <button
                    onClick={() => {
                      onSelect(conversation.id);
                      onClose();
                    }}
                    className="w-full rounded-lg py-2 pr-8 pl-3 text-left transition-colors"
                    style={{
                      background:
                        conversation.id === activeId
                          ? "var(--app-surface-muted)"
                          : "transparent",
                    }}
                  >
                    <span
                      className="block truncate text-[13px]"
                      style={{
                        color:
                          conversation.id === activeId
                            ? "var(--app-ink)"
                            : "var(--app-ink-muted)",
                      }}
                    >
                      {conversation.title}
                    </span>
                    <span
                      className="block text-[11px]"
                      style={{ color: "var(--app-ink-faint)" }}
                    >
                      {formatRelative(conversation.updatedAt)}
                    </span>
                  </button>

                  <button
                    onClick={() => onRemove(conversation.id)}
                    className="absolute top-1/2 right-1.5 -translate-y-1/2 rounded-md p-1.5 opacity-0 transition-opacity group-hover:opacity-100 focus:opacity-100"
                    style={{ color: "var(--app-ink-faint)" }}
                    aria-label={`Delete ${conversation.title}`}
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              ))
            )}
          </div>
        </div>

        <div
          className="border-t px-4 py-3 text-[11.5px]"
          style={{
            borderColor: "var(--app-border)",
            color: "var(--app-ink-faint)",
          }}
        >
          {chunkCount === null
            ? "Connecting to backend…"
            : `${chunkCount} chunks · 6 policies indexed`}
        </div>
      </aside>
    </>
  );
}
