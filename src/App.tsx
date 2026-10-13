import React, { useState, useEffect } from 'react';
import { 
  Terminal, 
  Settings, 
  Activity, 
  Code2, 
  LayoutDashboard, 
  Server, 
  Cpu, 
  ExternalLink,
  ShieldCheck,
  Zap
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

// Mock components (we will create them in the next steps)
const DashboardOverview = () => (
  <div className="space-y-6">
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      <div className="bg-slate-800/50 border border-slate-700 p-6 rounded-2xl">
        <div className="flex items-center gap-4 mb-4">
          <div className="p-3 bg-blue-500/20 text-blue-400 rounded-xl"><Cpu size={24}/></div>
          <div>
            <p className="text-slate-400 text-sm">System CPU</p>
            <h3 className="text-2xl font-bold">12.5%</h3>
          </div>
        </div>
        <div className="w-full bg-slate-700 h-2 rounded-full overflow-hidden">
          <div className="bg-blue-500 h-full w-[12.5%] transition-all duration-500"></div>
        </div>
      </div>
      <div className="bg-slate-800/50 border border-slate-700 p-6 rounded-2xl">
        <div className="flex items-center gap-4 mb-4">
          <div className="p-3 bg-purple-500/20 text-purple-400 rounded-xl"><Activity size={24}/></div>
          <div>
            <p className="text-slate-400 text-sm">RAM Usage</p>
            <h3 className="text-2xl font-bold">42.8%</h3>
          </div>
        </div>
        <div className="w-full bg-slate-700 h-2 rounded-full overflow-hidden">
          <div className="bg-purple-500 h-full w-[42.8%] transition-all duration-500"></div>
        </div>
      </div>
      <div className="bg-slate-800/50 border border-slate-700 p-6 rounded-2xl">
        <div className="flex items-center gap-4 mb-4">
          <div className="p-3 bg-emerald-500/20 text-emerald-400 rounded-xl"><Server size={24}/></div>
          <div>
            <p className="text-slate-400 text-sm">Managed Apps</p>
            <h3 className="text-2xl font-bold">4 Running</h3>
          </div>
        </div>
        <div className="flex gap-2">
          <span className="w-3 h-3 bg-emerald-500 rounded-full animate-pulse"></span>
          <span className="text-xs text-slate-400">All systems operational</span>
        </div>
      </div>
    </div>

    <div className="bg-slate-800/30 border border-slate-700/50 rounded-2xl p-8 text-center max-w-2xl mx-auto mt-12">
      <Zap className="mx-auto text-yellow-400 mb-4" size={48} />
      <h2 className="text-2xl font-bold mb-4">Welcome to TeleVPS Pro</h2>
      <p className="text-slate-400 mb-8 leading-relaxed">
        Your VPS is now empowered with a professional Heroku-like management system. 
        You can control everything from your Telegram Bot, but we've restored this dashboard 
        so you can easily view your code and monitor system health.
      </p>
      <div className="flex flex-col sm:flex-row gap-4 justify-center">
        <div className="flex items-center gap-2 bg-slate-900 border border-slate-700 px-4 py-3 rounded-xl font-mono text-sm text-yellow-400 overflow-x-auto">
          <span>curl -sSL https://.../setup.sh | bash</span>
        </div>
      </div>
    </div>
  </div>
);

const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'simulator' | 'code' | 'stats'>('dashboard');

  const tabs = [
    { id: 'dashboard', label: 'Overview', icon: LayoutDashboard },
    { id: 'simulator', label: 'Telegram Bot', icon: Terminal },
    { id: 'code', label: 'Source Code', icon: Code2 },
    { id: 'stats', label: 'Server Metrics', icon: Activity },
  ];

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="bg-slate-900/80 backdrop-blur-md border-b border-slate-800 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg shadow-blue-500/20">
              <Zap className="text-white fill-white" size={20} />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight">TeleVPS <span className="text-blue-400">Pro</span></h1>
              <p className="text-[10px] text-slate-500 uppercase tracking-widest font-bold">Personal Cloud Engine</p>
            </div>
          </div>
          
          <nav className="hidden md:flex items-center gap-1 bg-slate-800/40 p-1 rounded-xl border border-slate-700/50">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  activeTab === tab.id 
                    ? 'bg-blue-500 text-white shadow-md' 
                    : 'text-slate-400 hover:text-white hover:bg-slate-700/50'
                }`}
              >
                <tab.icon size={16} />
                {tab.label}
              </button>
            ))}
          </nav>

          <div className="flex items-center gap-4">
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-emerald-500/10 border border-emerald-500/20 rounded-full">
              <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></div>
              <span className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider">Live Preview</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-6 py-8">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2 }}
          >
            {activeTab === 'dashboard' && <DashboardOverview />}
            {activeTab === 'simulator' && (
              <div className="h-[700px] bg-slate-800/20 border border-slate-700 rounded-3xl flex items-center justify-center text-slate-500">
                <div className="text-center">
                  <Terminal size={48} className="mx-auto mb-4 opacity-20" />
                  <p>Interactive Simulator Restoring...</p>
                </div>
              </div>
            )}
            {activeTab === 'code' && (
              <div className="h-[700px] bg-slate-800/20 border border-slate-700 rounded-3xl flex items-center justify-center text-slate-500">
                <div className="text-center">
                  <Code2 size={48} className="mx-auto mb-4 opacity-20" />
                  <p>Code Explorer Restoring...</p>
                </div>
              </div>
            )}
            {activeTab === 'stats' && (
              <div className="h-[700px] bg-slate-800/20 border border-slate-700 rounded-3xl flex items-center justify-center text-slate-500">
                <div className="text-center">
                  <Activity size={48} className="mx-auto mb-4 opacity-20" />
                  <p>Advanced Metrics Restoring...</p>
                </div>
              </div>
            )}
          </motion.div>
        </AnimatePresence>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800 py-8 px-6 text-center text-slate-500 text-sm">
        <p>&copy; 2026 TeleVPS Pro. Built for Ubuntu 22.04 LTS.</p>
      </footer>
    </div>
  );
};

export default App;
