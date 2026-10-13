import React, { useState, useEffect } from 'react';
import { FileCode, Copy, Check, Download, Search } from 'lucide-react';
import { SCRIPTS_DATA } from '../data/scriptsData';

export const CodeExplorer: React.FC = () => {
  const [selectedFile, setSelectedFile] = useState<string>('bot.py');
  const [content, setContent] = useState<string>('Loading...');
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    // In a real environment, we'd fetch from /api/raw/:filename
    // For the preview, we'll try to fetch directly if the server supports it,
    // or just show a placeholder if we can't.
    const fetchContent = async () => {
      try {
        // In AI Studio, we can often access root files via relative paths if configured
        const response = await fetch(`/${selectedFile}`);
        if (response.ok) {
          const text = await response.text();
          setContent(text);
        } else {
          setContent(`# Error loading ${selectedFile}\n# File might be missing or inaccessible.`);
        }
      } catch (err) {
        setContent(`# Connection error loading ${selectedFile}`);
      }
    };
    fetchContent();
  }, [selectedFile]);

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = selectedFile;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex flex-col h-full bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
      <div className="flex flex-col md:flex-row flex-1">
        {/* Sidebar */}
        <div className="w-full md:w-64 bg-slate-900/50 border-r border-slate-800 p-4 space-y-2">
          <div className="relative mb-6">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={14} />
            <input 
              type="text" 
              placeholder="Search files..." 
              className="w-full bg-slate-800 border border-slate-700 rounded-lg py-1.5 pl-9 pr-3 text-xs focus:outline-none focus:border-blue-500/50"
            />
          </div>
          <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest px-2 pb-2">Core Files</p>
          {Object.keys(SCRIPTS_DATA).map((fileName) => (
            <button
              key={fileName}
              onClick={() => setSelectedFile(fileName)}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-xl text-sm transition-all ${
                selectedFile === fileName 
                  ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20' 
                  : 'text-slate-400 hover:text-white hover:bg-slate-800'
              }`}
            >
              <FileCode size={16} />
              <span className="truncate">{fileName}</span>
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 flex flex-col min-w-0">
          <div className="h-14 border-b border-slate-800 flex items-center justify-between px-6 bg-slate-900/50">
            <div className="flex items-center gap-3">
              <span className="text-sm font-bold">{selectedFile}</span>
              <span className="text-[10px] bg-slate-800 text-slate-400 px-2 py-0.5 rounded border border-slate-700">
                {(SCRIPTS_DATA as any)[selectedFile]?.language.toUpperCase()}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <button 
                onClick={handleCopy}
                className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
                title="Copy Code"
              >
                {copied ? <Check size={18} className="text-emerald-400" /> : <Copy size={18} />}
              </button>
              <button 
                onClick={handleDownload}
                className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
                title="Download File"
              >
                <Download size={18} />
              </button>
            </div>
          </div>
          <div className="flex-1 overflow-auto bg-[#0d1117] p-6 font-mono text-sm leading-relaxed custom-scrollbar">
            <pre className="text-slate-300 whitespace-pre-wrap">{content}</pre>
          </div>
        </div>
      </div>
    </div>
  );
};
