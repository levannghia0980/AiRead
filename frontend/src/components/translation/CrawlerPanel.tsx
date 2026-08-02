import React from 'react'
import { Globe, RefreshCw, Play } from 'lucide-react'
import { Novel } from '../../store/useNovelStore'

interface CrawlerPanelProps {
  inputUrl: string
  setInputUrl: (url: string) => void
  isAnalyzing: boolean
  handleAnalyzeUrl: () => void
  analyzedData: any
  handleSaveNovel: () => void
  isSaving: boolean
  novels: Novel[]
  selectedNovelId?: number
  fetchNovelDetails: (id: number) => void
}

export const CrawlerPanel: React.FC<CrawlerPanelProps> = ({
  inputUrl,
  setInputUrl,
  isAnalyzing,
  handleAnalyzeUrl,
  analyzedData,
  handleSaveNovel,
  isSaving,
  novels,
  selectedNovelId,
  fetchNovelDetails
}) => {
  return (
    <div className="glass-panel rounded-2xl p-4 lg:p-5 flex flex-col gap-3 flex-shrink-0">
      <h2 className="text-xs font-bold text-slate-400 flex items-center gap-1.5 uppercase tracking-wider">
        <Globe className="w-4 h-4 text-cyber-accent" /> Nhập Link & Chọn Truyện Đang Dịch
      </h2>

      <div className="flex gap-2">
        <input
          type="text"
          value={inputUrl}
          onChange={(e) => setInputUrl(e.target.value)}
          placeholder="Nhập link truyện (69shuba, alicesw...)..."
          className="flex-1 glass-input rounded-xl px-3 py-2 text-xs"
        />
        <button
          onClick={handleAnalyzeUrl}
          disabled={isAnalyzing || !inputUrl}
          className="bg-cyber-accent hover:bg-cyber-accent/80 text-cyber-bg font-semibold px-4 py-2 rounded-xl text-xs transition-all duration-200 flex items-center gap-1 disabled:opacity-50"
        >
          {isAnalyzing ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />} Phân Tích
        </button>
      </div>

      {/* Analyzed metadata details */}
      {analyzedData && (
        <div className="mt-1 border-t border-cyber-border/40 pt-3 flex gap-3 animate-fade-in flex-shrink-0">
          {analyzedData.cover_url && (
            <img
              src={analyzedData.cover_url}
              alt="Novel cover"
              className="w-12 h-16 object-cover rounded-lg border border-cyber-border"
            />
          )}
          <div className="flex-1 flex flex-col justify-between">
            <div className="text-[10px] text-slate-400">
              <h3 className="text-xs font-bold text-cyber-accent truncate max-w-[180px]">{analyzedData.title}</h3>
              <p>Tác giả: <span className="text-slate-200">{analyzedData.author}</span></p>
            </div>
            <button
              onClick={handleSaveNovel}
              disabled={isSaving}
              className="w-fit mt-1 bg-gradient-to-r from-cyber-accent to-cyber-purple hover:opacity-90 text-cyber-bg font-bold px-3 py-1 rounded-lg text-[9px] uppercase tracking-wider transition-all flex items-center gap-1"
            >
              {isSaving ? <RefreshCw className="w-3 h-3 animate-spin" /> : null} Lưu & Dịch
            </button>
          </div>
        </div>
      )}

      {/* Selection list directly inside card */}
      {novels.length > 0 && (
        <div className="border-t border-cyber-border/40 pt-2 flex flex-col gap-2">
          <div className="grid grid-cols-1 gap-1.5 max-h-24 overflow-y-auto pr-1">
            {novels.map((n) => {
              const isSelected = selectedNovelId === n.id
              return (
                <div
                  key={n.id}
                  onClick={() => fetchNovelDetails(n.id)}
                  className={`glass-card p-1.5 rounded-lg flex gap-2 cursor-pointer transition-all duration-200 border text-[11px] ${
                    isSelected
                      ? 'border-cyber-accent bg-cyber-accent/5 shadow-md'
                      : 'border-cyber-border/10 hover:border-cyber-border/25 hover:bg-slate-900/40'
                  }`}
                >
                  {n.cover_url ? (
                    <img src={n.cover_url} alt="cover" className="w-6 h-8 object-cover rounded border border-cyber-border flex-shrink-0" />
                  ) : (
                    <div className="w-6 h-8 rounded bg-slate-800 flex items-center justify-center text-[8px] flex-shrink-0">
                      📖
                    </div>
                  )}
                  <div className="flex-1 min-w-0 flex flex-col justify-center">
                    <h3 className="font-bold text-[10px] text-slate-200 truncate">{n.title}</h3>
                    <div className="flex items-center justify-between text-[8px] text-cyber-muted">
                      <span className="truncate max-w-[70px]">{n.author}</span>
                      {isSelected ? <span className="text-cyber-accent font-bold">● Đang chọn</span> : <span>{n.status}</span>}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
export default CrawlerPanel
