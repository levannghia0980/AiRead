import React, { useState, useMemo, useDeferredValue } from 'react'
import {
  BookOpen,
  RefreshCw,
  Download,
  RotateCcw,
  CheckCircle,
  XCircle,
  Wand2,
  Trash2,
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  Save,
  Eye,
  Library as LibIcon
} from 'lucide-react'
import { Novel } from '../store/useNovelStore'
import ReaderFloatingBar from './ReaderFloatingBar'
import ParagraphItem from './ParagraphItem'

const splitParagraphs = (text: string): string[] => {
  if (!text) return []
  let clean = text.normalize("NFC")
  clean = clean.replace(/([\u00c0-\u024f\u1ea0-\u1eff])\s+([\u0300-\u036f]+)/gi, '$1$2').normalize("NFC")
  const vietVowels = "[aáàảãạăắằẳẵặâấầẩẫậeéèẻẽẹêếềểễệiíìỉĩịoóòỏõọôốồổỗộơớờởỡợuúùủũụưứừửữựyýỳỷỹỵAÁÀẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬEẾỀỂỄỆIÍÌỈĨỊOÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢUÚÙỦŨỤƯỨỪỬỮỰYÝỲỶỸỴ]"
  const vietEndings = "(?:ng|nh|ch|c|t|n|m|p|u|y)"
  const brokenSyllableRegex = new RegExp(`(${vietVowels}+)[\\t ]+(${vietEndings})(?![a-zà-ỹá-ỵă-ặâ-ậê-ệô-ộơ-ợư-ựA-ZÁ-Ỵ])`, "gi")
  clean = clean.replace(brokenSyllableRegex, "$1$2").normalize("NFC")
  clean = clean.replace(/<br\s*\/?>/gi, '\n\n').replace(/<\/?p[^>]*>/gi, '\n\n').replace(/<\/?div[^>]*>/gi, '\n\n')
  return clean.split(/\n+/).map(p => p.trim()).filter(Boolean)
}

const formatChapterTextForReader = (text: string) => {
  if (!text) return ''

  let clean = text.normalize("NFC")
  clean = clean.replace(/([\u00c0-\u024f\u1ea0-\u1eff])\s+([\u0300-\u036f]+)/gi, '$1$2')
  clean = clean.normalize("NFC")

  const vietVowels = "[aáàảãạăắằẳẵặâấầẩẫậeéèẻẽẹêếềểễệiíìỉĩịoóòỏõọôốồổỗộơớờởỡợuúùủũụưứừửữựyýỳỷỹỵAÁÀẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬEẾỀỂỄỆIÍÌỈĨỊOÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢUÚÙỦŨỤƯỨỪỬỮỰYÝỲỶỸỴ]"
  const vietEndings = "(?:ng|nh|ch|c|t|n|m|p|u|y)"
  const brokenSyllableRegex = new RegExp(`(${vietVowels}+)[\\t ]+(${vietEndings})(?![a-zà-ỹá-ỵă-ặâ-ậê-ệô-ộơ-ợư-ựA-ZÁ-Ỵ])`, "gi")
  clean = clean.replace(brokenSyllableRegex, "$1$2")
  clean = clean.normalize("NFC")

  clean = clean.replace(/<br\s*\/?>/gi, '\n\n')
  clean = clean.replace(/<\/?p[^>]*>/gi, '\n\n')
  clean = clean.replace(/<\/?div[^>]*>/gi, '\n\n')

  clean = clean
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')

  let rawParagraphs = clean.split(/\n+/).map(p => p.trim()).filter(Boolean)

  if (rawParagraphs.length <= 2 && clean.length > 300) {
    const autoSplit = clean.replace(/([.!?…”"])\s+([A-ZÁÀẢÃẠĂẮẶẲẴÂẤẬẨẪÉÈẺẼẸÊẾỆỂỄÍÌỈĨỊÓÒỎÕỌÔỐỘỔỖƠỚỢỞỠÚÙỦŨỤƯỨỰỬỮÝỲỶỸỴĐ“"«])/g, '$1\n\n$2')
    rawParagraphs = autoSplit.split(/\n+/).map(p => p.trim()).filter(Boolean)
  }

  return rawParagraphs
    .map(p => `<p class="mb-5 leading-relaxed text-base font-sans text-slate-200" style="letter-spacing: normal;">${p}</p>`)
    .join('\n')
}

