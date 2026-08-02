import React, { useRef, useEffect } from 'react'
import { Terminal as TermIcon, Trash2 } from 'lucide-react'
import { LogEntry } from '../../store/useNovelStore'

interface TerminalLogsProps {
  logs: LogEntry[]
  setLogs: (logs: LogEntry[]) => void
}

export const TerminalLogs: React.FC<TerminalLogsProps> = React.memo(({ logs, setLogs }) => {
  const terminalEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs.length])

  return (
    <div className="glass-panel rounded-2xl flex flex-col h-full overflow-hidden border border-cyber-border/40">
      {/* Header Bar */}
      <div className="bg-slate-950/80 px-4 py-2.5 border-b border-cyber-border/40 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <TermIcon className="w-4 h-4 text-cyber-accent" />
          <span className="text-xs font-bold text-slate-200 tracking-wider">NHẬT KÝ THỰC THI (REALTIME LOGS)</span>
          <span className="text-[10px] text-cyber-muted bg-slate-900 px-2 py-0.5 rounded border border-cyber-border/30">
            {logs.length} dòng
          </span>
        </div>
        <button
          onClick={() => setLogs([])}
          className="text-slate-400 hover:text-rose-400 text-xs flex items-center gap-1 transition-colors px-2 py-1 rounded hover:bg-slate-900"
          title="Xóa nhật ký"
        >
          <Trash2 className="w-3.5 h-3.5" />
          <span>Xóa</span>
        </button>
      </div>

      {/* Log Content Area */}
      <div className="flex-1 bg-[#05070e] p-4 overflow-y-auto font-mono text-xs space-y-1.5 min-h-[300px]">
        {logs.length === 0 ? (
          <div className="h-full flex items-center justify-center text-slate-600 text-xs italic">
            Chưa có log sự kiện nào. Hãy bấm "Bắt Đầu Dịch" để xem dòng thời gian xử lý.
          </div>
        ) : (
          logs.map((log, index) => {
            let textColor = 'text-slate-300'
            if (log.level === 'danger' || log.level === 'error') textColor = 'text-rose-400 font-bold'
            else if (log.level === 'warning') textColor = 'text-amber-400'
            else if (log.level === 'success') textColor = 'text-emerald-400 font-bold'
            else if (log.level === 'pre') textColor = 'text-cyan-400'
            else if (log.level === 'in' || log.level === 'purple') textColor = 'text-purple-400 font-bold'
            else if (log.level === 'post') textColor = 'text-emerald-300'

            return (
              <div key={index} className="flex items-start space-x-3 leading-relaxed hover:bg-slate-900/40 p-0.5 rounded">
                <span className="text-slate-600 text-[10px] select-none shrink-0 font-mono mt-0.5">
                  [{log.time}]
                </span>
                <span className={`break-all ${textColor}`}>
                  {log.message}
                </span>
              </div>
            )
          })
        )}
        <div ref={terminalEndRef} />
      </div>
    </div>
  )
})
export default TerminalLogs
