import React, { useState } from 'react'
import { Play, Pause, Trash2, BookOpen, AlertTriangle, Sparkles } from 'lucide-react'
import { ProgressData, NOVEL_GENRE_OPTIONS } from '../../store/useNovelStore'
import GenreSelectionModal from './GenreSelectionModal'

interface ActiveJobControlsProps {
  selectedNovel: any
  progress: ProgressData | null
  startTranslation: (novelId: number) => Promise<void>
  pauseTranslation: () => Promise<void>
  clearJob: () => Promise<void>
}

export const ActiveJobControls: React.FC<ActiveJobControlsProps> = ({
  selectedNovel,
  progress,
  startTranslation,
  pauseTranslation,
  clearJob
}) => {
  const [isGenreModalOpen, setIsGenreModalOpen] = useState(false)

  if (!selectedNovel) {
    return (
      <div className="glass-panel rounded-2xl p-4 text-center text-xs text-cyber-muted">
        Vui lòng chọn hoặc nhập link một bộ truyện để xem bảng điều khiển dịch.
      </div>
    )
  }

  const isRunning = progress?.isRunning ?? false
  const totalCh = progress?.totalChapters || selectedNovel.chapters.length
  const completedCh = progress?.completedChapters || selectedNovel.chapters.filter((c: any) => c.status === 'COMPLETED' || c.status === 'RESCUED').length
  const pct = totalCh > 0 ? Math.round((completedCh / totalCh) * 100) : 0
  const stage = progress?.stage || 'idle'
  const hasStopError = !isRunning && stage === 'failed'
  const failureMessage = selectedNovel?.chapters?.find((c: any) => c.status === 'FAILED' && c.error_msg)?.error_msg || ''
  const isPaused = !isRunning && stage === 'paused'

  const currentGenreCode = selectedNovel?.novel?.genres || ''
  const currentGenreOption = NOVEL_GENRE_OPTIONS.find(g => g.code === currentGenreCode)

  const handleStartClick = async () => {
    if (!currentGenreCode || !currentGenreCode.trim()) {
      setIsGenreModalOpen(true)
      return
    }
    try {
      await startTranslation(selectedNovel.novel.id)
    } catch (err: any) {
      if (err.message && err.message.includes('GENRE_REQUIRED')) {
        setIsGenreModalOpen(true)
      }
    }
  }

  return (
    <>
      <div className="glass-panel rounded-2xl p-4 flex flex-col gap-3 flex-shrink-0">
        {/* Genre info badge */}
        <div className="flex items-center justify-between bg-slate-900/60 p-2.5 rounded-xl border border-cyber-border/40 text-xs">
          <div className="flex items-center gap-2">
            <span className="text-sm">{currentGenreOption?.icon || '❓'}</span>
            <div>
              <span className="text-[10px] text-cyber-muted block">Thể loại truyện (Khóa 100% ngữ cảnh):</span>
              <span className="font-bold text-cyber-accent">
                {currentGenreOption?.name || 'Chưa chọn thể loại (Bắt buộc)'}
              </span>
            </div>
          </div>
          <button
            onClick={() => setIsGenreModalOpen(true)}
            className="text-[10px] font-bold px-2.5 py-1 rounded-lg bg-cyber-accent/10 border border-cyber-accent/30 text-cyber-accent hover:bg-cyber-accent/20 transition-all flex items-center gap-1"
          >
            <Sparkles className="w-3 h-3" />
            {currentGenreCode ? 'Đổi Thể Loại' : 'Chọn Ngay'}
          </button>
        </div>

        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
              <BookOpen className="w-4 h-4 text-cyber-accent" /> Tiến Trình Dịch
            </h2>
            <p className="text-[10px] text-cyber-muted mt-0.5">
              {completedCh} / {totalCh} chương đã hoàn thành ({pct}%)
            </p>
          </div>

          <div className="flex items-center space-x-2">
            {!isRunning ? (
              <button
                onClick={handleStartClick}
                className="bg-emerald-500 hover:bg-emerald-600 text-white font-bold px-4 py-1.5 rounded-xl text-xs flex items-center gap-1.5 shadow-lg shadow-emerald-500/20 transition-all"
              >
                <Play className="w-3.5 h-3.5" /> Bắt Đầu Dịch
              </button>
            ) : (
              <button
                onClick={pauseTranslation}
                className="bg-amber-500 hover:bg-amber-600 text-white font-bold px-4 py-1.5 rounded-xl text-xs flex items-center gap-1.5 shadow-lg shadow-amber-500/20 transition-all"
              >
                <Pause className="w-3.5 h-3.5" /> Tạm Dừng
              </button>
            )}


          <button
            onClick={clearJob}
            className="p-1.5 hover:bg-cyber-danger/20 text-slate-400 hover:text-cyber-danger rounded-xl border border-cyber-border/40 transition-all"
            title="Dọn dẹp trạng thái job"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {hasStopError && failureMessage && (
        <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-3 text-[11px] text-rose-200 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
          <div>
            <div className="font-semibold">Dịch đã dừng do lỗi</div>
            <div className="mt-1 text-rose-100/90">{failureMessage}</div>
          </div>
        </div>
      )}

      {isPaused && (
        <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 text-[11px] text-amber-200">
          Tiến trình đã được tạm dừng. Bạn có thể bắt đầu lại bất cứ lúc nào.
        </div>
      )}

      {/* Progress Bar */}
      <div className="w-full bg-slate-900/80 rounded-full h-2 overflow-hidden border border-cyber-border/30">
        <div
          className="bg-gradient-to-r from-cyber-accent via-purple-500 to-emerald-400 h-full transition-all duration-500 rounded-full"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>

    <GenreSelectionModal
      isOpen={isGenreModalOpen}
      novelId={selectedNovel?.novel?.id}
      novelTitle={selectedNovel?.novel?.title || ''}
      currentGenre={currentGenreCode}
      onClose={() => setIsGenreModalOpen(false)}
      onSuccess={() => {
        startTranslation(selectedNovel.novel.id)
      }}
    />
  </>
  )
}
export default ActiveJobControls

