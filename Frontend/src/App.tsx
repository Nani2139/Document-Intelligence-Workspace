import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import { FileText, MessageSquare } from 'lucide-react';
import DocumentsPage from './pages/DocumentsPage';
import ChatPage from './pages/ChatPage';

function NavItem({ to, icon: Icon, label }: { to: string; icon: typeof FileText; label: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
          isActive
            ? 'bg-emerald-900/20 text-emerald-400'
            : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800'
        }`
      }
    >
      <Icon size={16} />
      {label}
    </NavLink>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="h-screen flex flex-col bg-zinc-950 text-zinc-100">
        {/* Top nav */}
        <header className="flex items-center justify-between px-6 py-3 border-b border-zinc-800">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-emerald-600 flex items-center justify-center text-white font-bold text-sm">
              DI
            </div>
            <span className="text-sm font-semibold text-zinc-200">Document Intelligence</span>
          </div>
          <nav className="flex gap-1">
            <NavItem to="/" icon={FileText} label="Documents" />
            <NavItem to="/chat" icon={MessageSquare} label="Chat" />
          </nav>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-hidden">
          <Routes>
            <Route path="/" element={<DocumentsPage />} />
            <Route path="/chat" element={<ChatPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
