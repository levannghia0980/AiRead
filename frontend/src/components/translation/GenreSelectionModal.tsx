import React, { useState } from 'react'
import { Sparkles, Check, AlertCircle, X } from 'lucide-react'
import { NOVEL_GENRE_OPTIONS, useNovelStore } from '../../store/useNovelStore'

interface GenreSelectionModalProps {
  isOpen: boolean
  novelId: number
  novelTitle: string
  currentGenre?: string
  onClose: () => void
  onSuccess?: () => void
}

export const GenreSelectionModal: React.FC<GenreSelectionModalProps> = ({
  isOpen,
  novelId,
  novelTitle,
  currentGenre = '',
  onClose,
  onSuccess
}) => {
  const [selectedCode, setSelectedCode] = useState<string>(currentGenre || 'XIANXIA')
  const [isSaving, setIsSaving] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const { updateNovelGenre } = useNovelStore()

  if (!isOpen) return null

  const handleSave = async () => {
    if (!selectedCode) return
    setIsSaving(true)
    setErrorMsg(null)
    try {
      const res = await updateNovelGenre(novelId, selectedCode)
      if (res.success) {
        if (onSuccess) onSuccess()
        onClose()
      } else {
        setErrorMsg(res.message || 'Lỗi lưu thể loại')
      }
    } catch (e: any) {
      setErrorMsg(e.message || 'Lỗi kết nối')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-fadeIn">
      <div className="relative w-full max-w-xl glass-panel rounded-2xl border border-cyber-accent/40 bg-slate-900/95 p-6 shadow-2xl shadow-cyber-accent/10">
        
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-cyber-border/40">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-xl bg-cyber-accent/10 text-cyber-accent border border-cyber-accent/30">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-md font-bold text-slate-100">Bắt Buộc Chọn Thể Loại Truyện</h3>
              <p className="text-xs text-cyber-muted truncate max-w-md">
                Truyện: <span className="text-cyber-accent font-semibold">{novelTitle}</span>
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <p className="text-xs text-slate-300 mt-3 mb-4 leading-relaxed">
          Vui lòng chọn kiểu bối cảnh cho truyện. Hệ thống sẽ **khóa duy nhất 1 ngữ cảnh thể loại** này khi gửi lên AI, loại bỏ 100% quy tắc thừa giúp bản dịch mượt mà và chuẩn xưng hô nhất.
        </p>

        {/* Options List */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-h-80 overflow-y-auto pr-1">
          {NOVEL_GENRE_OPTIONS.map((opt) => {
            const isSelected = selectedCode === opt.code
            return (
              <div
                key={opt.code}
                onClick={() => setSelectedCode(opt.code)}
                className={`p-3.5 rounded-xl border transition-all cursor-pointer flex flex-col justify-between ${
                  isSelected
                    ? 'border-cyber-accent bg-cyber-accent/15 text-slate-100 shadow-md shadow-cyber-accent/10'
                    : 'border-cyber-border/40 bg-slate-950/40 text-slate-300 hover:border-cyber-border hover:bg-slate-900'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 font-bold text-xs">
                    <span className="text-base">{opt.icon}</span>
                    <span className={isSelected ? 'text-cyber-accent' : 'text-slate-200'}>{opt.name}</span>
                  </div>
                  {isSelected && <Check className="w-4 h-4 text-cyber-accent" />}
                </div>
                <p className="text-[10px] text-cyber-muted mt-2 line-clamp-2 leading-relaxed">
                  {opt.desc}
                </p>
              </div>
            )
          })}
        </div>

        {errorMsg && (
          <div className="mt-3 p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* Footer actions */}
        <div className="flex items-center justify-end gap-3 mt-6 pt-4 border-t border-cyber-border/40">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold text-slate-400 hover:text-slate-200 transition-colors"
          >
            Hủy Bỏ
          </button>
          <button
            onClick={handleSave}
            disabled={isSaving || !selectedCode}
            className="px-5 py-2 text-xs font-bold bg-cyber-accent text-cyber-bg hover:bg-cyber-accent/90 rounded-xl shadow-lg shadow-cyber-accent/20 transition-all disabled:opacity-50 flex items-center gap-1.5"
          >
            {isSaving ? 'Đang lưu CSDL...' : 'Xác Nhận & Tiếp Tục Dịch'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default GenreSelectionModal
