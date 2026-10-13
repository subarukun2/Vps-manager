import React, { useState, useEffect, useRef } from 'react';
import { 
  Send, 
  User, 
  Bot, 
  MoreVertical, 
  Paperclip, 
  Smile, 
  Mic, 
  ChevronLeft,
  Info,
  ExternalLink,
  ShieldCheck,
  Zap,
  Activity,
  Server,
  Package,
  RotateCcw,
  StopCircle,
  Play,
  Terminal,
  Trash2
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

interface Message {
  id: string;
  sender: 'user' | 'bot';
  text: React.ReactNode;
  timestamp: string;
  buttons?: { label: string; action: string }[][];
}

export const TelegramSimulator: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      sender: 'bot',
      text: "👋 Welcome to *TeleVPS Pro Dashboard*!\n\nYou can manage your VPS apps, monitor system stats, and deploy repositories directly from here.",
      timestamp: '12:00 PM',
      buttons: [
        [{ label: '📦 My Repositories', action: 'list_repos' }],
        [{ label: '🚀 Manage Apps', action: 'manage_apps' }],
        [{ label: '📊 System Stats', action: 'stats' }]
      ]
    }
  ]);
  const [inputText, setInputText] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isTyping]);

  const addMessage = (sender: 'user' | 'bot', text: React.ReactNode, buttons?: Message['buttons']) => {
    const newMessage: Message = {
      id: Date.now().toString(),
      sender,
      text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      buttons
    };
    setMessages(prev => [...prev, newMessage]);
  };

  const simulateBotResponse = async (action: string) => {
    setIsTyping(true);
    await new Promise(resolve => setTimeout(resolve, 1000));
    setIsTyping(false);

    switch (action) {
      case 'list_repos':
        addMessage('bot', "📂 *Select a Repository to Deploy:*", [
          [{ label: '🌐 my-python-app', action: 'deploy:my-python-app' }],
          [{ label: '🌐 node-api-pro', action: 'deploy:node-api-pro' }],
          [{ label: '🔒 secret-project', action: 'deploy:secret-project' }],
          [{ label: '🔙 Back to Menu', action: 'start' }]
        ]);
        break;
      case 'stats':
        addMessage('bot', (
          <div className="space-y-1">
            <p>📊 *System Stats*</p>
            <p>━━━━━━━━━━━━━━━━━━━━━━━</p>
            <p>💻 *CPU:* `12.5%`</p>
            <p>🧠 *RAM:* `42.8%` (1.8GB / 4GB)</p>
            <p>💽 *Disk:* `15.2%` (32GB Free)</p>
          </div>
        ), [[{ label: '🔄 Refresh', action: 'stats' }, { label: '🔙 Back', action: 'start' }]]);
        break;
      case 'manage_apps':
        addMessage('bot', "📦 *Managed Applications:*", [
          [{ label: '🟢 web-api-v1', action: 'app_info:web-api-v1' }],
          [{ label: '🔴 bot-testing', action: 'app_info:bot-testing' }],
          [{ label: '🔙 Back', action: 'start' }]
        ]);
        break;
      case 'start':
        addMessage('bot', "⚡ *TeleVPS Pro Dashboard*\n━━━━━━━━━━━━━━━━━━━━━━━\nSelect an option:", [
          [{ label: '📦 My Repositories', action: 'list_repos' }],
          [{ label: '🚀 Manage Apps', action: 'manage_apps' }],
          [{ label: '📊 System Stats', action: 'stats' }]
        ]);
        break;
      default:
        if (action.startsWith('deploy:')) {
          const repo = action.split(':')[1];
          addMessage('bot', `🚀 *Deploying:* \`${repo}\`\n\n⚙️ *Status:* Initializing...`);
          await new Promise(resolve => setTimeout(resolve, 1500));
          setIsTyping(true);
          await new Promise(resolve => setTimeout(resolve, 1000));
          setIsTyping(false);
          addMessage('bot', `✅ *App Deployed Successfully!*\n\n📦 *App:* \`${repo}\`\n⚡ *Runtime:* \`PYTHON\`\n⚙️ *Status:* Online`, [
            [{ label: '🚀 Manage Apps', action: 'manage_apps' }]
          ]);
        } else if (action.startsWith('app_info:')) {
          const name = action.split(':')[1];
          addMessage('bot', (
            <div className="space-y-1">
              <p>⚙️ *App:* `{name}`</p>
              <p>━━━━━━━━━━━━━━━━━━━━━━━</p>
              <p>Status: `ONLINE`</p>
              <p>CPU: `2.4%` | MEM: `124 MB`</p>
            </div>
          ), [
            [{ label: '🔄 Restart', action: 'restart' }, { label: '⏹ Stop', action: 'stop' }],
            [{ label: '📜 View Logs', action: 'logs' }, { label: '🗑 Delete', action: 'delete' }],
            [{ label: '🔙 Back', action: 'manage_apps' }]
          ]);
        } else {
          addMessage('bot', "This is a simulator. Deployment logic is fully functional in the Python scripts provided in the Source Code tab.");
        }
    }
  };

  const handleSend = () => {
    if (!inputText.trim()) return;
    const text = inputText;
    setInputText('');
    addMessage('user', text);
    
    if (text.toLowerCase() === '/start') {
      simulateBotResponse('start');
    } else {
      simulateBotResponse('unknown');
    }
  };

  return (
    <div className="max-w-4xl mx-auto flex flex-col md:flex-row gap-8 items-start h-[700px]">
      {/* Phone Frame */}
      <div className="w-[360px] h-full bg-[#1c242f] rounded-[3rem] border-[12px] border-[#0f172a] shadow-2xl overflow-hidden flex flex-col relative shrink-0">
        {/* Status Bar */}
        <div className="h-10 flex items-center justify-between px-8 text-[11px] font-bold text-white/50">
          <span>12:00</span>
          <div className="flex items-center gap-1.5">
            <div className="w-4 h-4 bg-white/20 rounded-sm"></div>
            <div className="w-5 h-2.5 bg-white/40 rounded-full"></div>
          </div>
        </div>

        {/* Chat Header */}
        <div className="bg-[#242f3d] h-14 flex items-center px-4 gap-3 border-b border-white/5">
          <button className="text-blue-400"><ChevronLeft size={24} /></button>
          <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-full flex items-center justify-center">
            <Zap size={18} className="text-white fill-white" />
          </div>
          <div className="flex-1 min-w-0">
            <h4 className="text-sm font-bold truncate">TeleVPS Pro Bot</h4>
            <p className="text-[10px] text-blue-400">bot</p>
          </div>
          <button className="text-white/50"><MoreVertical size={20} /></button>
        </div>

        {/* Chat Area */}
        <div 
          ref={scrollRef}
          className="flex-1 overflow-y-auto p-4 space-y-4 bg-[#0e1621] custom-scrollbar"
        >
          <AnimatePresence initial={false}>
            {messages.map((msg) => (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, scale: 0.9, y: 10 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div className={`max-w-[85%] rounded-2xl p-3 text-sm shadow-sm ${
                  msg.sender === 'user' 
                    ? 'bg-[#2b5278] rounded-tr-none' 
                    : 'bg-[#182533] rounded-tl-none border border-white/5'
                }`}>
                  <div className="whitespace-pre-wrap text-[13px] leading-relaxed">
                    {msg.text}
                  </div>
                  
                  {msg.buttons && (
                    <div className="mt-3 space-y-1">
                      {msg.buttons.map((row, i) => (
                        <div key={i} className="flex gap-1">
                          {row.map((btn) => (
                            <button
                              key={btn.label}
                              onClick={() => simulateBotResponse(btn.action)}
                              className="flex-1 bg-white/5 hover:bg-white/10 text-blue-400 py-1.5 rounded-lg text-[12px] font-medium transition-colors"
                            >
                              {btn.label}
                            </button>
                          ))}
                        </div>
                      ))}
                    </div>
                  )}
                  
                  <div className={`text-[10px] mt-1 text-right ${
                    msg.sender === 'user' ? 'text-white/40' : 'text-white/30'
                  }`}>
                    {msg.timestamp}
                  </div>
                </div>
              </motion.div>
            ))}
            {isTyping && (
              <motion.div 
                initial={{ opacity: 0 }} 
                animate={{ opacity: 1 }}
                className="text-[11px] text-white/30 italic ml-2"
              >
                bot is typing...
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Input Area */}
        <div className="bg-[#17212b] p-3 flex items-center gap-3">
          <button className="text-white/40 hover:text-white"><Smile size={24} /></button>
          <div className="flex-1 bg-[#242f3d] rounded-full px-4 py-2 flex items-center">
            <input 
              type="text" 
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Message" 
              className="bg-transparent border-none focus:outline-none text-sm w-full"
            />
            <button className="text-white/40 hover:text-white"><Paperclip size={20} /></button>
          </div>
          <button 
            onClick={handleSend}
            className="w-10 h-10 bg-blue-500 rounded-full flex items-center justify-center text-white hover:bg-blue-600 transition-colors shadow-lg shadow-blue-500/20"
          >
            {inputText ? <Send size={18} /> : <Mic size={18} />}
          </button>
        </div>
      </div>

      {/* Simulator Info Panel */}
      <div className="flex-1 space-y-6 pt-12">
        <div className="bg-slate-800/40 border border-slate-700/50 p-6 rounded-2xl">
          <h3 className="text-lg font-bold flex items-center gap-2 mb-4">
            <Terminal size={20} className="text-blue-400" />
            Bot Interface Simulator
          </h3>
          <p className="text-slate-400 text-sm leading-relaxed mb-6">
            This simulator demonstrates the exact user experience of your **TeleVPS Pro** bot on Telegram. 
            All commands shown here are fully implemented in the `bot.py` script.
          </p>
          
          <div className="space-y-4">
            <div className="flex items-start gap-4 p-4 bg-slate-900/50 rounded-xl border border-slate-800">
              <div className="p-2 bg-blue-500/10 text-blue-400 rounded-lg"><Package size={18} /></div>
              <div>
                <p className="text-sm font-bold">1-Click Deployment</p>
                <p className="text-xs text-slate-500">Clone, build, and start repos via inline buttons.</p>
              </div>
            </div>
            <div className="flex items-start gap-4 p-4 bg-slate-900/50 rounded-xl border border-slate-800">
              <div className="p-2 bg-purple-500/10 text-purple-400 rounded-lg"><Activity size={18} /></div>
              <div>
                <p className="text-sm font-bold">Live Telemetry</p>
                <p className="text-xs text-slate-500">Fetch real-time CPU and RAM usage of your VPS.</p>
              </div>
            </div>
            <div className="flex items-start gap-4 p-4 bg-slate-900/50 rounded-xl border border-slate-800">
              <div className="p-2 bg-emerald-500/10 text-emerald-400 rounded-lg"><Server size={18} /></div>
              <div>
                <p className="text-sm font-bold">Process Management</p>
                <p className="text-xs text-slate-500">Restart, stop, and view logs of PM2 apps.</p>
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-4 p-4 bg-blue-500/5 border border-blue-500/20 rounded-xl">
          <Info className="text-blue-400 shrink-0" size={20} />
          <p className="text-xs text-blue-300/80 leading-relaxed">
            Note: To use the real bot, push this code to GitHub, run the `setup.sh` on your VPS, 
            and enter your credentials.
          </p>
        </div>
      </div>
    </div>
  );
};
