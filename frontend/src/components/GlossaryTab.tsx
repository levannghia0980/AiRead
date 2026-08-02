import React, { useState, useEffect, useMemo } from 'react'
import { FileText, Plus, Trash2, Search, Edit3, Check, X, RefreshCw, Sparkles, BookOpen } from 'lucide-react'
import { Glossary, Novel } from '../store/useNovelStore'

interface GlossaryTabProps {
  glossary: Glossary[]
  corrections: any[]
  novels: Novel[]
  fetchGlossary: (novelId: number, chapterNo?: number | null) => Promise<void>
  addGlossaryTerm: (novelId: number, chinese: string, vietnamese: string, category: string, chapterNo?: number | null) => Promise<{ success: boolean; message?: string; affected_chapters?: number }>
  updateGlossaryTerm: (novelId: number, termId: number, chinese: string, vietnamese: string, category: string, oldVietnamese?: string, chapterNo?: number | null) => Promise<{ success: boolean; message?: string; affected_chapters?: number }>
  applyGlossaryToAllChapters: (novelId: number) => Promise<{ success: boolean; message?: string; affected_chapters?: number }>
  deleteGlossaryTerm: (novelId: number, termId: number, chapterNo?: number | null) => Promise<void>
  fetchCorrections: (novelId: number, chapterNo: number) => Promise<void>
  addCorrection: (novelId: number, chapterNo: number, wrong: string, correct: string) => Promise<any>
  updateCorrection: (novelId: number, chapterNo: number, corrId: number, wrong: string, correct: string) => Promise<any>
  deleteCorrection: (novelId: number, chapterNo: number, corrId: number) => Promise<void>
}

