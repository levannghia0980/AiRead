import React from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'

interface ReaderFloatingBarProps {
  readingChapter: any
  selectedNovel: any
  handleReadChapter: (novelId: number, chapterNo: number) => void
}

export const ReaderFloatingBar: React.FC<ReaderFloatingBarProps> = React.memo(({
  readingChapter,
  selectedNovel,
  handleReadChapter
}) => {
  if (!readingChapter) return null

  const prevChapter = selectedNovel?.chapters?.find(
    (c: any) => c.chapter_no === readingChapter.chapter_no - 1 && (c.status === 'COMPLETED' || c.status === 'RESCUED')
  )
  const nextChapter = selectedNovel?.chapters?.find(
    (c: any) => c.chapter_no === readingChapter.chapter_no + 1 && (c.status === 'COMPLETED' || c.status === 'RESCUED')
  )

  return (
    <div className="fixed bottom-20 md:bottom-6 left-1/2 -translate-x-1/2 z-40 bg-slate-950/95 border border-cyber-accent/40 shadow-2xl shadow-cyber-accent/20 rounded-full px-4 py-2 flex items-center gap-2 text-xs backdrop-blur-md">
      <button
        onClick={() => prevChapter && handleReadChapter(selectedNovel.novel.id, prevChapter.chapter_no)}
        disabled={!prevChapter}
        className="px-3 py-1.5 rounded-full bg-slate-800 hover:bg-slate-700 disabled:opacity-30 text-slate-200 font-bold flex items-center gap-1 transition-all"
        title="Chương trước"
      >
        <ChevronLeft className="w-4 h-4" /> Trước
      </button>

      <select
        value={readingChapter.chapter_no}
        onChange={(e) => handleReadChapter(selectedNovel.novel.id, Number(e.target.value))}
        className="bg-slate-900 border border-slate-800 text-cyber-accent text-xs font-bold font-mono px-3 py-1.5 rounded-full focus:outline-none focus:border-cyber-accent cursor-pointer max-w-[220px] truncate"
      >
        {selectedNovel?.chapters
          ?.filter((c: any) => c.status === 'COMPLETED' || c.status === 'RESCUED')
          ?.map((c: any) => (
            <option key={c.chapter_no} value={c.chapter_no}>
              Chương {c.chapter_no}: {c.title}
            </option>
          ))}
      </select>

      <button
        onClick={() => nextChapter && handleReadChapter(selectedNovel.novel.id, nextChapter.chapter_no)}
        disabled={!nextChapter}
        className="px-3 py-1.5 rounded-full bg-cyber-accent hover:bg-cyber-accent/90 disabled:opacity-30 text-white font-bold flex items-center gap-1 transition-all shadow-md shadow-cyber-accent/20"
        title="Chương sau"
      >
        Sau <ChevronRight className="w-4 h-4" />
      </button>
    </div>
  )
})

export default ReaderFloatingBar
