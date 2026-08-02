import React from 'react'
import { FileText, Plus, Trash2, RefreshCw } from 'lucide-react'

interface NovelGlossarySidebarProps {
  selectedNovel: any
  novelGlossary: any[]
  quickZh: string
  setQuickZh: (v: string) => void
  quickVi: string
  setQuickVi: (v: string) => void
  isAddingQuickGlossary: boolean
  handleAddQuickGlossary: (e: React.FormEvent) => void
  handleDeleteGlossaryTerm: (termId: number) => void
}

export const NovelGlossarySidebar: React.FC<NovelGlossarySidebarProps> = ({
  selectedNovel,
  novelGlossary,
  quickZh,
  setQuickZh,
  quickVi,
  setQuickVi,
  isAddingQuickGlossary,
  handleAddQuickGlossary,
  handleDeleteGlossaryTerm
}) => {
  if (!selectedNovel) return null

  return (
    <div className="glass-panel rounded-2xl p-4 flex flex-col gap-3 flex-shrink-0">
      <h2 className="text-xs font-bold text-slate-300 flex items-center justify-between uppercase tracking-wider">
        <span className="flex items-center gap-1.5">
          <FileText className="w-4 h-4 text-cyber-accent" /> Từ Điển Riêng Của Truyện
        </span>
        <span className="text-[10px] text-cyber-accent bg-cyber-accent/10 px-2 py-0.5 rounded-full font-bold border border-cyber-accent/20">
          {novelGlossary.length} từ
        </span>
      </h2>

      {/* Quick Add Glossary Form */}
      <form onSubmit={handleAddQuickGlossary} className="flex flex-col gap-2 bg-slate-950/40 p-2.5 rounded-xl border border-cyber-border/40">
        <div className="grid grid-cols-2 gap-2">
          <input
            type="text"
            placeholder="Từ Hán gốc (vd: 徐小受)"
            value={quickZh}
            onChange={(e) => setQuickZh(e.target.value)}
            className="glass-input rounded-lg px-2.5 py-1.5 text-xs"
          />
          <input
            type="text"
            placeholder="Nghĩa Hán Việt (vd: Từ Tiểu Thụ)"
            value={quickVi}
            onChange={(e) => setQuickVi(e.target.value)}
            className="glass-input rounded-lg px-2.5 py-1.5 text-xs"
          />
        </div>
        <button
          type="submit"
          disabled={isAddingQuickGlossary || !quickZh.trim() || !quickVi.trim()}
          className="w-full bg-cyber-accent/20 hover:bg-cyber-accent/30 text-cyber-accent border border-cyber-accent/40 font-bold py-1.5 rounded-lg text-xs transition-all flex items-center justify-center gap-1 disabled:opacity-40"
        >
          {isAddingQuickGlossary ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
          Thêm Vào Từ Điển Bộ Truyện
        </button>
      </form>

      {/* Glossary Items List */}
      {novelGlossary.length > 0 ? (
        <div className="max-h-40 overflow-y-auto flex flex-col gap-1 pr-1">
          {novelGlossary.map((item: any) => (
            <div
              key={item.id}
              className="flex items-center justify-between bg-slate-900/60 p-2 rounded-lg border border-cyber-border/30 text-xs"
            >
              <div className="flex items-center gap-2 truncate">
                <span className="font-bold text-amber-300">{item.chinese_term}</span>
                <span className="text-slate-500">➔</span>
                <span className="font-bold text-emerald-400">{item.vietnamese_term}</span>
              </div>
              <button
                onClick={() => handleDeleteGlossaryTerm(item.id)}
                className="text-slate-500 hover:text-rose-400 p-1 rounded hover:bg-rose-500/10 transition-all flex-shrink-0"
              >
                <Trash2 className="w-3 h-3" />
              </button>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-[10px] text-cyber-muted text-center py-2">
          Bộ truyện chưa có từ riêng. Hãy thêm từ riêng ở trên để ép AI dịch chuẩn tên nhân vật.
        </p>
      )}
    </div>
  )
}
export default NovelGlossarySidebar