export const GlossaryTab: React.FC<GlossaryTabProps> = React.memo(({
  glossary,
  corrections,
  novels,
  fetchGlossary,
  addGlossaryTerm,
  updateGlossaryTerm,
  applyGlossaryToAllChapters,
  deleteGlossaryTerm,
  fetchCorrections,
  addCorrection,
  updateCorrection,
  deleteCorrection
}) => {
  const [selectedNovelId, setSelectedNovelId] = useState<number>(0)
  const [selectedChapterNo, setSelectedChapterNo] = useState<number>(0)
  const [chapters, setChapters] = useState<any[]>([])
  const [subTab, setSubTab] = useState<'entities' | 'corrections'>('entities')

  // Glossary Form State
  const [chineseTerm, setChineseTerm] = useState('')
  const [vietnameseTerm, setVietnameseTerm] = useState('')
  const [category, setCategory] = useState('NAME')
  const [searchTerm, setSearchTerm] = useState('')

  // Corrections Form State
  const [wrongText, setWrongText] = useState('')
  const [correctText, setCorrectText] = useState('')
  const [corrSearchTerm, setCorrSearchTerm] = useState('')

  // State hỗ trợ sửa trực tiếp (Inline Editing Glossary)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editChinese, setEditChinese] = useState('')
  const [editVietnamese, setEditVietnamese] = useState('')
  const [editCategory, setEditCategory] = useState('NAME')
  const [oldVietnamese, setOldVietnamese] = useState('')

  // State hỗ trợ sửa trực tiếp (Inline Editing Corrections)
  const [editingCorrId, setEditingCorrId] = useState<number | null>(null)
  const [editWrong, setEditWrong] = useState('')
  const [editCorrect, setEditCorrect] = useState('')

  // State thông báo & trạng thái đang áp dụng
  const [notice, setNotice] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isApplyingAll, setIsApplyingAll] = useState(false)

  // Fetch chapters list dynamically when selectedNovelId changes
  useEffect(() => {
    setSelectedChapterNo(0)
    if (selectedNovelId > 0) {
      fetch(`/api/novels/${selectedNovelId}`)
        .then(res => res.json())
        .then(data => {
          if (data.chapters) {
            setChapters(data.chapters)
          } else {
            setChapters([])
          }
        })
        .catch(() => setChapters([]))
    } else {
      setChapters([])
    }
  }, [selectedNovelId])

  // Sync subTab: Reset to 'entities' if no chapter selected
  useEffect(() => {
    if (selectedChapterNo === 0) {
      setSubTab('entities')
    }
  }, [selectedChapterNo])

  // Fetch glossary & corrections when novel or chapter selection changes
  useEffect(() => {
    fetchGlossary(selectedNovelId, selectedChapterNo > 0 ? selectedChapterNo : null)
    if (selectedNovelId > 0 && selectedChapterNo > 0) {
      fetchCorrections(selectedNovelId, selectedChapterNo)
    }
    setNotice(null)
  }, [selectedNovelId, selectedChapterNo])

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!chineseTerm.trim() || !vietnameseTerm.trim()) return
    setIsSubmitting(true)
    setNotice(null)

    try {
      const res = await addGlossaryTerm(
        selectedNovelId, 
        chineseTerm.trim(), 
        vietnameseTerm.trim(), 
        category,
        selectedChapterNo > 0 ? selectedChapterNo : null
      )
      if (res && res.message) {
        setNotice(res.message)
      } else {
        setNotice(`✨ Đã thêm từ '${chineseTerm}' ➔ '${vietnameseTerm}' vào từ điển.`)
      }
      setChineseTerm('')
      setVietnameseTerm('')
    } catch (err: any) {
      setNotice(`❌ Lỗi: ${err.message}`)
    } finally {
      setIsSubmitting(false)
    }
  }

  const startEdit = (term: Glossary) => {
    setEditingId(term.id)
    setEditChinese(term.chinese_term)
    setEditVietnamese(term.vietnamese_term)
    setOldVietnamese(term.vietnamese_term)
    setEditCategory(term.category)
  }

  const cancelEdit = () => {
    setEditingId(null)
  }

  const handleSaveEdit = async (termId: number) => {
    if (!editChinese.trim() || !editVietnamese.trim()) return
    setIsSubmitting(true)
    setNotice(null)

    try {
      const res = await updateGlossaryTerm(
        selectedNovelId,
        termId,
        editChinese.trim(),
        editVietnamese.trim(),
        editCategory,
        oldVietnamese,
        selectedChapterNo > 0 ? selectedChapterNo : null
      )
      if (res && res.message) {
        setNotice(res.message)
      } else {
        setNotice(`✨ Đã cập nhật từ '${editChinese}' ➔ '${editVietnamese}' và tự động áp dụng vào các chương đã dịch!`)
      }
      setEditingId(null)
    } catch (err: any) {
      setNotice(`❌ Lỗi khi cập nhật từ: ${err.message}`)
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleApplyAll = async () => {
    if (selectedNovelId === 0) {
      alert("Vui lòng chọn một bộ truyện cụ thể để áp dụng từ điển đồng bộ!")
      return
    }
    const selNovel = novels.find(n => n.id === selectedNovelId)
    const titleStr = selNovel ? (selNovel.title_rough || selNovel.title_raw) : 'bộ truyện này'

    if (!window.confirm(`Bạn có chắc muốn cưỡng ép thay thế TOÀN BỘ từ điển vào tất cả các chương đã dịch của "${titleStr}" không?`)) return

    setIsApplyingAll(true)
    setNotice(null)
    try {
      const res = await applyGlossaryToAllChapters(selectedNovelId)
      if (res && res.message) {
        setNotice(res.message)
      } else {
        setNotice(`🎉 Đã quét và thay thế từ điển thành công vào toàn bộ các chương đã dịch của ${titleStr}!`)
      }
    } catch (err: any) {
      setNotice(`❌ Lỗi khi áp dụng từ điển: ${err.message}`)
    } finally {
      setIsApplyingAll(false)
    }
  }

  // Corrections CRUD Actions
  const handleAddCorrection = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!wrongText.trim() || !correctText.trim()) return
    setIsSubmitting(true)
    setNotice(null)

    try {
      const res = await addCorrection(selectedNovelId, selectedChapterNo, wrongText.trim(), correctText.trim())
      if (res && res.message) {
        setNotice(res.message)
      } else {
        setNotice(`✨ Đã thêm lỗi '${wrongText}' ➔ '${correctText}' cho Chương ${selectedChapterNo}.`)
      }
      setWrongText('')
      setCorrectText('')
    } catch (err: any) {
      setNotice(`❌ Lỗi: ${err.message}`)
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleSaveEditCorr = async (corrId: number) => {
    if (!editWrong.trim() || !editCorrect.trim()) return
    setIsSubmitting(true)
    setNotice(null)

    try {
      const res = await updateCorrection(selectedNovelId, selectedChapterNo, corrId, editWrong.trim(), editCorrect.trim())
      if (res && res.message) {
        setNotice(res.message)
      } else {
        setNotice(`✨ Đã cập nhật lỗi thành công!`)
      }
      setEditingCorrId(null)
    } catch (err: any) {
      setNotice(`❌ Lỗi: ${err.message}`)
    } finally {
      setIsSubmitting(false)
    }
  }

  const filteredGlossary = useMemo(() => {
    if (!searchTerm.trim()) return glossary
    const query = searchTerm.toLowerCase()
    return glossary.filter(g =>
      g.chinese_term.toLowerCase().includes(query) ||
      g.vietnamese_term.toLowerCase().includes(query) ||
      g.category.toLowerCase().includes(query)
    )
  }, [glossary, searchTerm])

  const filteredCorrections = useMemo(() => {
    if (!corrSearchTerm.trim()) return corrections
    const query = corrSearchTerm.toLowerCase()
    return corrections.filter(c =>
      c.wrong_text.toLowerCase().includes(query) ||
      c.correct_text.toLowerCase().includes(query)
    )
  }, [corrections, corrSearchTerm])

  const selectedNovelObj = useMemo(() => novels.find(n => n.id === selectedNovelId), [novels, selectedNovelId])

  return (
    <div className="flex flex-col h-full overflow-hidden p-6 gap-6">
      {/* Top Controls Header */}
      <div className="glass-panel p-5 rounded-2xl flex flex-col md:flex-row items-center justify-between gap-4 flex-shrink-0">
        <div>
          <h2 className="text-md font-bold text-slate-100 flex items-center gap-2">
            <FileText className="w-5 h-5 text-cyber-accent" /> Quản Lý Từ Điển Thuật Ngữ & Tên Nhân Vật
          </h2>
          <p className="text-xs text-cyber-muted mt-0.5">
            Mọi chỉnh sửa hoặc thêm mới sẽ tự động được thay thế cưỡng ép vào <b>toàn bộ các chương đã dịch</b> của bộ truyện.
          </p>
        </div>

        {/* Novel & Chapter Selector */}
        <div className="flex items-center gap-3 flex-wrap">
          {/* Novel Selector */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400 whitespace-nowrap font-medium">Bộ truyện:</span>
            <select
              value={selectedNovelId}
              onChange={(e) => setSelectedNovelId(parseInt(e.target.value))}
              className="glass-input rounded-xl px-3 py-1.5 text-xs font-semibold text-cyber-accent border-cyber-accent/30"
            >
              <option value={0}>🌐 Từ Điển Dùng Chung (Toàn hệ thống)</option>
              {novels.map(n => (
                <option key={n.id} value={n.id}>📖 {n.title_rough || n.title_raw}</option>
              ))}
            </select>
          </div>

          {/* Chapter Selector */}
          {selectedNovelId > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400 whitespace-nowrap font-medium">Chương:</span>
              <select
                value={selectedChapterNo}
                onChange={(e) => setSelectedChapterNo(parseInt(e.target.value))}
                className="glass-input rounded-xl px-3 py-1.5 text-xs font-semibold text-cyber-accent border-cyber-accent/30"
              >
                <option value={0}>📖 Tất Cả Chương</option>
                {chapters.map(ch => (
                  <option key={ch.id} value={ch.chapter_no}>
                    Chương {ch.chapter_no}: {ch.title_rough || ch.title_raw}
                  </option>
                ))}
              </select>
            </div>
          )}

          {selectedNovelId > 0 && selectedChapterNo === 0 && (
            <button
              onClick={handleApplyAll}
              disabled={isApplyingAll}
              className="bg-cyber-accent/15 border border-cyber-accent/40 text-cyber-accent hover:bg-cyber-accent/30 font-bold px-3.5 py-1.5 rounded-xl text-xs transition-all flex items-center gap-1.5 disabled:opacity-50 shadow-md shadow-cyber-accent/10"
              title="Quét và thay thế toàn bộ từ điển mới vào tất cả các chương đã dịch"
            >
              {isApplyingAll ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5 text-amber-300" />}
              Áp Dụng Thay Từ Vào Tất Cả Chương
            </button>
          )}
        </div>
      </div>

      {/* Real-time Notice Banner */}
      {notice && (
        <div className="p-3.5 bg-slate-900/80 border border-cyber-accent/40 rounded-xl text-xs font-semibold text-emerald-400 flex items-center justify-between shadow-lg backdrop-blur-md animate-fade-in flex-shrink-0">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-amber-300 animate-pulse flex-shrink-0" />
            <span>{notice}</span>
          </div>
          <button onClick={() => setNotice(null)} className="text-slate-400 hover:text-slate-200">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Sub tabs for Chapter specific dict vs corrections */}
      {selectedNovelId > 0 && selectedChapterNo > 0 && (
        <div className="flex border-b border-cyber-border/40 gap-4 flex-shrink-0">
          <button
            onClick={() => setSubTab('entities')}
            className={`px-4 py-2 text-xs font-bold transition-all border-b-2 ${
              subTab === 'entities'
                ? 'border-cyber-accent text-cyber-accent'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            👤 Tên & Thuật Ngữ
          </button>
          <button
            onClick={() => setSubTab('corrections')}
            className={`px-4 py-2 text-xs font-bold transition-all border-b-2 ${
              subTab === 'corrections'
                ? 'border-cyber-accent text-cyber-accent'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            🛠️ Lỗi GG Dịch
          </button>
        </div>
      )}

      {/* Content Form and List */}
      {subTab === 'entities' ? (
        <>
          {/* Add New Term Form */}
          <form onSubmit={handleAdd} className="glass-panel p-4 rounded-2xl grid grid-cols-1 md:grid-cols-4 gap-3 flex-shrink-0">
            <input
              type="text"
              placeholder="Từ Hán gốc (vd: 徐小受)"
              value={chineseTerm}
              onChange={(e) => setChineseTerm(e.target.value)}
              className="glass-input rounded-xl px-3 py-2 text-xs"
            />
            <input
              type="text"
              placeholder="Nghĩa Hán Việt / Dịch chuẩn (vd: Từ Tiểu Thụ)"
              value={vietnameseTerm}
              onChange={(e) => setVietnameseTerm(e.target.value)}
              className="glass-input rounded-xl px-3 py-2 text-xs"
            />
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="glass-input rounded-xl px-3 py-2 text-xs"
            >
              <option value="NAME">👤 Tên Nhân Vật (NAME)</option>
              <option value="PLACE">🏯 Địa Danh (PLACE)</option>
              <option value="SECT">⚔️ Tông Môn/Phái (SECT)</option>
              <option value="ITEM">🔮 Vật Phẩm/Bảo Vật (ITEM)</option>
              <option value="SKILL">⚡ Chiêu Thức/Võ Kỹ (SKILL)</option>
              <option value="OTHER">📌 Từ Ngữ Khác (OTHER)</option>
            </select>
            <button
              type="submit"
              disabled={isSubmitting || !chineseTerm.trim() || !vietnameseTerm.trim()}
              className="bg-cyber-accent hover:bg-cyber-accent/80 text-cyber-bg font-bold px-4 py-2 rounded-xl text-xs transition-all flex items-center justify-center gap-1.5 disabled:opacity-50 shadow-lg shadow-cyber-accent/20"
            >
              {isSubmitting ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
              {selectedChapterNo > 0 ? 'Thêm Từ Vào Chương' : 'Thêm & Áp Dụng Từ Mới'}
            </button>
          </form>

          {/* Glossary Table List */}
          <div className="glass-panel rounded-2xl flex-1 flex flex-col overflow-hidden">
            {/* Table Search & Filter Bar */}
            <div className="px-5 py-3 border-b border-cyber-border/40 flex items-center justify-between flex-shrink-0">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-slate-300">
                  Danh Sách Từ Thuật Ngữ ({filteredGlossary.length} từ)
                </span>
                {selectedNovelObj && (
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-cyber-accent/20 text-cyber-accent border border-cyber-accent/30">
                    {selectedNovelObj.title_rough || selectedNovelObj.title_raw}
                    {selectedChapterNo > 0 ? ` • Chương ${selectedChapterNo}` : ''}
                  </span>
                )}
              </div>
              <div className="relative w-64">
                <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-500" />
                <input
                  type="text"
                  placeholder="Tìm theo từ Hán hoặc Hán Việt..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full glass-input rounded-lg pl-8 pr-3 py-1 text-xs"
                />
              </div>
            </div>

            {/* Table Grid */}
            <div className="flex-1 overflow-y-auto p-4">
              {filteredGlossary.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-48 text-center text-cyber-muted text-xs gap-2">
                  <BookOpen className="w-8 h-8 text-slate-600 opacity-50" />
                  <span>
                    {selectedChapterNo > 0 
                      ? 'Chương này chưa có từ thuật ngữ liên kết riêng.' 
                      : 'Chưa có từ thuật ngữ nào trong danh sách bộ truyện này.'}
                  </span>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {filteredGlossary.map((term) => {
                    const isEditingThis = editingId === term.id

                    if (isEditingThis) {
                      return (
                        <div
                          key={term.id}
                          className="flex flex-col gap-2 bg-slate-900/90 p-3.5 rounded-xl border border-amber-400/60 shadow-lg animate-fade-in text-xs col-span-1"
                        >
                          <span className="text-[10px] font-bold text-amber-300 flex items-center gap-1">
                            <Edit3 className="w-3.5 h-3.5" /> Chỉnh sửa từ thuật ngữ
                          </span>
                          <div className="grid grid-cols-2 gap-2">
                            <input
                              type="text"
                              value={editChinese}
                              onChange={(e) => setEditChinese(e.target.value)}
                              placeholder="Từ Hán"
                              className="glass-input px-2.5 py-1 text-xs rounded-lg border-cyber-accent/40"
                            />
                            <input
                              type="text"
                              value={editVietnamese}
                              onChange={(e) => setEditVietnamese(e.target.value)}
                              placeholder="Dịch Hán Việt"
                              className="glass-input px-2.5 py-1 text-xs rounded-lg border-emerald-400/40 text-emerald-300 font-bold"
                            />
                          </div>
                          <div className="flex items-center justify-between gap-2 mt-1">
                            <select
                              value={editCategory}
                              onChange={(e) => setEditCategory(e.target.value)}
                              className="glass-input px-2 py-1 text-[11px] rounded-lg"
                            >
                              <option value="NAME">👤 Tên Nhân Vật</option>
                              <option value="PLACE">🏯 Địa Danh</option>
                              <option value="SECT">⚔️ Tông Môn</option>
                              <option value="ITEM">🔮 Vật Phẩm</option>
                              <option value="SKILL">⚡ Chiêu Thức</option>
                              <option value="OTHER">📌 Từ Ngữ Khác</option>
                            </select>

                            <div className="flex items-center gap-1">
                              <button
                                onClick={() => handleSaveEdit(term.id)}
                                disabled={isSubmitting}
                                className="bg-emerald-500 hover:bg-emerald-600 text-slate-950 font-bold px-2.5 py-1 rounded-lg text-xs flex items-center gap-1 shadow-md"
                                title="Lưu và tự động thay thế vào các chương đã dịch"
                              >
                                <Check className="w-3.5 h-3.5" /> Lưu & Áp Dụng
                              </button>
                              <button
                                onClick={cancelEdit}
                                className="bg-slate-800 hover:bg-slate-700 text-slate-300 px-2 py-1 rounded-lg text-xs"
                              >
                                <X className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </div>
                        </div>
                      )
                    }

                    return (
                      <div
                        key={term.id}
                        className="flex items-center justify-between bg-slate-900/60 p-3 rounded-xl border border-cyber-border/30 hover:border-cyber-accent/40 transition-all text-xs group"
                      >
                        <div className="flex items-center gap-3 truncate">
                          <span className="font-bold text-amber-300 text-sm font-mono flex-shrink-0">{term.chinese_term}</span>
                          <span className="text-slate-500 flex-shrink-0">➔</span>
                          <div className="truncate">
                            <p className="font-bold text-emerald-400 truncate">{term.vietnamese_term}</p>
                            <span className="text-[9px] px-1.5 py-0.5 rounded bg-slate-800 text-cyber-muted border border-cyber-border/30">
                              {term.category}
                            </span>
                          </div>
                        </div>

                        <div className="flex items-center gap-1 flex-shrink-0 ml-2">
                          <button
                            onClick={() => startEdit(term)}
                            className="p-1.5 text-slate-400 hover:text-amber-300 rounded-lg hover:bg-amber-400/10 transition-all"
                            title="Chỉnh sửa từ và tự động áp dụng vào các chương"
                          >
                            <Edit3 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => deleteGlossaryTerm(selectedNovelId, term.id, selectedChapterNo > 0 ? selectedChapterNo : null)}
                            className="p-1.5 text-slate-400 hover:text-rose-400 rounded-lg hover:bg-rose-500/10 transition-all"
                            title={selectedChapterNo > 0 ? 'Gỡ liên kết khỏi chương này' : 'Xóa từ khỏi Từ điển'}
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        </>
      ) : (
        <>
          {/* Add New Correction Form */}
          <form onSubmit={handleAddCorrection} className="glass-panel p-4 rounded-2xl grid grid-cols-1 md:grid-cols-3 gap-3 flex-shrink-0">
            <input
              type="text"
              placeholder="Từ Google dịch sai (vd: Serena)"
              value={wrongText}
              onChange={(e) => setWrongText(e.target.value)}
              className="glass-input rounded-xl px-3 py-2 text-xs col-span-1"
            />
            <input
              type="text"
              placeholder="Sửa lại đúng Hán Việt (vd: Táp Nhã)"
              value={correctText}
              onChange={(e) => setCorrectText(e.target.value)}
              className="glass-input rounded-xl px-3 py-2 text-xs col-span-1 text-emerald-300 font-bold"
            />
            <button
              type="submit"
              disabled={isSubmitting || !wrongText.trim() || !correctText.trim()}
              className="bg-cyber-accent hover:bg-cyber-accent/80 text-cyber-bg font-bold px-4 py-2 rounded-xl text-xs transition-all flex items-center justify-center gap-1.5 disabled:opacity-50 shadow-lg shadow-cyber-accent/20"
            >
              {isSubmitting ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
              Thêm & Sửa Lỗi
            </button>
          </form>

          {/* Corrections Table List */}
          <div className="glass-panel rounded-2xl flex-1 flex flex-col overflow-hidden">
            {/* Table Search & Filter Bar */}
            <div className="px-5 py-3 border-b border-cyber-border/40 flex items-center justify-between flex-shrink-0">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-slate-300">
                  Danh Sách Sửa Lỗi Google ({filteredCorrections.length} từ)
                </span>
                {selectedNovelObj && (
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-cyber-accent/20 text-cyber-accent border border-cyber-accent/30">
                    {selectedNovelObj.title_rough || selectedNovelObj.title_raw} • Chương {selectedChapterNo}
                  </span>
                )}
              </div>
              <div className="relative w-64">
                <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-500" />
                <input
                  type="text"
                  placeholder="Tìm theo từ lỗi hoặc từ đúng..."
                  value={corrSearchTerm}
                  onChange={(e) => setCorrSearchTerm(e.target.value)}
                  className="w-full glass-input rounded-lg pl-8 pr-3 py-1 text-xs"
                />
              </div>
            </div>

            {/* Table Grid */}
            <div className="flex-1 overflow-y-auto p-4">
              {filteredCorrections.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-48 text-center text-cyber-muted text-xs gap-2">
                  <BookOpen className="w-8 h-8 text-slate-600 opacity-50" />
                  <span>Chương này chưa có lỗi Google nào được khai báo.</span>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {filteredCorrections.map((corr) => {
                    const isEditingThisCorr = editingCorrId === corr.id

                    if (isEditingThisCorr) {
                      return (
                        <div
                          key={corr.id}
                          className="flex flex-col gap-2 bg-slate-900/90 p-3.5 rounded-xl border border-amber-400/60 shadow-lg animate-fade-in text-xs col-span-1"
                        >
                          <span className="text-[10px] font-bold text-amber-300 flex items-center gap-1">
                            <Edit3 className="w-3.5 h-3.5" /> Chỉnh sửa lỗi Google
                          </span>
                          <div className="grid grid-cols-2 gap-2">
                            <input
                              type="text"
                              value={editWrong}
                              onChange={(e) => setEditWrong(e.target.value)}
                              placeholder="Lỗi gốc"
                              className="glass-input px-2.5 py-1 text-xs rounded-lg border-cyber-accent/40"
                            />
                            <input
                              type="text"
                              value={editCorrect}
                              onChange={(e) => setEditCorrect(e.target.value)}
                              placeholder="Sửa lại đúng"
                              className="glass-input px-2.5 py-1 text-xs rounded-lg border-emerald-400/40 text-emerald-300 font-bold"
                            />
                          </div>
                          <div className="flex items-center justify-end gap-1 mt-2">
                            <button
                              onClick={() => handleSaveEditCorr(corr.id)}
                              disabled={isSubmitting}
                              className="bg-emerald-500 hover:bg-emerald-600 text-slate-950 font-bold px-2.5 py-1 rounded-lg text-xs flex items-center gap-1 shadow-md"
                            >
                              <Check className="w-3.5 h-3.5" /> Lưu
                            </button>
                            <button
                              onClick={() => setEditingCorrId(null)}
                              className="bg-slate-800 hover:bg-slate-700 text-slate-300 px-2 py-1 rounded-lg text-xs"
                            >
                              <X className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </div>
                      )
                    }

                    return (
                      <div
                        key={corr.id}
                        className="flex items-center justify-between bg-slate-900/60 p-3 rounded-xl border border-cyber-border/30 hover:border-cyber-accent/40 transition-all text-xs group"
                      >
                        <div className="flex items-center gap-3 truncate">
                          <span className="font-bold text-rose-400 text-sm font-mono flex-shrink-0 line-through truncate max-w-[80px]">{corr.wrong_text}</span>
                          <span className="text-slate-500 flex-shrink-0">➔</span>
                          <div className="truncate">
                            <p className="font-bold text-emerald-400 truncate">{corr.correct_text}</p>
                            <span className="text-[8px] px-1.5 py-0.5 rounded bg-rose-950/20 text-rose-400 border border-rose-900/30 font-bold">
                              LỖI GG
                            </span>
                          </div>
                        </div>

                        <div className="flex items-center gap-1 flex-shrink-0 ml-2">
                          <button
                            onClick={() => {
                              setEditingCorrId(corr.id)
                              setEditWrong(corr.wrong_text)
                              setEditCorrect(corr.correct_text)
                            }}
                            className="p-1.5 text-slate-400 hover:text-amber-300 rounded-lg hover:bg-amber-400/10 transition-all"
                            title="Chỉnh sửa từ lỗi"
                          >
                            <Edit3 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => deleteCorrection(selectedNovelId, selectedChapterNo, corr.id)}
                            className="p-1.5 text-slate-400 hover:text-rose-400 rounded-lg hover:bg-rose-500/10 transition-all"
                            title="Xóa lỗi dịch"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
})

export default GlossaryTab