export interface LibraryTabProps {
  novels: Novel[]
  selectedNovel: any
  fetchNovelDetails: (id: number) => void
  deleteNovel: (id: number) => void
  readingChapter: any
  setReadingChapter: (v: any) => void
  isEditing: boolean
  setIsEditing: (v: boolean) => void
  isSavingEdit: boolean
  handleSaveEdit: () => void
  editorRef: React.RefObject<HTMLDivElement>
  handleDownloadNovel: (novelId: number, fmt: 'txt' | 'docx') => void
  isDownloading: boolean
  handleResetChapters: (novelId: number, chapterNos?: number[]) => void
  isResetting: boolean
  chapterSearch: string
  setChapterSearch: (v: string) => void
  showChaptersList: boolean
  setShowChaptersList: (v: boolean) => void
  saveResult: any
  handleQuickFixAll: (novelId: number) => void
  isFixingAll: boolean
  handleBatchFixRed: (novelId: number) => void
  isFixingRed: boolean
  handleReadChapter: (novelId: number, chapterNo: number) => void
  handleRestartNovel: (novelId: number) => void
  isRestarting: boolean
}

export const LibraryTab: React.FC<LibraryTabProps> = React.memo(({
  novels,
  selectedNovel,
  fetchNovelDetails,
  deleteNovel,
  readingChapter,
  setReadingChapter,
  isEditing,
  setIsEditing,
  isSavingEdit,
  handleSaveEdit,
  editorRef,
  handleDownloadNovel,
  isDownloading,
  handleResetChapters,
  isResetting,
  chapterSearch,
  setChapterSearch,
  showChaptersList,
  setShowChaptersList,
  saveResult,
  handleQuickFixAll,
  isFixingAll,
  handleBatchFixRed,
  isFixingRed,
  handleReadChapter,
  handleRestartNovel,
  isRestarting
}) => {
  const [viewMode, setViewMode] = useState<'bookshelf' | 'details'>(
    selectedNovel ? 'details' : 'bookshelf'
  )
  const [showRestartConfirm, setShowRestartConfirm] = useState(false)

  React.useEffect(() => {
    if (selectedNovel) {
      setViewMode('details')
    }
  }, [selectedNovel?.novel.id])

  const deferredSearch = useDeferredValue(chapterSearch)

  const yellowChaptersCount = useMemo(() => {
    if (!selectedNovel?.chapters) return 0
    return selectedNovel.chapters.filter((ch: any) => 
      (ch.status === 'COMPLETED' || ch.status === 'RESCUED') && ch.translated_text && ch.translated_text.includes('class="fallback-word"')
    ).length
  }, [selectedNovel?.chapters])

  const redChaptersCount = useMemo(() => {
    if (!selectedNovel?.chapters) return 0
    return selectedNovel.chapters.filter((ch: any) => 
      (ch.status === 'COMPLETED' || ch.status === 'RESCUED') && ch.has_swept_errors
    ).length
  }, [selectedNovel?.chapters])

  const filteredChapters = useMemo(() => {
    if (!selectedNovel?.chapters) return []
    if (!deferredSearch.trim()) return selectedNovel.chapters
    const query = deferredSearch.toLowerCase()
    return selectedNovel.chapters.filter((ch: any) =>
      ch.chapter_no.toString().includes(query) ||
      ch.title.toLowerCase().includes(query)
    )
  }, [selectedNovel?.chapters, deferredSearch])

  // 1. EMBEDDED READER VIEW
  if (readingChapter) {
    const prevChapter = selectedNovel?.chapters.find((c: any) => c.chapter_no === readingChapter.chapter_no - 1 && (c.status === 'COMPLETED' || c.status === 'RESCUED'))
    const nextChapter = selectedNovel?.chapters.find((c: any) => c.chapter_no === readingChapter.chapter_no + 1 && (c.status === 'COMPLETED' || c.status === 'RESCUED'))

    return (
      <div className="relative flex flex-col h-full overflow-hidden bg-slate-950/60 rounded-2xl border border-cyber-border/40 reader-container">
        {/* Reader Header Controls */}
        <div className="flex-shrink-0 border-b border-cyber-border/40 px-5 py-3.5 flex items-center justify-between bg-slate-950/95 z-30 flex-wrap gap-2 reader-header">
          <div className="flex items-center gap-3">
            <button
              onClick={() => {
                setReadingChapter(null)
                window.history.pushState({ tab: 'library' }, '', '?tab=library')
              }}
              className="p-1.5 rounded-lg border border-cyber-border hover:bg-slate-800 text-slate-300 hover:text-white transition-all flex items-center gap-1.5 text-xs font-bold"
            >
              <ArrowLeft className="w-4 h-4 text-cyber-accent" />
              <span>Thoát Đọc (Danh Sách)</span>
            </button>
            <div>
              <h2 className="text-sm font-bold text-cyber-accent reader-title">
                Chương {readingChapter.chapter_no}: {readingChapter.title}
              </h2>
              <p className="text-[10px] text-cyber-muted font-medium flex items-center gap-1">
                <span>{selectedNovel?.novel.title}</span>
                <span className="text-cyber-accent font-mono font-bold">• Chương {readingChapter.chapter_no}/{selectedNovel?.chapters?.length || 0}</span>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <select
              value={readingChapter.chapter_no}
              onChange={(e) => handleReadChapter(selectedNovel.novel.id, Number(e.target.value))}
              className="bg-slate-900 border border-cyber-border text-cyber-accent text-xs font-bold font-mono px-2.5 py-1.5 rounded-lg focus:outline-none focus:border-cyber-accent cursor-pointer"
            >
              {selectedNovel?.chapters
                ?.filter((c: any) => c.status === 'COMPLETED' || c.status === 'RESCUED')
                ?.map((c: any) => (
                  <option key={c.chapter_no} value={c.chapter_no}>
                    Chương {c.chapter_no}/{selectedNovel?.chapters?.length || 0}: {c.title}
                  </option>
                ))}
            </select>

            {isEditing ? (
              <div className="flex items-center gap-2">
                <button
                  onClick={handleSaveEdit}
                  disabled={isSavingEdit}
                  className="bg-emerald-500 hover:bg-emerald-600 text-white font-bold px-3 py-1.5 rounded-lg text-xs flex items-center gap-1.5 shadow-lg shadow-emerald-500/20 transition-all disabled:opacity-50"
                  title="Lưu bản dịch đã chỉnh sửa"
                >
                  {isSavingEdit ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                  Lưu Chỉnh Sửa
                </button>
                <button
                  onClick={() => setIsEditing(false)}
                  disabled={isSavingEdit}
                  className="bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold px-3 py-1.5 rounded-lg text-xs flex items-center gap-1.5 border border-cyber-border transition-all"
                  title="Hủy bỏ chỉnh sửa"
                >
                  <XCircle className="w-3.5 h-3.5" />
                  Hủy
                </button>
              </div>
            ) : (
              <button
                onClick={() => setIsEditing(true)}
                className="border border-cyber-accent/40 bg-cyber-accent/10 hover:bg-cyber-accent/20 text-cyber-accent font-bold px-3 py-1.5 rounded-lg text-xs flex items-center gap-1.5 transition-all"
              >
                <Wand2 className="w-3.5 h-3.5" />
                Sửa Bản Dịch
              </button>
            )}

            <button
              onClick={() => prevChapter && handleReadChapter(selectedNovel.novel.id, prevChapter.chapter_no)}
              disabled={!prevChapter || isEditing}
              className="px-3 py-1.5 border border-cyber-border/60 rounded-lg text-xs font-semibold text-slate-300 hover:border-cyber-accent hover:text-cyber-accent disabled:opacity-30 disabled:hover:border-cyber-border/60 transition-all flex items-center gap-1"
            >
              <ChevronLeft className="w-4 h-4" /> Trước
            </button>

            <button
              onClick={() => nextChapter && handleReadChapter(selectedNovel.novel.id, nextChapter.chapter_no)}
              disabled={!nextChapter || isEditing}
              className="px-3 py-1.5 border border-cyber-border/60 rounded-lg text-xs font-semibold text-slate-300 hover:border-cyber-accent hover:text-cyber-accent disabled:opacity-30 disabled:hover:border-cyber-border/60 transition-all flex items-center gap-1"
            >
              Sau <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Reader Content Body */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 text-slate-200 leading-relaxed font-sans text-base pb-44 md:pb-32 reader-content-body">
          {isEditing ? (
            <div className="max-w-4xl mx-auto space-y-3 my-2">
              <div className="flex items-center justify-between p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs">
                <div className="flex items-center gap-2">
                  <span className="animate-pulse font-bold">✏️ Chế độ chỉnh sửa trực tiếp:</span>
                  <span>Bạn có thể click trực tiếp vào văn bản bên dưới để sửa chữ, sau đó bấm <strong>"Lưu Chỉnh Sửa"</strong>.</span>
                </div>
                <button
                  onClick={() => setIsEditing(false)}
                  className="text-[11px] underline hover:text-white font-semibold"
                >
                  Đóng chế độ sửa
                </button>
              </div>
              <div
                ref={editorRef}
                contentEditable
                suppressContentEditableWarning
                className="focus:outline-none min-h-[500px] border border-cyber-accent/50 focus:border-cyber-accent rounded-2xl p-6 sm:p-10 bg-slate-900/70 leading-relaxed font-sans text-base shadow-inner text-slate-100 reader-paper-sheet"
                style={{ letterSpacing: 'normal' }}
                dangerouslySetInnerHTML={{ __html: formatChapterTextForReader(readingChapter.translated_text) }}
              />
            </div>
          ) : (
            <div className="max-w-4xl mx-auto reader-paper-sheet p-6 sm:p-10 rounded-2xl border border-cyber-border/30 shadow-md my-2">
              <div className="mb-6 pb-4 border-b border-cyber-border/30">
                <h1 className="text-xl sm:text-2xl font-bold reader-title text-cyber-accent mb-2">
                  Chương {readingChapter.chapter_no}: {readingChapter.title}
                </h1>
                <p className="text-xs text-cyber-muted flex items-center gap-2">
                  <span>{selectedNovel?.novel.title}</span>
                  <span>•</span>
                  <span>{splitParagraphs(readingChapter.translated_text).length} đoạn văn</span>
                </p>
              </div>
              <div className="prose max-w-none leading-relaxed text-slate-200 font-sans text-base">
                {splitParagraphs(readingChapter.translated_text).map((pText, idx) => (
                  <ParagraphItem key={idx} htmlContent={pText} />
                ))}
              </div>
            </div>
          )}
        </div>

        <ReaderFloatingBar
          readingChapter={readingChapter}
          selectedNovel={selectedNovel}
          handleReadChapter={handleReadChapter}
        />
      </div>
    )
  }

  // 2. BOOKSHELF GRID VIEW
  if (viewMode === 'bookshelf' || !selectedNovel) {
    return (
      <div className="flex flex-col h-full overflow-hidden p-6 gap-6">
        <div className="glass-panel p-5 rounded-2xl flex items-center justify-between flex-shrink-0">
          <div>
            <h2 className="text-md font-bold text-slate-100 flex items-center gap-2">
              <LibIcon className="w-5 h-5 text-cyber-accent" /> Tủ Sách Truyện Đã Lưu ({novels.length} bộ)
            </h2>
            <p className="text-xs text-cyber-muted mt-0.5">
              Chọn một bộ truyện để xem danh sách chương, đọc nội dung hoặc xuất bản file.
            </p>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {novels.length === 0 ? (
            <div className="glass-panel p-12 text-center rounded-2xl flex flex-col items-center justify-center">
              <BookOpen className="w-12 h-12 text-slate-600 mb-3 opacity-40" />
              <p className="text-sm font-semibold text-slate-300">Chưa có bộ truyện nào được lưu</p>
              <p className="text-xs mt-1 text-slate-500">Vui lòng sang tab "Dịch Thuật" và dán link truyện từ 69shuba/alicesw để cào truyện.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {novels.map((novel) => {
                const isSelected = selectedNovel?.novel.id === novel.id
                return (
                  <div
                    key={novel.id}
                    className={`glass-panel p-4 rounded-2xl flex flex-col justify-between border transition-all duration-200 hover:border-cyber-accent/50 hover:shadow-lg hover:shadow-cyber-accent/10 group ${
                      isSelected ? 'border-cyber-accent bg-cyber-accent/5' : 'border-cyber-border/30'
                    }`}
                  >
                    <div className="flex gap-3">
                      {novel.cover_url ? (
                        <img
                          src={novel.cover_url}
                          alt={novel.title}
                          className="w-16 h-22 object-cover rounded-xl border border-cyber-border shadow-md flex-shrink-0"
                        />
                      ) : (
                        <div className="w-16 h-22 rounded-xl bg-slate-900 border border-cyber-border flex items-center justify-center text-xl flex-shrink-0">
                          📖
                        </div>
                      )}
                      <div className="flex-1 min-w-0 flex flex-col justify-between">
                        <div>
                          <h3 className="font-bold text-sm text-slate-100 truncate group-hover:text-cyber-accent transition-colors">
                            {novel.title}
                          </h3>
                          <p className="text-[11px] text-cyber-muted truncate mt-0.5">Tác giả: {novel.author || 'N/A'}</p>
                          <span className="inline-block mt-2 text-[9px] font-bold px-2 py-0.5 rounded-full bg-slate-900 text-cyber-accent border border-cyber-accent/20">
                            {novel.status || 'Đang cập nhật'}
                          </span>
                        </div>

                        <button
                          onClick={() => deleteNovel(novel.id)}
                          className="text-[10px] text-slate-500 hover:text-rose-400 flex items-center gap-1 mt-2 self-start transition-colors"
                          title="Xóa truyện khỏi thư viện"
                        >
                          <Trash2 className="w-3 h-3" /> Xóa bộ này
                        </button>
                      </div>
                    </div>

                    <button
                      onClick={() => {
                        fetchNovelDetails(novel.id)
                        setViewMode('details')
                      }}
                      className="mt-4 w-full bg-cyber-accent/15 hover:bg-cyber-accent text-cyber-accent hover:text-cyber-bg font-bold py-2 rounded-xl text-xs border border-cyber-accent/30 transition-all flex items-center justify-center gap-1.5"
                    >
                      <Eye className="w-3.5 h-3.5" /> Xem Chương & Đọc
                    </button>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    )
  }

  // 3. NOVEL DETAILS & CHAPTERS LIST VIEW
  const completedCount = selectedNovel.chapters.filter((c: any) => c.status === 'COMPLETED' || c.status === 'RESCUED').length

  return (
    <>
    <div className="flex flex-col h-full overflow-hidden">
      {/* Novel Header Bar */}
      <div className="flex-shrink-0 bg-[#070A13] border-b border-cyber-border px-5 py-4 flex flex-col gap-3 z-20">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setViewMode('bookshelf')}
              className="p-2 rounded-xl border border-cyber-border/60 hover:border-cyber-accent text-slate-400 hover:text-cyber-accent transition-all text-xs font-bold flex items-center gap-1"
              title="Quay lại Tủ Sách"
            >
              <ArrowLeft className="w-4 h-4" /> Tủ Sách
            </button>
            {selectedNovel.novel.cover_url && (
              <img src={selectedNovel.novel.cover_url} alt="cover" className="w-10 h-14 object-cover rounded border border-cyber-border" />
            )}
            <div>
              <h2 className="text-md font-bold text-slate-100 truncate max-w-[250px]">{selectedNovel.novel.title}</h2>
              <div className="flex items-center gap-2 mt-0.5">
                <p className="text-[10px] text-cyber-muted">
                  {completedCount} / {selectedNovel.chapters.length} chương đã hoàn thành
                </p>
                <span className="text-slate-600">•</span>
                <select
                  value={selectedNovel.novel.genres || ''}
                  onChange={async (e) => {
                    const val = e.target.value
                    if (val) {
                      const { useNovelStore } = await import('../store/useNovelStore')
                      await useNovelStore.getState().updateNovelGenre(selectedNovel.novel.id, val)
                    }
                  }}
                  className="bg-slate-900 border border-cyber-accent/40 text-cyber-accent text-[10px] font-bold px-2 py-0.5 rounded-lg focus:outline-none focus:border-cyber-accent cursor-pointer"
                >
                  <option value="">⚠️ Bắt buộc chọn Thể Loại</option>
                  <option value="XIANXIA">☯️ Tiên Hiệp / Cổ Trang</option>
                  <option value="WUXIA">⚔️ Võ Lâm / Kiếm Hiệp</option>
                  <option value="MODERN_URBAN">🏙️ Đô Thị / Hiện Đại</option>
                  <option value="ROMANCE">💕 Ngôn Tình / Điền Văn</option>
                  <option value="SYSTEM_REINCARNATION">⚡ Hệ Thống / Trọng Sinh</option>
                  <option value="SCI_FI_APOCALYPSE">🚀 Mạt Thế / Viễn Tưởng</option>
                </select>
              </div>
            </div>

          </div>

          <div className="flex gap-2 flex-wrap justify-end">
            {/* Quick Fix All Yellow Sentences Button */}
            {yellowChaptersCount > 0 && (
              <button
                onClick={() => handleQuickFixAll(selectedNovel.novel.id)}
                disabled={isFixingAll || isFixingRed}
                className="bg-amber-500/20 border border-amber-500/50 hover:bg-amber-500/30 text-amber-300 font-bold px-3.5 py-2 rounded-xl text-xs flex items-center gap-1.5 transition-all shadow-lg disabled:opacity-40 animate-pulse"
                title="Gom tất cả các câu chứa chữ vàng gửi AI biên tập mượt mà 1 lượt duy nhất"
              >
                {isFixingAll ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Wand2 className="w-3.5 h-3.5" />}
                ⚡ Sửa Chữ Vàng ({yellowChaptersCount})
              </button>
            )}

            {/* Quick Fix All Red Sentences Button */}
            {redChaptersCount > 0 && (
              <button
                onClick={() => handleBatchFixRed(selectedNovel.novel.id)}
                disabled={isFixingAll || isFixingRed}
                className="bg-rose-500/20 border border-rose-500/50 hover:bg-rose-500/30 text-rose-300 font-bold px-3.5 py-2 rounded-xl text-xs flex items-center gap-1.5 transition-all shadow-lg disabled:opacity-40 animate-pulse"
                title="Gom tất cả lỗi Hán tự dịch sai gửi AI sửa mượt mà 1 lượt duy nhất"
              >
                {isFixingRed ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Wand2 className="w-3.5 h-3.5" />}
                ⚡ Sửa Hán Tự ({redChaptersCount})
              </button>
            )}

            {/* Download TXT */}
            <button
              onClick={() => handleDownloadNovel(selectedNovel.novel.id, 'txt')}
              disabled={isDownloading || completedCount === 0}
              className="border border-cyber-accent/40 hover:bg-cyber-accent/10 text-cyber-accent font-bold px-3 py-2 rounded-xl text-xs flex items-center gap-1.5 transition-all shadow-lg disabled:opacity-40"
              title="Tải file TXT gộp tất cả chương"
            >
              {isDownloading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
              TXT
            </button>

            {/* Download DOCX */}
            <button
              onClick={() => handleDownloadNovel(selectedNovel.novel.id, 'docx')}
              disabled={isDownloading || completedCount === 0}
              className="border border-cyber-purple/40 hover:bg-cyber-purple/10 text-cyber-purple font-bold px-3 py-2 rounded-xl text-xs flex items-center gap-1.5 transition-all shadow-lg disabled:opacity-40"
              title="Tải file DOCX gộp tất cả chương"
            >
              {isDownloading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
              DOCX
            </button>

            <button
              onClick={() => handleResetChapters(selectedNovel.novel.id)}
              disabled={isResetting}
              className="border border-cyber-danger/30 hover:bg-cyber-danger/10 text-cyber-danger font-bold px-3 py-2 rounded-xl text-xs flex items-center gap-1.5 transition-all shadow-lg disabled:opacity-40"
            >
              {isResetting ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <RotateCcw className="w-3.5 h-3.5" />}
              Reset Tất Cả
            </button>

            {/* Nút Restart Toàn Bộ - Xóa sạch entities, audio, corrections */}
            <button
              onClick={() => setShowRestartConfirm(true)}
              disabled={isRestarting}
              className="border-2 border-red-500/50 hover:bg-red-500/20 text-red-400 font-bold px-3 py-2 rounded-xl text-xs flex items-center gap-1.5 transition-all shadow-lg shadow-red-500/10 disabled:opacity-40"
              title="Xóa SẠCH tất cả: bản dịch, audio, thực thể, lỗi — dịch lại từ đầu"
            >
              {isRestarting ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <span>🔄</span>}
              Restart Toàn Bộ
            </button>
          </div>
        </div>

        {/* Search & Toggle Chapter List Bar */}
        <div className="flex items-center gap-3 bg-slate-950/40 p-2.5 rounded-xl border border-cyber-border/40 mt-1">
          <div className="relative flex-1">
            <span className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-500">🔍</span>
            <input
              type="text"
              placeholder="Tìm nhanh số chương hoặc tiêu đề..."
              value={chapterSearch}
              onChange={(e) => {
                setChapterSearch(e.target.value)
                if (e.target.value.trim() !== '') {
                  setShowChaptersList(true)
                }
              }}
              className="w-full glass-input rounded-lg pl-9 pr-3 py-1.5 text-xs"
            />
          </div>
          <button
            onClick={() => setShowChaptersList(!showChaptersList)}
            className={`px-3 py-1.5 border rounded-lg text-xs font-bold transition-all whitespace-nowrap flex items-center gap-1.5 ${
              showChaptersList
                ? 'border-cyber-accent bg-cyber-accent/10 text-cyber-accent'
                : 'border-cyber-border/60 hover:border-cyber-accent text-slate-300'
            }`}
          >
            <span>{showChaptersList ? '📂 Ẩn Chương' : '📁 Hiện Chương'}</span>
            <span className="text-[10px] opacity-75">({selectedNovel.chapters.length})</span>
          </button>
        </div>
      </div>

      {/* Save Result Notice */}
      {saveResult && (
        <div className={`mx-5 mt-3 flex items-start gap-2 p-3 rounded-lg text-xs animate-fade-in flex-shrink-0 ${
          saveResult.success
            ? 'bg-cyber-success/10 border border-cyber-success/30 text-cyber-success'
            : 'bg-cyber-danger/10 border border-cyber-danger/30 text-cyber-danger'
        }`}>
          {saveResult.success ? <CheckCircle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" /> : <XCircle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />}
          <span className="break-all">{saveResult.message}</span>
        </div>
      )}

      {/* Chapter List */}
      {showChaptersList ? (
        <div className="flex-grow lg:flex-1 lg:min-h-0 overflow-y-auto p-5 min-h-0">
          <div className="flex flex-col gap-1.5">
            {filteredChapters.map((ch: any) => {
              const isRescued = ch.status === 'RESCUED'
              const isCompleted = ch.status === 'COMPLETED' || isRescued
              const isFailed = ch.status === 'FAILED'
              const hasYellowText = isCompleted && ch.translated_text && ch.translated_text.includes('class="fallback-word"')
              const hasRedText = isCompleted && ch.has_swept_errors

              return (
                <div
                  key={ch.id}
                  className={`w-full flex items-center justify-between px-4 py-2.5 rounded-xl text-xs border transition-all duration-150 group ${
                    hasRedText
                      ? 'border-rose-500/50 bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 font-medium'
                      : hasYellowText
                        ? 'border-amber-500/50 bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 font-medium'
                        : isFailed
                        ? 'border-cyber-danger/40 bg-cyber-danger/10 hover:bg-cyber-danger/20 text-cyber-danger'
                        : isRescued
                          ? 'border-purple-500/30 bg-purple-950/20 hover:bg-purple-950/30 text-purple-300'
                          : isCompleted
                            ? 'border-cyber-border/20 bg-slate-900/30 hover:bg-slate-900/60 hover:border-cyber-border/40 text-slate-200'
                            : 'border-cyber-border/10 hover:bg-slate-900/40 hover:border-cyber-border/30 text-slate-500'
                  }`}
                >
                  <button
                    onClick={() => isCompleted && handleReadChapter(selectedNovel.novel.id, ch.chapter_no)}
                    disabled={!isCompleted}
                    className={`flex-1 text-left flex items-center gap-3 min-w-0 ${isCompleted ? 'cursor-pointer' : 'cursor-default'}`}
                  >
                    <span className={`w-8 h-8 rounded-lg flex items-center justify-center text-[10px] font-bold flex-shrink-0 ${
                      hasRedText
                        ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                        : hasYellowText
                          ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                        : isFailed
                          ? 'bg-cyber-danger/15 text-cyber-danger border border-cyber-danger/30'
                          : isRescued
                            ? 'bg-purple-500/15 text-purple-400 border border-purple-500/30'
                            : isCompleted
                              ? 'bg-cyber-success/15 text-cyber-success border border-cyber-success/30'
                              : 'bg-slate-900/60 text-slate-500 border border-cyber-border/30'
                    }`}>
                      {ch.chapter_no}
                    </span>
                    <div className="min-w-0">
                      <p className={`font-medium truncate ${
                        hasRedText ? 'text-rose-300 font-bold' : hasYellowText ? 'text-amber-300 font-bold' : isFailed ? 'text-cyber-danger font-bold' : isRescued ? 'text-purple-300 font-bold' : isCompleted ? 'text-slate-200' : 'text-slate-500'
                      }`}>{ch.title}</p>
                      <p className={`text-[10px] mt-0.5 ${hasRedText ? 'text-rose-400 font-bold' : hasYellowText ? 'text-amber-400 font-bold' : isFailed ? 'text-cyber-danger/80' : isRescued ? 'text-purple-400' : 'text-cyber-muted'}`}>
                        {hasRedText ? '🔴 Cần sửa Hán tự' : hasYellowText ? '🟡 Cần sửa chữ vàng' : isFailed ? '❌ Lỗi dịch' : isRescued ? '💜 Dịch cứu hộ' : isCompleted ? '✅ Đã dịch' : '⏳ Chờ dịch'}
                      </p>
                    </div>
                  </button>
                  <div className="flex items-center gap-2 ml-2 flex-shrink-0">
                    {isCompleted && (
                      <button
                        onClick={() => handleReadChapter(selectedNovel.novel.id, ch.chapter_no)}
                        className="px-2.5 py-1 bg-cyber-success/15 hover:bg-cyber-success/30 border border-cyber-success/30 hover:border-cyber-success text-cyber-success hover:text-white text-[10px] font-bold rounded-lg transition-all"
                      >
                        Xem & Đọc
                      </button>
                    )}

                    <button
                      onClick={() => handleResetChapters(selectedNovel.novel.id, [ch.chapter_no])}
                      title="Xóa bản dịch, cache và cào dịch lại chương này"
                      className="p-1.5 hover:bg-cyber-danger/20 text-slate-500 hover:text-cyber-danger rounded-lg transition-all"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      ) : (
        <div className="flex-grow lg:flex-1 flex flex-col items-center justify-center p-8 text-center text-xs text-cyber-muted">
          <BookOpen className="w-8 h-8 text-slate-600 mb-2 opacity-50" />
          <span>Danh sách chương đang ẩn. Bấm <strong className="text-cyber-accent">"Hiện Chương"</strong> hoặc nhập ô tìm kiếm để xem.</span>
        </div>
      )}
    </div>

      {/* === RESTART CONFIRMATION DIALOG === */}
      {showRestartConfirm && selectedNovel && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/70 backdrop-blur-sm">
          <div className="bg-slate-900 border-2 border-red-500/50 rounded-2xl p-6 max-w-md w-full mx-4 shadow-2xl shadow-red-500/20">
            <div className="text-center mb-4">
              <span className="text-4xl">⚠️</span>
              <h3 className="text-lg font-bold text-red-400 mt-2">Restart Toàn Bộ Truyện</h3>
              <p className="text-slate-400 text-sm mt-2">
                Hành động này sẽ <strong className="text-red-400">XÓA SẠCH</strong> tất cả:
              </p>
              <ul className="text-xs text-slate-500 mt-2 space-y-1 text-left pl-6 list-disc">
                <li>Tất cả bản dịch (GG, LLM, FINAL)</li>
                <li>Tất cả file Audio TTS</li>
                <li>Tất cả thực thể nhân vật, địa danh</li>
                <li>Tất cả bản sửa lỗi (corrections)</li>
                <li>Metadata cache</li>
              </ul>
            </div>
            <div className="mb-4 text-center">
              <p className="text-sm font-semibold text-white bg-slate-800/80 border border-red-500/30 rounded-lg p-3">
                Truyện: <span className="text-cyber-accent">{selectedNovel.novel.title || selectedNovel.novel.title_rough || selectedNovel.novel.title_raw}</span>
              </p>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => setShowRestartConfirm(false)}
                className="flex-1 bg-slate-700 hover:bg-slate-600 text-white font-bold py-2.5 rounded-xl text-sm transition-all"
              >
                Hủy
              </button>
              <button
                onClick={async () => {
                  setShowRestartConfirm(false)
                  handleRestartNovel(selectedNovel.novel.id)
                }}
                disabled={isRestarting}
                className="flex-1 bg-red-600 hover:bg-red-500 disabled:bg-slate-700 disabled:text-slate-500 text-white font-bold py-2.5 rounded-xl text-sm transition-all disabled:cursor-not-allowed flex items-center justify-center gap-1.5"
              >
                {isRestarting ? <RefreshCw className="w-4 h-4 animate-spin" /> : <span>🔄</span>}
                Xác Nhận Restart
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
})

export default LibraryTab
