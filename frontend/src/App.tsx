import { useState } from "react";
import {
  BrowserRouter,
  Route,
  Routes,
  useNavigate,
} from "react-router-dom";
import {
  QueryClient,
  QueryClientProvider,
  useQuery,
} from "@tanstack/react-query";
import { Menu, Plus } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { ChatPage } from "@/pages/ChatPage";
import { PoliciesPage } from "@/pages/PoliciesPage";
import { useConversations } from "@/stores/conversations";
import { api } from "@/services/api";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false, refetchOnWindowFocus: false },
  },
});

function Shell() {
  const [navOpen, setNavOpen] = useState(false);
  const navigate = useNavigate();

  const {
    conversations,
    active,
    activeId,
    startNew,
    select,
    remove,
    appendTurn,
    updateTurn,
  } = useConversations();

  /**
   * Clearing the active conversation is not enough on its
   * own: from /policies the state change is invisible and the
   * button looks dead. Both New chat buttons go through here
   * so they always land on the chat page.
   */
  function handleNew() {
    startNew();
    navigate("/");
    setNavOpen(false);
  }

  /** Same reason: picking from history must show the chat. */
  function handleSelect(id: string) {
    select(id);
    navigate("/");
    setNavOpen(false);
  }

  const stats = useQuery({
    queryKey: ["stats"],
    queryFn: api.stats,
    retry: false,
  });

  return (
    <div
      className="flex h-screen overflow-hidden"
      style={{ background: "var(--app-canvas)" }}
    >
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        onNew={handleNew}
        onSelect={handleSelect}
        onRemove={remove}
        chunkCount={stats.data?.count ?? null}
        open={navOpen}
        onClose={() => setNavOpen(false)}
      />

      <main className="flex min-w-0 flex-1 flex-col">
        <header
          className="flex items-center gap-2 border-b px-4 py-3"
          style={{
            borderColor: "var(--app-border)",
            background: "var(--app-surface)",
          }}
        >
          <button
            onClick={() => setNavOpen(true)}
            className="rounded-md p-1 md:hidden"
            style={{ color: "var(--app-ink-muted)" }}
            aria-label="Open navigation"
          >
            <Menu size={18} />
          </button>

          <span className="text-[14px] font-medium">
            {active?.title ?? "New chat"}
          </span>

          <button
            onClick={handleNew}
            className="ml-auto inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12.5px] font-medium text-white"
            style={{ background: "var(--app-accent)" }}
          >
            <Plus size={14} />
            New chat
          </button>
        </header>

        <div
          className="min-h-0 flex-1"
          style={{ background: "var(--app-surface)" }}
        >
          <Routes>
            <Route
              path="/"
              element={
                <ChatPage
                  active={active}
                  appendTurn={appendTurn}
                  updateTurn={updateTurn}
                />
              }
            />
            <Route
              path="/policies"
              element={<PoliciesPage />}
            />
          </Routes>
        </div>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Shell />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
