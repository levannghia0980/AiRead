import React, { useState, useEffect, useRef } from 'react'
import {
  BookOpen,
  Settings,
  Play,
  Pause,
  RotateCcw,
  Plus,
  Trash2,
  Download,
  Terminal as TermIcon,
  Globe,
  RefreshCw,
  Library as LibIcon,
  FileText,
  Key,
  CheckCircle,
  XCircle,
  Eye,
  ArrowLeft,
  Save,
  ChevronRight,
  ChevronLeft,
  Wand2
} from 'lucide-react'
import { useNovelStore, ProgressData } from './store/useNovelStore'

export default function App() {
  const {
    novels,
    selectedNovel,
    glossary,
    logs,
    progress,
    packagedResult,
    provider,
    model,
    apiKeys,
    customPrompt,
    delay,
    concurrency,
    startChapter,
    endChapter,
    setSettings,
    testApiKey,
    fetchNovels,
    fetchNovelDetails,
    deleteNovel,
    fetchGlossary,
    addGlossaryTerm,
    deleteGlossaryTerm,
    startTranslation,
    pauseTranslation,
    clearJob,
    manualExport,
    resetChapters,
    fetchChapterText,
    updateChapterText,
    checkQuality,
    downloadNovel,
    addLog,
    setLogs,
    setProgress,
    setPackagedResult,
    loadSettingsFromEnv
  } = useNovelStore()

  // Local UI State
  const [activeTab, setActiveTab] = useState<'translate' | 'glossary' | 'library' | 'reader'>('translate')

  // Crawler URL State
  const [inputUrl, setInputUrl] = useState('')
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [analyzedData, setAnalyzedData] = useState<any>(null)
  const [isSaving, setIsSaving] = useState(false)

  // API Key Test State
  const [isTestingKey, setIsTestingKey] = useState(false)
  const [keyTestResult, setKeyTestResult] = useState<{ success: boolean; message: string } | null>(null)
  const [isSavedToEnv, setIsSavedToEnv] = useState(false)

  // Quality Check State
  const [isCheckingQuality, setIsCheckingQuality] = useState(false)
  const [qualityResult, setQualityResult] = useState<{ total_chapters: number; bad_count: number; bad_chapters: Array<{ chapter_no: number; title: string; status: string; issues: string[] }> } | null>(null)
  const [justFixed, setJustFixed] = useState<Set<number>>(new Set())

  // Download State
  const [isDownloading, setIsDownloading] = useState(false)

  // Reader State
  const [readingChapter, setReadingChapter] = useState<{ chapter_no: number; title: string; translated_text: string; raw_text: string } | null>(null)
  const [isLoadingChapter, setIsLoadingChapter] = useState(false)
  const [saveResult, setSaveResult] = useState<{ success: boolean; message: string; folder_path?: string } | null>(null)
  const [isEditing, setIsEditing] = useState(false)
  const [isSavingEdit, setIsSavingEdit] = useState(false)
  const editorRef = useRef<HTMLDivElement>(null)

  // Glossary Form State
  const [glossaryNovelId, setGlossaryNovelId] = useState<number>(0)
  const [chineseTerm, setChineseTerm] = useState('')
  const [vietnameseTerm, setVietnameseTerm] = useState('')
  const [glossaryCategory, setGlossaryCategory] = useState('NAME')

  // Novel-specific glossary state
  const [novelGlossary, setNovelGlossary] = useState<any[]>([])
  const [quickZh, setQuickZh] = useState('')
  const [quickVi, setQuickVi] = useState('')
  const [isAddingQuickGlossary, setIsAddingQuickGlossary] = useState(false)

  // Auto-scroll for logs terminal
  const terminalEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    fetchNovels()

    // Tải settings (bao gồm API key) từ backend .env khi khởi động
    loadSettingsFromEnv()

    // Connect to Server-Sent Events stream for real-time logs and progress updates
    const eventSource = new EventSource('/api/translation/logs')

    eventSource.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data)
        const { event: eventType, data } = payload

        if (eventType === 'init_logs') {
          setLogs(data)
        } else if (eventType === 'log') {
          addLog(data)
        } else if (eventType === 'progress') {
          setProgress(data)
        } else if (eventType === 'packaged') {
          setPackagedResult(data)
        }
      } catch (e) {
        console.error("SSE parse error", e)
      }
    }

    eventSource.onerror = (e) => {
      console.warn("SSE connection error, attempting automatic reconnect...", e)
    }

    return () => {
      eventSource.close()
    }
  }, [])

  useEffect(() => {
    if (terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs])

  // Trigger glossary fetch when glossary novel ID changes
  useEffect(() => {
    fetchGlossary(glossaryNovelId)
  }, [glossaryNovelId, novels])

  // Load selected novel's glossary automatically when selected
  useEffect(() => {
    if (selectedNovel) {
      fetch(`/api/novels/${selectedNovel.novel.id}/glossary`)
        .then(res => res.json())
        .then(data => setNovelGlossary(data))
        .catch(err => console.error("Failed to load novel glossary", err))
    } else {
      setNovelGlossary([])
    }
  }, [selectedNovel])

  // Quick Add Glossary handler
  const handleQuickAddGlossary = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedNovel || !quickZh.trim() || !quickVi.trim()) return
    setIsAddingQuickGlossary(true)
    try {
      const response = await fetch(`/api/novels/${selectedNovel.novel.id}/glossary`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          chinese_term: quickZh.trim(),
          vietnamese_term: quickVi.trim(),
          category: 'NAME'
        })
      })
      if (response.ok) {
        setQuickZh('')
        setQuickVi('')
        // Refresh novel glossary
        const res = await fetch(`/api/novels/${selectedNovel.novel.id}/glossary`)
        const data = await res.json()
        setNovelGlossary(data)
        // Also refresh global store's glossary if current view is showing it
        if (glossaryNovelId === selectedNovel.novel.id || glossaryNovelId === 0) {
          fetchGlossary(glossaryNovelId)
        }
      } else {
        alert("Thêm từ điển thất bại.")
      }
    } catch (e: any) {
      alert(`Lỗi: ${e.message}`)
    } finally {
      setIsAddingQuickGlossary(false)
    }
  }

  // Quick Delete Glossary handler
  const handleQuickDeleteGlossary = async (termId: number) => {
    if (!selectedNovel) return
    try {
      const response = await fetch(`/api/novels/${selectedNovel.novel.id}/glossary/${termId}`, {
        method: 'DELETE'
      })
      if (response.ok) {
        setNovelGlossary(prev => prev.filter(g => g.id !== termId))
        // Also refresh global store's glossary if current view is showing it
        if (glossaryNovelId === selectedNovel.novel.id || glossaryNovelId === 0) {
          fetchGlossary(glossaryNovelId)
        }
      } else {
        alert("Xóa từ điển thất bại.")
      }
    } catch (e: any) {
      alert(`Lỗi: ${e.message}`)
    }
  }

  // Action Handlers
  const handleAnalyzeUrl = async () => {
    if (!inputUrl) return
    setIsAnalyzing(true)
    setAnalyzedData(null)
    try {
      const res = await fetch('/api/novels/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: inputUrl })
      })
      if (!res.ok) {
        throw new Error("Lỗi cào dữ liệu từ trang nguồn.")
      }
      const data = await res.json()
      setAnalyzedData(data)
    } catch (err: any) {
      alert(err.message || "Failed to analyze URL")
    } finally {
      setIsAnalyzing(false)
    }
  }

  const handleSaveNovel = async () => {
    if (!analyzedData) return
    setIsSaving(true)
    try {
      const payload = {
        title: analyzedData.title,
        author: analyzedData.author,
        cover_url: analyzedData.cover_url,
        source_url: inputUrl,
        genres: analyzedData.genres,
        status: analyzedData.status,
        chapters: analyzedData.chapters
      }
      const res = await fetch('/api/novels/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      if (res.ok) {
        const data = await res.json()
        await fetchNovels()
        // Automatically switch to details
        await fetchNovelDetails(data.novel_id)
        setAnalyzedData(null)
        setInputUrl('')
      }
    } catch (e) {
      alert("Failed to save novel")
    } finally {
      setIsSaving(false)
    }
  }

  const handleStart = async (novelId: number) => {
    try {
      await startTranslation(novelId)
    } catch (e: any) {
      alert(e.message)
    }
  }

  const handleAddGlossary = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!chineseTerm || !vietnameseTerm) return
    await addGlossaryTerm(glossaryNovelId, chineseTerm.trim(), vietnameseTerm.trim(), glossaryCategory)
    setChineseTerm('')
    setVietnameseTerm('')
  }

  // Model defaults matching providers
  const getModelsForProvider = (prov: string) => {
    switch (prov) {
      case 'gemini':
        return [
          'gemini-3.5-flash',
          'gemini-3.1-flash-lite',
          'gemini-3.1-pro',
          'gemini-2.5-flash',
          'gemini-2.5-flash-lite',
          'gemini-2.5-pro'
        ]
      case 'openai':
        return ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'o1-mini']
      case 'claude':
        return ['claude-3-5-sonnet-latest', 'claude-3-5-haiku-latest', 'claude-3-opus-20240229']
      case 'openrouter':
        return [
          'openrouter/free',
          'meta-llama/llama-3.3-70b-instruct:free',
          'nousresearch/hermes-3-llama-3.1-405b:free',
          'deepseek/deepseek-chat',
          'qwen/qwen-2.5-72b-instruct'
        ]
      default:
        return []
    }
  }

  // Handle Test API Key
  const handleTestKey = async () => {
    setIsTestingKey(true)
    setKeyTestResult(null)
    try {
      const result = await testApiKey()
      setKeyTestResult(result)
    } catch (e: any) {
      setKeyTestResult({ success: false, message: e.message })
    } finally {
      setIsTestingKey(false)
    }
  }

  // Handle Read Chapter
  const handleReadChapter = async (novelId: number, chapterNo: number) => {
    setIsLoadingChapter(true)
    setReadingChapter(null)
    setIsEditing(false)
    try {
      const data = await fetchChapterText(novelId, chapterNo)
      setReadingChapter(data)
    } finally {
      setIsLoadingChapter(false)
    }
  }

  // Handle Save Edit Chapter Text
  const handleSaveEdit = async () => {
    if (!selectedNovel || !readingChapter) return
    const newHtml = editorRef.current?.innerHTML
    if (!newHtml) return
    setIsSavingEdit(true)
    try {
      const success = await updateChapterText(
        selectedNovel.novel.id,
        readingChapter.chapter_no,
        newHtml
      )
      if (success) {
        setReadingChapter({
          ...readingChapter,
          translated_text: newHtml
        })
        setIsEditing(false)
      } else {
        alert("Không thể lưu bản dịch chỉnh sửa. Có lỗi xảy ra.")
      }
    } catch (e: any) {
      alert("Lỗi kết nối: " + e.message)
    } finally {
      setIsSavingEdit(false)
    }
  }


  // Handle Reset Chapters
  const [isResetting, setIsResetting] = useState(false)
  const handleResetChapters = async (novelId: number, chapterNos?: number[]) => {
    const confirmMsg = chapterNos
      ? `Bạn có chắc muốn XÓA BẢN DỊCH, XÓA CACHE và CÀO LẠI từ đầu chương ${chapterNos.join(', ')} không?`
      : "Bạn có chắc muốn XÓA BẢN DỊCH VÀ CACHE của TOÀN BỘ CÁC CHƯƠNG để cào/dịch lại từ đầu không?"
    if (!window.confirm(confirmMsg)) return

    setIsResetting(true)
    try {
      await resetChapters(novelId, chapterNos)
      await fetchNovelDetails(novelId)
      setQualityResult(null)
    } catch (e: any) {
      alert(`Lỗi khi reset chương: ${e.message}`)
    } finally {
      setIsResetting(false)
    }
  }

  // Handle Check Quality
  const handleCheckQuality = async (novelId: number) => {
    setIsCheckingQuality(true)
    setQualityResult(null)
    setJustFixed(new Set())
    try {
      const result = await checkQuality(novelId)
      setQualityResult(result)
    } catch (e: any) {
      alert(`Lỗi kiểm tra chất lượng: ${e.message}`)
    } finally {
      setIsCheckingQuality(false)
    }
  }

  // Handle Quick Fix Chapter
  const [isFixingChapters, setIsFixingChapters] = useState<Record<number, boolean>>({})
  const handleQuickFixChapter = async (novelId: number, chapterNo: number) => {
    if (!apiKeys || !apiKeys.trim()) {
      alert("Bạn cần cấu hình API Key ở cột cấu hình bên phải trước khi dùng tính năng Sửa nhanh!")
      return
    }
    
    setIsFixingChapters(prev => ({ ...prev, [chapterNo]: true }))
    try {
      const response = await fetch(`/api/novels/${novelId}/chapters/${chapterNo}/quick-fix`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          provider: provider,
          model: model,
          api_key: apiKeys,
          prompt: customPrompt
        })
      })
      const result = await response.json()
      if (response.ok && result.success) {
        setJustFixed(prev => {
          const next = new Set(prev)
          next.add(chapterNo)
          return next
        })
        await fetchNovelDetails(novelId)
      } else {
        alert(`Sửa nhanh thất bại: ${result.detail || result.message || 'Lỗi không xác định'}`)
      }
    } catch (e: any) {
      alert(`Lỗi kết nối khi sửa nhanh: ${e.message}`)
    } finally {
      setIsFixingChapters(prev => ({ ...prev, [chapterNo]: false }))
    }
  }

  // Handle Ignore Quality Error
  const handleIgnoreQuality = async (novelId: number, chapterNo: number) => {
    try {
      const response = await fetch(`/api/novels/${novelId}/chapters/${chapterNo}/ignore-quality`, {
        method: 'POST'
      })
      const result = await response.json()
      if (response.ok && result.success) {
        handleCheckQuality(novelId)
      } else {
        alert(`Bỏ qua lỗi thất bại: ${result.message || 'Lỗi không xác định'}`)
      }
    } catch (e: any) {
      alert(`Lỗi kết nối: ${e.message}`)
    }
  }

  // Handle Quick Fix All Chapters
  const [isFixingAll, setIsFixingAll] = useState(false)
  const handleQuickFixAll = async (novelId: number, badChapters: { chapter_no: number }[]) => {
    if (!apiKeys || !apiKeys.trim()) {
      alert("Bạn cần cấu hình API Key ở cột cấu hình bên phải trước khi dùng tính năng Sửa nhanh!")
      return
    }
    if (!window.confirm(`Bạn có chắc muốn dùng AI TỰ ĐỘNG SỬA NHANH tất cả ${badChapters.length} chương lỗi không? Quá trình sẽ được chạy lần lượt.`)) {
      return
    }
    
    setIsFixingAll(true)
    let successCount = 0
    let failCount = 0
    
    for (const bc of badChapters) {
      try {
        setIsFixingChapters(prev => ({ ...prev, [bc.chapter_no]: true }))
        const response = await fetch(`/api/novels/${novelId}/chapters/${bc.chapter_no}/quick-fix`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            provider: provider,
            model: model,
            api_key: apiKeys,
            prompt: customPrompt
          })
        })
        const result = await response.json()
        if (response.ok && result.success) {
          successCount++
          setJustFixed(prev => {
            const next = new Set(prev)
            next.add(bc.chapter_no)
            return next
          })
        } else {
          failCount++
        }
      } catch (e) {
        failCount++
      } finally {
        setIsFixingChapters(prev => ({ ...prev, [bc.chapter_no]: false }))
      }
    }
    
    setIsFixingAll(false)
    alert(`Đã hoàn tất sửa nhanh hàng loạt! Thành công: ${successCount}, Thất bại: ${failCount}`)
    await fetchNovelDetails(novelId)
  }

  // Handle Download Novel
  const handleDownloadNovel = async (novelId: number, fmt: 'txt' | 'docx') => {
    setIsDownloading(true)
    try {
      await downloadNovel(novelId, fmt)
    } catch (e: any) {
      alert(`Lỗi tải file: ${e.message}`)
    } finally {
      setIsDownloading(false)
    }
  }

  // Open Reader for a novel
  const handleOpenReader = async (novelId: number) => {
    setReadingChapter(null)
    setSaveResult(null)
    setQualityResult(null)
    await fetchNovelDetails(novelId)
    setActiveTab('reader')
  }


  // Percentage Helper
  const getPercentage = (p: ProgressData | null) => {
    if (!p || !p.totalChapters) return 0
    return Math.round((p.completedChapters || 0) / p.totalChapters * 100)
  }

  return (
    <div className="h-screen w-screen bg-[#070A13] text-slate-100 flex flex-col overflow-hidden antialiased">
      {/* Decorative Blur Orbs */}
      <div className="absolute top-[-10%] left-[-10%] w-[500px] h-[500px] rounded-full bg-cyber-accent opacity-[0.03] blur-[150px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[600px] h-[600px] rounded-full bg-cyber-purple opacity-[0.04] blur-[150px] pointer-events-none" />

      {/* Premium Navbar */}
      <header className="flex-shrink-0 sticky top-0 z-50 glass-panel border-b border-cyber-border px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyber-accent to-cyber-purple flex items-center justify-center neon-border-cyan animate-glow-pulse">
            <BookOpen className="w-6 h-6 text-[#070A13] stroke-[2.5]" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-wider cyber-gradient-text">AiRead v2</h1>
            <p className="text-xs text-cyber-muted font-medium uppercase tracking-widest">Premium Translation Suite</p>
          </div>
        </div>

        {/* Tab Selection */}
        <nav className="flex bg-slate-950/60 p-1 rounded-xl border border-cyber-border">
          <button
            onClick={() => setActiveTab('translate')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${activeTab === 'translate' ? 'bg-gradient-to-r from-cyber-accent/20 to-cyber-purple/20 border border-cyber-accent/30 text-cyber-accent' : 'text-slate-400 hover:text-slate-200'}`}
          >
            <BookOpen className="w-4 h-4" /> Dịch Truyện
          </button>
          <button
            onClick={() => setActiveTab('glossary')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${activeTab === 'glossary' ? 'bg-gradient-to-r from-cyber-accent/20 to-cyber-purple/20 border border-cyber-accent/30 text-cyber-accent' : 'text-slate-400 hover:text-slate-200'}`}
          >
            <Globe className="w-4 h-4" /> Thuật Ngữ
          </button>
          <button
            onClick={() => setActiveTab('library')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${activeTab === 'library' ? 'bg-gradient-to-r from-cyber-accent/20 to-cyber-purple/20 border border-cyber-accent/30 text-cyber-accent' : 'text-slate-400 hover:text-slate-200'}`}
          >
            <LibIcon className="w-4 h-4" /> Thư Viện ({novels.length})
          </button>
          <button
            onClick={() => setActiveTab('reader')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${activeTab === 'reader' ? 'bg-gradient-to-r from-cyber-accent/20 to-cyber-purple/20 border border-cyber-accent/30 text-cyber-accent' : 'text-slate-400 hover:text-slate-200'}`}
          >
            <Eye className="w-4 h-4" /> Đọc Truyện
          </button>
        </nav>
      </header>

      {/* Main Content Layout */}
      <main className="flex-grow lg:flex-1 max-w-7xl w-full mx-auto p-4 lg:p-6 grid grid-cols-1 lg:grid-cols-3 gap-6 overflow-hidden min-h-0">

        {/* Left Columns (Inputs, Control Panels, Glossary forms depending on tabs) */}
        <div className="lg:col-span-2 flex flex-col gap-4 overflow-hidden h-full min-h-0">

          {activeTab === 'translate' && (
            <>
              {/* Novel URL Input Card */}
              <div className="glass-panel rounded-2xl p-6 flex flex-col gap-4">
                <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
                  <Globe className="w-5 h-5 text-cyber-accent" /> Nhập Link Truyện Nguồn
                </h2>
                <div className="flex gap-3">
                  <input
                    type="text"
                    value={inputUrl}
                    onChange={(e) => setInputUrl(e.target.value)}
                    placeholder="Nhập link truyện Trung Quốc (Ví dụ: https://69shuba.cx/book/52141/)"
                    className="flex-1 glass-input rounded-xl px-4 py-3 text-sm"
                  />
                  <button
                    onClick={handleAnalyzeUrl}
                    disabled={isAnalyzing || !inputUrl}
                    className="bg-cyber-accent hover:bg-cyber-accent/80 text-cyber-bg font-semibold px-6 py-3 rounded-xl text-sm transition-all duration-200 shadow-lg shadow-cyber-accent/10 flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {isAnalyzing ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />} Phân Tích
                  </button>
                </div>

                {/* Analyzed metadata details */}
                {analyzedData && (
                  <div className="mt-4 border-t border-cyber-border pt-4 flex gap-4 animate-fade-in">
                    {analyzedData.cover_url && (
                      <img
                        src={analyzedData.cover_url}
                        alt="Novel cover"
                        className="w-24 h-32 object-cover rounded-lg border border-cyber-border"
                      />
                    )}
                    <div className="flex-1 flex flex-col justify-between">
                      <div>
                        <h3 className="text-md font-bold text-cyber-accent">{analyzedData.title}</h3>
                        <p className="text-sm text-slate-400 mt-1">Tác giả: <span className="text-slate-200">{analyzedData.author}</span></p>
                        <p className="text-sm text-slate-400">Thể loại: <span className="text-slate-200">{analyzedData.genres || "N/A"}</span></p>
                        <p className="text-sm text-slate-400">Số chương: <span className="text-cyber-accent font-semibold">{analyzedData.chapters?.length}</span></p>
                      </div>
                      <button
                        onClick={handleSaveNovel}
                        disabled={isSaving}
                        className="w-fit mt-3 bg-gradient-to-r from-cyber-accent to-cyber-purple hover:opacity-90 text-cyber-bg font-bold px-6 py-2.5 rounded-xl text-xs uppercase tracking-wider transition-all duration-200 shadow-md flex items-center gap-2"
                      >
                        {isSaving ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : null} Lưu Vào Database & Dịch
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Translation Progress & Interactive Logs Card */}
              <div className="glass-panel rounded-2xl p-4 lg:p-6 flex-grow lg:flex-1 lg:min-h-0 flex flex-col gap-4 overflow-hidden">
                <div className="flex items-center justify-between border-b border-cyber-border pb-3">
                  <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
                    <TermIcon className="w-5 h-5 text-cyber-purple" /> Trình Giám Sát Tiến Trình Dịch
                  </h2>
                  {progress?.isRunning && (
                    <span className="flex h-2.5 w-2.5 relative">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyber-success opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-cyber-success"></span>
                    </span>
                  )}
                </div>

                {/* Progress Details */}
                {progress?.novelTitle ? (
                  <div className="bg-slate-950/40 p-4 rounded-xl border border-cyber-border flex flex-col gap-3 flex-shrink-0">
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="font-bold text-cyber-accent text-sm">{progress.novelTitle}</h3>
                        <p className="text-xs text-cyber-muted capitalize mt-0.5">Trạng thái: <span className="text-slate-300 font-semibold">{progress.stage}</span></p>
                      </div>
                      <div className="text-right">
                        <span className="text-lg font-extrabold text-cyber-accent">{getPercentage(progress)}%</span>
                        <p className="text-[10px] text-cyber-muted uppercase tracking-wider">Chương {progress.completedChapters}/{progress.totalChapters}</p>
                      </div>
                    </div>

                    {/* Neon Progress Bar */}
                    <div className="w-full bg-slate-900 rounded-full h-2.5 overflow-hidden border border-cyber-border">
                      <div
                        className="bg-gradient-to-r from-cyber-accent to-cyber-purple h-full rounded-full transition-all duration-500 ease-out"
                        style={{ width: `${getPercentage(progress)}%` }}
                      />
                    </div>

                    {/* Tiny stats */}
                    <div className="flex justify-between text-xs text-cyber-muted border-t border-cyber-border/40 pt-2 mt-1">
                      <span>Đang xử lý chương: <strong className="text-slate-300">{progress.currentChapterNo || "N/A"}</strong></span>
                      <span>Chương lỗi: <strong className={progress.failedChapters && progress.failedChapters > 0 ? "text-cyber-danger" : "text-slate-300"}>{progress.failedChapters || 0}</strong></span>
                    </div>
                  </div>
                ) : (
                  <div className="bg-slate-950/20 py-8 text-center text-sm text-cyber-muted rounded-xl border border-dashed border-cyber-border flex-shrink-0">
                    Chưa có công việc dịch nào đang chạy. Chọn truyện trong Thư Viện để bắt đầu dịch.
                  </div>
                )}

                {/* Terminal logs display */}
                <div className="flex-grow lg:flex-1 lg:min-h-0 flex flex-col gap-2">
                  <span className="text-xs uppercase tracking-wider text-cyber-muted font-bold flex items-center gap-1.5"><TermIcon className="w-3.5 h-3.5" /> Log Hệ Thống (SSE)</span>
                  <div className="flex-grow lg:flex-1 lg:min-h-0 bg-slate-950/80 rounded-xl p-4 font-mono text-xs overflow-y-auto border border-cyber-border flex flex-col gap-2 text-slate-300">
                    {logs.length === 0 ? (
                      <span className="text-slate-500 italic">Hàng đợi log trống...</span>
                    ) : (
                      logs.map((log, idx) => {
                        let textClass = "text-slate-300"
                        if (log.level === "danger" || log.level === "error") textClass = "text-cyber-danger"
                        else if (log.level === "success") textClass = "text-cyber-success"
                        else if (log.level === "warning") textClass = "text-yellow-400"

                        return (
                          <div key={idx} className="flex gap-2">
                            <span className="text-slate-500">[{log.time}]</span>
                            <span className={textClass}>{log.message}</span>
                          </div>
                        )
                      })
                    )}
                    <div ref={terminalEndRef} />
                  </div>
                </div>

                {/* Download links if packaged */}
                {packagedResult?.success && (
                  <div className="bg-gradient-to-r from-cyber-success/10 to-transparent border border-cyber-success/30 p-4 rounded-xl flex flex-col gap-2.5 animate-fade-in">
                    <span className="text-sm font-bold text-cyber-success flex items-center gap-1.5"><Download className="w-4 h-4" /> Đóng gói hoàn tất! Tải sách của bạn:</span>
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
                      {packagedResult.txt && (
                        <a href={packagedResult.txt} download className="flex items-center justify-center gap-1.5 bg-slate-900 hover:bg-slate-800 text-xs py-2 px-3 rounded-lg border border-cyber-border font-medium text-slate-200" title="Tải file TXT đầy đủ tiêu đề chương">
                          <FileText className="w-3.5 h-3.5 text-yellow-500" /> Tải TXT
                        </a>
                      )}
                      {packagedResult.txt_clean && (
                        <a href={packagedResult.txt_clean} download className="flex items-center justify-center gap-1.5 bg-slate-900 hover:bg-slate-800 text-xs py-2 px-3 rounded-lg border border-cyber-border font-medium text-slate-200" title="Tải file TXT gộp toàn bộ truyện đã xóa tiêu đề chương">
                          <FileText className="w-3.5 h-3.5 text-orange-500" /> TXT Liền Mạch
                        </a>
                      )}
                      {packagedResult.epub && (
                        <a href={packagedResult.epub} download className="flex items-center justify-center gap-1.5 bg-slate-900 hover:bg-slate-800 text-xs py-2 px-3 rounded-lg border border-cyber-border font-medium text-slate-200">
                          <BookOpen className="w-3.5 h-3.5 text-cyber-accent" /> Tải EPUB
                        </a>
                      )}
                      {packagedResult.docx && (
                        <a href={packagedResult.docx} download className="flex items-center justify-center gap-1.5 bg-slate-900 hover:bg-slate-800 text-xs py-2 px-3 rounded-lg border border-cyber-border font-medium text-slate-200">
                          <FileText className="w-3.5 h-3.5 text-blue-500" /> Tải DOCX
                        </a>
                      )}
                      {packagedResult.html && (
                        <a href={packagedResult.html} download className="flex items-center justify-center gap-1.5 bg-slate-900 hover:bg-slate-800 text-xs py-2 px-3 rounded-lg border border-cyber-border font-medium text-slate-200">
                          <Globe className="w-3.5 h-3.5 text-cyber-success" /> Tải HTML Book
                        </a>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </>
          )}

          {activeTab === 'glossary' && (
            <div className="glass-panel rounded-2xl p-4 lg:p-6 flex-grow lg:flex-1 lg:min-h-0 flex flex-col gap-4 overflow-hidden">
              <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
                <Globe className="w-5 h-5 text-cyber-accent" /> Quản Lý Từ Điển Thuật Ngữ
              </h2>

              <form onSubmit={handleAddGlossary} className="grid grid-cols-1 md:grid-cols-4 gap-3 bg-slate-950/40 p-4 rounded-xl border border-cyber-border flex-shrink-0">
                <div className="flex flex-col gap-1.5">
                  <label className="text-[10px] text-cyber-muted uppercase tracking-wider font-bold">Từ Gốc (Tiếng Trung)</label>
                  <input
                    type="text"
                    placeholder="Ví dụ: 苏宇"
                    value={chineseTerm}
                    onChange={(e) => setChineseTerm(e.target.value)}
                    className="glass-input rounded-lg px-3 py-2 text-xs"
                    required
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="text-[10px] text-cyber-muted uppercase tracking-wider font-bold">Bản Dịch Nghĩa (Tiếng Việt)</label>
                  <input
                    type="text"
                    placeholder="Ví dụ: Tô Vũ"
                    value={vietnameseTerm}
                    onChange={(e) => setVietnameseTerm(e.target.value)}
                    className="glass-input rounded-lg px-3 py-2 text-xs"
                    required
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="text-[10px] text-cyber-muted uppercase tracking-wider font-bold">Loại Thuật Ngữ</label>
                  <select
                    value={glossaryCategory}
                    onChange={(e) => setGlossaryCategory(e.target.value)}
                    className="glass-input rounded-lg px-3 py-2 text-xs bg-slate-900"
                  >
                    <option value="NAME">Tên Nhân Vật</option>
                    <option value="PLACE">Địa Danh</option>
                    <option value="SECT">Môn Phái</option>
                    <option value="ITEM">Vật Phẩm/Chiêu Thức</option>
                    <option value="OTHER">Khác</option>
                  </select>
                </div>
                <div className="flex items-end">
                  <button
                    type="submit"
                    className="w-full bg-cyber-accent hover:bg-cyber-accent/80 text-cyber-bg font-bold py-2 rounded-lg text-xs uppercase flex items-center justify-center gap-1.5 transition-all duration-200"
                  >
                    <Plus className="w-3.5 h-3.5" /> Thêm Từ Điển
                  </button>
                </div>
              </form>

              {/* Glossary Novel Scope Filter */}
              <div className="flex items-center gap-3 flex-shrink-0">
                <span className="text-xs text-cyber-muted font-bold uppercase tracking-wider">Phạm Vi Từ Điển:</span>
                <select
                  value={glossaryNovelId}
                  onChange={(e) => setGlossaryNovelId(Number(e.target.value))}
                  className="glass-input rounded-lg px-3 py-1.5 text-xs bg-[#070A13]"
                >
                  <option value={0}>Dùng Chung Toàn Cầu (Global)</option>
                  {novels.map((n) => (
                    <option key={n.id} value={n.id}>Truyện: {n.title}</option>
                  ))}
                </select>
              </div>

              {/* Glossary List */}
              <div className="border border-cyber-border rounded-xl overflow-hidden bg-slate-950/20 flex-grow lg:flex-1 lg:overflow-y-auto lg:min-h-0">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-950/60 uppercase tracking-widest text-[10px] text-cyber-muted border-b border-cyber-border">
                    <tr>
                      <th className="px-4 py-3">Tiếng Trung (Từ gốc)</th>
                      <th className="px-4 py-3">Tiếng Việt (Dịch nghĩa)</th>
                      <th className="px-4 py-3">Phân Loại</th>
                      <th className="px-4 py-3 text-right">Hành Động</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-cyber-border/40 font-mono text-slate-300">
                    {glossary.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="px-4 py-8 text-center text-cyber-muted italic font-sans">
                          Danh sách từ điển trống. Hãy nhập thêm thuật ngữ đầu tiên.
                        </td>
                      </tr>
                    ) : (
                      glossary.map((g) => (
                        <tr key={g.id} className="hover:bg-white/5 transition-all">
                          <td className="px-4 py-3 text-slate-100 font-bold">{g.chinese_term}</td>
                          <td className="px-4 py-3 text-cyber-accent">{g.vietnamese_term}</td>
                          <td className="px-4 py-3">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-sans font-bold ${g.category === 'NAME' ? 'bg-purple-900/60 text-purple-300' :
                                g.category === 'PLACE' ? 'bg-blue-900/60 text-blue-300' :
                                  g.category === 'SECT' ? 'bg-emerald-900/60 text-emerald-300' :
                                    'bg-slate-800 text-slate-300'
                              }`}>
                              {g.category}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-right">
                            <button
                              onClick={() => deleteGlossaryTerm(glossaryNovelId, g.id)}
                              className="text-slate-500 hover:text-cyber-danger p-1 rounded transition-colors"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab === 'library' && (
            <div className="glass-panel rounded-2xl p-4 lg:p-6 flex-grow lg:flex-1 lg:min-h-0 flex flex-col gap-4 overflow-hidden">
              <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
                <LibIcon className="w-5 h-5 text-cyber-accent" /> Thư Viện Truyện Dịch
              </h2>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 lg:flex-grow lg:flex-1 lg:overflow-y-auto lg:min-h-0 pr-1">
                {novels.length === 0 ? (
                  <div className="col-span-2 py-12 text-center text-cyber-muted border border-dashed border-cyber-border rounded-xl">
                    Chưa có truyện nào trong thư viện. Sử dụng tính năng "Dịch Truyện" để phân tích và lưu truyện mới.
                  </div>
                ) : (
                  novels.map((n) => (
                    <div
                      key={n.id}
                      className={`glass-card p-4 rounded-xl flex gap-3 cursor-pointer ${selectedNovel?.novel.id === n.id ? 'border-cyber-accent shadow-md shadow-cyber-accent/5' : ''
                        }`}
                      onClick={() => handleOpenReader(n.id)}
                    >
                      {n.cover_url ? (
                        <img src={n.cover_url} alt="cover" className="w-16 h-20 object-cover rounded-lg border border-cyber-border" />
                      ) : (
                        <div className="w-16 h-20 bg-slate-900 flex items-center justify-center rounded-lg border border-cyber-border">
                          <BookOpen className="w-6 h-6 text-slate-600" />
                        </div>
                      )}
                      <div className="flex-1 flex flex-col justify-between overflow-hidden">
                        <div>
                          <h3 className="font-bold text-sm text-slate-200 truncate">{n.title}</h3>
                          <p className="text-xs text-cyber-muted truncate mt-0.5">Tác giả: {n.author}</p>
                          <span className="text-[10px] px-1.5 py-0.5 bg-slate-950/60 rounded border border-cyber-border text-slate-400 font-bold uppercase tracking-wider">{n.status}</span>
                        </div>
                        <div className="flex justify-end gap-2 mt-2">
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              handleOpenReader(n.id)
                            }}
                            className="text-cyber-accent hover:text-cyber-accent/80 p-1 rounded transition-colors"
                            title="Đọc truyện"
                          >
                            <Eye className="w-4 h-4" />
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              deleteNovel(n.id)
                            }}
                            className="text-slate-500 hover:text-cyber-danger p-1 rounded transition-colors"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

          {/* READER TAB */}
          {activeTab === 'reader' && (
            <div className="glass-panel rounded-2xl p-0 flex-grow lg:flex-1 lg:min-h-0 flex flex-col overflow-hidden h-full">
              {!selectedNovel ? (
                <div className="flex-1 flex flex-col items-center justify-center gap-4 p-8">
                  <Eye className="w-12 h-12 text-slate-600" />
                  <p className="text-cyber-muted text-sm">Chưa chọn truyện. Vào <strong className="text-cyber-accent cursor-pointer" onClick={() => setActiveTab('library')}>Thư Viện</strong> để chọn truyện cần đọc.</p>
                </div>
              ) : readingChapter ? (() => {
                const chaptersSorted = selectedNovel ? [...selectedNovel.chapters].sort((a, b) => a.chapter_no - b.chapter_no) : [];
                const currentIndex = chaptersSorted.findIndex(c => c.chapter_no === readingChapter.chapter_no);
                const prevChapter = currentIndex > 0 ? chaptersSorted[currentIndex - 1] : null;
                const nextChapter = currentIndex >= 0 && currentIndex < chaptersSorted.length - 1 ? chaptersSorted[currentIndex + 1] : null;

                return (
                  /* Reading View */
                  <div className="flex flex-col h-full relative">
                    {/* Reader Header */}
                    <div className="sticky top-0 z-10 glass-panel border-b border-cyber-border px-5 py-3 flex items-center justify-between rounded-t-2xl">
                      <button
                        onClick={() => setReadingChapter(null)}
                        className="flex items-center gap-1.5 text-cyber-accent hover:text-cyber-accent/80 text-xs font-bold transition-colors"
                      >
                        <ArrowLeft className="w-4 h-4" /> Quay lại
                      </button>
                      <h3 className="text-sm font-bold text-slate-200 truncate max-w-[300px] md:max-w-[400px]">
                        Chương {readingChapter.chapter_no}: {readingChapter.title}
                      </h3>
                      {/* Top Header Mini Navigation */}
                      <div className="flex items-center gap-2">
                        {!isEditing ? (
                          <>
                            <button
                              onClick={() => setIsEditing(true)}
                              className="flex items-center gap-1.5 px-3 py-1 rounded bg-slate-900/60 hover:bg-slate-900 border border-cyber-border/40 text-xs font-bold text-slate-300 hover:text-cyber-accent transition-all"
                            >
                              <Settings className="w-3.5 h-3.5" /> Sửa bản dịch
                            </button>
                            <button
                              onClick={() => prevChapter && handleReadChapter(selectedNovel.novel.id, prevChapter.chapter_no)}
                              disabled={!prevChapter}
                              className="p-1 rounded bg-slate-900/60 hover:bg-slate-900 border border-cyber-border/40 text-slate-300 hover:text-cyber-accent disabled:opacity-30 disabled:hover:text-slate-300 transition-all"
                              title={prevChapter ? `Chương trước: ${prevChapter.title}` : "Đây là chương đầu tiên"}
                            >
                              <ChevronLeft className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => nextChapter && handleReadChapter(selectedNovel.novel.id, nextChapter.chapter_no)}
                              disabled={!nextChapter}
                              className="p-1 rounded bg-slate-900/60 hover:bg-slate-900 border border-cyber-border/40 text-slate-300 hover:text-cyber-accent disabled:opacity-30 disabled:hover:text-slate-300 transition-all"
                              title={nextChapter ? `Chương sau: ${nextChapter.title}` : "Đây là chương cuối cùng"}
                            >
                              <ChevronRight className="w-4 h-4" />
                            </button>
                          </>
                        ) : (
                          <>
                            <button
                              onClick={handleSaveEdit}
                              disabled={isSavingEdit}
                              className="flex items-center gap-1.5 px-3 py-1 rounded bg-green-500/20 hover:bg-green-500/30 border border-green-500/40 text-xs font-bold text-green-400 hover:text-green-300 transition-all disabled:opacity-50"
                            >
                              <Save className="w-3.5 h-3.5" /> {isSavingEdit ? 'Đang lưu...' : 'Lưu lại'}
                            </button>
                            <button
                              onClick={() => setIsEditing(false)}
                              disabled={isSavingEdit}
                              className="flex items-center gap-1.5 px-3 py-1 rounded bg-slate-900 hover:bg-slate-800 border border-cyber-border/40 text-xs font-bold text-slate-400 hover:text-slate-200 transition-all"
                            >
                              Hủy
                            </button>
                          </>
                        )}
                      </div>
                    </div>

                    {/* Reader Body */}
                    <div className="flex-grow lg:flex-1 lg:min-h-0 overflow-y-auto p-6 md:px-12 md:py-8 pb-24">
                      {isEditing ? (
                        <div className="flex flex-col gap-4 h-full lg:min-h-0">
                          <div className="bg-slate-950/40 border border-cyber-border/30 rounded-xl px-4 py-2.5 text-xs text-cyber-muted leading-relaxed flex-shrink-0">
                            💡 <strong>Mẹo chỉnh sửa:</strong> Bạn có thể nhấp chuột trực tiếp vào nội dung bên phải để sửa bản dịch. Các từ/dòng tô màu biểu thị đoạn dịch lách luật (hoặc AI dịch dự phòng). Thay đổi từ ngữ và bấm <strong>Lưu lại</strong> ở góc trên bên phải để cập nhật vào cơ sở dữ liệu và đồng bộ hóa các file txt đã lưu.
                          </div>
                          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-stretch flex-grow lg:flex-1 lg:min-h-0">
                            {/* Column 1: Chinese text */}
                            <div className="flex flex-col gap-2 lg:h-full lg:min-h-0">
                              <span className="text-[10px] text-cyber-muted uppercase tracking-wider font-bold flex-shrink-0">Bản gốc tiếng Trung</span>
                              <div className="text-slate-400 bg-slate-950/40 border border-cyber-border/40 rounded-xl p-4 text-sm leading-relaxed overflow-y-auto lg:h-[35vh] lg:max-h-[35vh] lg:flex-1 font-mono whitespace-pre-line">
                                {readingChapter.raw_text || "Không có bản gốc tiếng Trung."}
                              </div>
                            </div>
                            {/* Column 2: Editable text */}
                            <div className="flex flex-col gap-2 lg:h-full lg:min-h-0">
                              <span className="text-[10px] text-cyber-accent uppercase tracking-wider font-bold flex-shrink-0">Bản dịch tiếng Việt (Nhấp để sửa)</span>
                              <div
                                ref={editorRef}
                                contentEditable={true}
                                suppressContentEditableWarning={true}
                                className="text-slate-200 bg-slate-950/80 border border-cyber-accent/30 focus:border-cyber-accent focus:outline-none rounded-xl p-4 text-sm leading-relaxed overflow-y-auto lg:h-[35vh] lg:max-h-[35vh] lg:flex-1 whitespace-pre-line outline-none"
                                dangerouslySetInnerHTML={{ __html: readingChapter.translated_text }}
                              />
                            </div>
                          </div>
                        </div>
                      ) : (
                        <article className="prose prose-invert prose-sm max-w-none">
                          <h2 className="text-lg font-bold text-cyber-accent mb-4 border-b border-cyber-border pb-3">
                            {readingChapter.title}
                          </h2>
                          <div className="text-slate-300 leading-relaxed whitespace-pre-line text-sm">
                            {readingChapter.translated_text ? (
                              <div dangerouslySetInnerHTML={{ __html: readingChapter.translated_text }} />
                            ) : (
                              <span className="italic text-cyber-muted">Chương này chưa được dịch.</span>
                            )}
                          </div>
                        </article>
                      )}
                    </div>

                    {/* Sticky Reader Footer Controls */}
                    {!isEditing && (
                      <div className="absolute bottom-0 left-0 right-0 z-10 glass-panel border-t border-cyber-border px-5 py-3.5 flex items-center justify-between rounded-b-2xl">
                        <button
                          onClick={() => prevChapter && handleReadChapter(selectedNovel.novel.id, prevChapter.chapter_no)}
                          disabled={!prevChapter}
                          className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-slate-900/60 hover:bg-slate-900 border border-cyber-border/40 text-xs font-bold text-slate-300 hover:text-cyber-accent disabled:opacity-30 disabled:hover:text-slate-300 transition-all"
                        >
                          <ChevronLeft className="w-4 h-4" /> Chương Trước
                        </button>

                        <button
                          onClick={() => setReadingChapter(null)}
                          className="text-xs text-cyber-muted hover:text-cyber-accent font-bold transition-colors uppercase tracking-wider"
                        >
                          Danh sách chương
                        </button>

                        <button
                          onClick={() => nextChapter && handleReadChapter(selectedNovel.novel.id, nextChapter.chapter_no)}
                          disabled={!nextChapter}
                          className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-slate-900/60 hover:bg-slate-900 border border-cyber-border/40 text-xs font-bold text-slate-300 hover:text-cyber-accent disabled:opacity-30 disabled:hover:text-slate-300 transition-all"
                        >
                          Chương Sau <ChevronRight className="w-4 h-4" />
                        </button>
                      </div>
                    )}
                  </div>
                );
              })()
                : (
                  /* Chapter List View */
                  <div className="flex flex-col h-full overflow-hidden">
                    {/* Novel Header */}
                    <div className="border-b border-cyber-border px-5 py-4 flex flex-col gap-3 flex-shrink-0">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          {selectedNovel.novel.cover_url && (
                            <img src={selectedNovel.novel.cover_url} alt="cover" className="w-10 h-14 object-cover rounded border border-cyber-border" />
                          )}
                          <div>
                            <h2 className="text-md font-bold text-slate-100 truncate max-w-[200px]">{selectedNovel.novel.title}</h2>
                            <p className="text-[10px] text-cyber-muted mt-0.5">
                              {selectedNovel.chapters.filter(c => c.status === 'COMPLETED').length} / {selectedNovel.chapters.length} chương đã dịch
                            </p>
                          </div>
                        </div>
                        <div className="flex gap-2 flex-wrap justify-end">
                          {/* Check Quality Button */}
                          <button
                            onClick={() => handleCheckQuality(selectedNovel.novel.id)}
                            disabled={isCheckingQuality}
                            className="border border-yellow-500/40 hover:bg-yellow-500/10 text-yellow-400 font-bold px-3 py-2 rounded-xl text-xs flex items-center gap-1.5 transition-all shadow-lg disabled:opacity-40"
                            title="Kiểm tra nhanh các chương dịch lỗi"
                          >
                            {isCheckingQuality ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <span className="text-sm">🔍</span>}
                            Kiểm Tra Lỗi
                          </button>
                          {/* Download TXT */}
                          <button
                            onClick={() => handleDownloadNovel(selectedNovel.novel.id, 'txt')}
                            disabled={isDownloading || selectedNovel.chapters.filter(c => c.status === 'COMPLETED').length === 0}
                            className="border border-cyber-accent/40 hover:bg-cyber-accent/10 text-cyber-accent font-bold px-3 py-2 rounded-xl text-xs flex items-center gap-1.5 transition-all shadow-lg disabled:opacity-40"
                            title="Tải file TXT gộp tất cả chương"
                          >
                            {isDownloading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
                            TXT
                          </button>
                          {/* Download DOCX */}
                          <button
                            onClick={() => handleDownloadNovel(selectedNovel.novel.id, 'docx')}
                            disabled={isDownloading || selectedNovel.chapters.filter(c => c.status === 'COMPLETED').length === 0}
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
                        </div>
                      </div>
                    </div>

                    {/* Save Result */}
                    {saveResult && (
                      <div className={`mx-5 mt-3 flex items-start gap-2 p-3 rounded-lg text-xs animate-fade-in flex-shrink-0 ${saveResult.success
                          ? 'bg-cyber-success/10 border border-cyber-success/30 text-cyber-success'
                          : 'bg-cyber-danger/10 border border-cyber-danger/30 text-cyber-danger'
                        }`}>
                        {saveResult.success ? <CheckCircle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" /> : <XCircle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />}
                        <span className="break-all">{saveResult.message}</span>
                      </div>
                    )}

                    {/* Quality Check Results Panel */}
                    {qualityResult && (
                      <div className="mx-5 mt-3 rounded-xl border border-cyber-danger/30 bg-cyber-danger/5 overflow-hidden animate-fade-in flex-shrink-0">
                        <div className="px-4 py-2.5 flex items-center justify-between bg-cyber-danger/10 border-b border-cyber-danger/20">
                          <span className="text-xs font-bold text-cyber-danger flex items-center gap-2">
                            🔍 Kết quả kiểm tra chất lượng
                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                              qualityResult.bad_count === 0
                                ? 'bg-cyber-success/20 text-cyber-success'
                                : 'bg-cyber-danger/20 text-cyber-danger'
                            }`}>
                              {qualityResult.bad_count === 0
                                ? `✅ ${qualityResult.total_chapters} chương OK`
                                : `${qualityResult.bad_count} / ${qualityResult.total_chapters} chương lỗi`
                              }
                            </span>
                          </span>
                          <div className="flex items-center gap-1.5 flex-wrap justify-end">
                            {qualityResult.bad_count > 0 && (
                              <>
                                <button
                                  onClick={() => handleQuickFixAll(selectedNovel.novel.id, qualityResult.bad_chapters)}
                                  disabled={isFixingAll}
                                  className="text-[10px] font-bold px-2.5 py-1 rounded-lg bg-cyber-accent/15 border border-cyber-accent/30 text-cyber-accent hover:bg-cyber-accent/25 transition-all flex items-center gap-1 disabled:opacity-40"
                                >
                                  {isFixingAll ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Wand2 className="w-3 h-3" />}
                                  Sửa nhanh tất cả ({qualityResult.bad_count})
                                </button>
                                <button
                                  onClick={() => {
                                    const badNos = qualityResult.bad_chapters.map(bc => bc.chapter_no)
                                    if (window.confirm(`Dịch lại ${badNos.length} chương lỗi? Sẽ xóa cache và cào + dịch lại từ đầu.`)) {
                                      handleResetChapters(selectedNovel.novel.id, badNos)
                                    }
                                  }}
                                  className="text-[10px] font-bold px-2.5 py-1 rounded-lg bg-cyber-danger/15 border border-cyber-danger/30 text-cyber-danger hover:bg-cyber-danger/25 transition-all flex items-center gap-1"
                                >
                                  <RotateCcw className="w-3 h-3" />
                                  Dịch lại tất cả ({qualityResult.bad_count})
                                </button>
                              </>
                            )}
                            <button
                              onClick={() => setQualityResult(null)}
                              className="text-slate-500 hover:text-cyber-danger text-xs transition-colors p-1"
                            >✕</button>
                          </div>
                        </div>
                        {qualityResult.bad_count === 0 ? (
                          <div className="px-4 py-3 text-xs text-cyber-success flex items-center gap-2">
                            <CheckCircle className="w-3.5 h-3.5" />
                            Tất cả {qualityResult.total_chapters} chương đều ổn. Không phát hiện lỗi dịch!
                          </div>
                        ) : (
                          <div className="max-h-64 overflow-y-auto">
                            {qualityResult.bad_chapters.map(bc => {
                              const isRepaired = justFixed.has(bc.chapter_no)
                              return (
                                <div
                                  key={bc.chapter_no}
                                  className={`px-4 py-2.5 border-b border-cyber-danger/10 last:border-0 flex items-start justify-between gap-2 transition-all duration-300 ${
                                    isRepaired
                                      ? 'bg-cyber-success/10 border-l-4 border-l-cyber-success hover:bg-cyber-success/15'
                                      : 'hover:bg-cyber-danger/5'
                                  }`}
                                >
                                  <div className="flex-1 min-w-0">
                                    <p className={`text-[11px] font-bold truncate flex items-center gap-1 ${
                                      isRepaired ? 'text-cyber-success' : 'text-cyber-danger'
                                    }`}>
                                      {isRepaired ? '✓' : ''} Ch. {bc.chapter_no} — {bc.title} {isRepaired ? '[Đã sửa]' : ''}
                                    </p>
                                    {bc.issues.map((issue: string, i: number) => (
                                      <p key={i} className="text-[10px] text-slate-400 mt-0.5 break-all leading-relaxed">{issue}</p>
                                    ))}
                                  </div>
                                  <div className="flex flex-col gap-1 items-end">
                                    {!isRepaired ? (
                                      <>
                                        <button
                                          onClick={() => handleQuickFixChapter(selectedNovel.novel.id, bc.chapter_no)}
                                          disabled={isFixingChapters[bc.chapter_no]}
                                          className="flex-shrink-0 text-[10px] font-bold px-2 py-1 rounded-lg bg-cyber-accent/15 border border-cyber-accent/30 text-cyber-accent hover:bg-cyber-accent/25 transition-all whitespace-nowrap flex items-center gap-1 disabled:opacity-40"
                                          title="Dùng AI quét và dịch sửa lỗi nhanh cho đoạn dịch thô/convert"
                                        >
                                          {isFixingChapters[bc.chapter_no] ? (
                                            <RefreshCw className="w-3 h-3 animate-spin" />
                                          ) : (
                                            <Wand2 className="w-3.5 h-3.5" />
                                          )}
                                          Sửa nhanh
                                        </button>
                                        <button
                                          onClick={() => handleResetChapters(selectedNovel.novel.id, [bc.chapter_no])}
                                          className="flex-shrink-0 text-[10px] font-bold px-2 py-1 rounded-lg bg-cyber-danger/15 border border-cyber-danger/30 text-cyber-danger hover:bg-cyber-danger/25 transition-all whitespace-nowrap flex items-center gap-1"
                                          title="Xóa và dịch lại chương này"
                                        >
                                          <RotateCcw className="w-3 h-3" />
                                          Dịch lại
                                        </button>
                                        <button
                                          onClick={() => handleIgnoreQuality(selectedNovel.novel.id, bc.chapter_no)}
                                          className="flex-shrink-0 text-[9px] font-medium px-2 py-0.5 rounded bg-slate-900 border border-cyber-border text-slate-400 hover:text-slate-200 transition-all whitespace-nowrap"
                                          title="Bỏ qua cảnh báo lỗi chất lượng này nếu chương đã dịch ổn"
                                        >
                                          Bỏ qua lỗi
                                        </button>
                                      </>
                                    ) : (
                                      <span className="text-[10px] font-bold text-cyber-success flex items-center gap-1 px-2.5 py-1 rounded-lg bg-cyber-success/15 border border-cyber-success/30">
                                        ✓ Hoàn tất
                                      </span>
                                    )}
                                  </div>
                                </div>
                              )
                            })}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Chapter List */}
                    <div className="flex-grow lg:flex-1 lg:min-h-0 overflow-y-auto p-3 min-h-0">
                      <div className="flex flex-col gap-1">
                        {selectedNovel.chapters.map((ch) => {
                          const isCompleted = ch.status === 'COMPLETED'
                          const isFailed = ch.status === 'FAILED'
                          const hasBadQuality = qualityResult?.bad_chapters.some(bc => bc.chapter_no === ch.chapter_no) ?? false
                          return (
                            <div
                              key={ch.id}
                              className={`w-full flex items-center justify-between px-4 py-2 rounded-xl text-xs border transition-all duration-150 group ${hasBadQuality
                                  ? 'border-cyber-danger/40 bg-cyber-danger/5 hover:bg-cyber-danger/10'
                                  : 'border-cyber-border/10 hover:bg-slate-900/40 hover:border-cyber-border/30'
                                }`}
                            >
                              <button
                                onClick={() => isCompleted && handleReadChapter(selectedNovel.novel.id, ch.chapter_no)}
                                disabled={!isCompleted}
                                className={`flex-1 text-left flex items-center gap-3 min-w-0 ${isCompleted ? 'cursor-pointer' : 'cursor-default'
                                  }`}
                              >
                                <span className={`w-8 h-8 rounded-lg flex items-center justify-center text-[10px] font-bold flex-shrink-0 ${hasBadQuality
                                    ? 'bg-cyber-danger/15 text-cyber-danger border border-cyber-danger/30'
                                    : isCompleted
                                      ? 'bg-cyber-success/15 text-cyber-success border border-cyber-success/30'
                                      : isFailed
                                        ? 'bg-cyber-danger/15 text-cyber-danger border border-cyber-danger/30'
                                        : 'bg-slate-900/60 text-slate-500 border border-cyber-border/30'
                                  }`}>
                                  {ch.chapter_no}
                                </span>
                                <div className="min-w-0">
                                  <p className={`font-medium truncate ${hasBadQuality ? 'text-cyber-danger font-bold' : isCompleted ? 'text-slate-200' : 'text-slate-500'
                                    }`}>{ch.title}</p>
                                  <p className={`text-[10px] mt-0.5 ${hasBadQuality ? 'text-cyber-danger/80' : 'text-cyber-muted'}`}>
                                    {hasBadQuality ? '⚠️ Lỗi chất lượng' : isCompleted ? '✅ Đã dịch' : isFailed ? '❌ Lỗi' : '⏳ Chờ dịch'}
                                  </p>
                                </div>
                              </button>
                              <div className="flex items-center gap-1.5 ml-2 flex-shrink-0">
                                {/* Delete/Reset single chapter button */}
                                <button
                                  onClick={() => handleResetChapters(selectedNovel.novel.id, [ch.chapter_no])}
                                  title="Xóa bản dịch, cache và cào dịch lại chương này"
                                  className="p-1.5 hover:bg-cyber-danger/20 text-slate-500 hover:text-cyber-danger rounded-lg transition-all"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>

                                {isCompleted && (
                                  <ChevronRight className="w-4 h-4 text-slate-500 group-hover:text-cyber-accent transition-colors" />
                                )}
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  </div>
                )}

              {/* Loading overlay */}
              {isLoadingChapter && (
                <div className="absolute inset-0 bg-[#070A13]/80 flex items-center justify-center rounded-2xl z-20">
                  <div className="flex flex-col items-center gap-3">
                    <RefreshCw className="w-8 h-8 text-cyber-accent animate-spin" />
                    <span className="text-sm text-cyber-muted">Đang tải nội dung chương...</span>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right Column: Global Settings & Selected Novel details */}
        <div className="flex flex-col gap-4 lg:h-full lg:overflow-y-auto lg:min-h-0 pr-1 pb-4 flex-shrink-0 lg:flex-shrink">

          {/* Active Job Controls Card */}
          {selectedNovel && (
            <div className="glass-panel rounded-2xl p-6 flex flex-col gap-4 border-l-2 border-l-cyber-accent">
              <div className="flex items-center gap-3">
                {selectedNovel.novel.cover_url && (
                  <img src={selectedNovel.novel.cover_url} alt="cover" className="w-12 h-16 object-cover rounded border border-cyber-border" />
                )}
                <div>
                  <span className="text-[9px] px-1.5 py-0.5 rounded bg-cyber-accent/10 border border-cyber-accent/30 text-cyber-accent font-bold uppercase tracking-wider">Đã chọn</span>
                  <h3 className="font-bold text-sm text-slate-200 truncate max-w-[180px]">{selectedNovel.novel.title}</h3>
                  <p className="text-[10px] text-cyber-muted truncate">Chương: {selectedNovel.chapters.length}</p>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="grid grid-cols-2 gap-2 mt-2">

                {/* Chapter Range Inputs */}
                <div className="col-span-2 grid grid-cols-2 gap-2 bg-slate-950/40 p-3 rounded-xl border border-cyber-border">
                  <div className="flex flex-col gap-1">
                    <label className="text-[9px] text-cyber-muted uppercase tracking-wider font-bold">Từ chương</label>
                    <input
                      type="number"
                      value={startChapter ?? ''}
                      min={1}
                      placeholder="1"
                      onChange={(e) => setSettings({ startChapter: e.target.value ? parseInt(e.target.value) : null })}
                      className="glass-input rounded-lg px-2.5 py-1.5 text-xs"
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-[9px] text-cyber-muted uppercase tracking-wider font-bold">Đến chương</label>
                    <input
                      type="number"
                      value={endChapter ?? ''}
                      min={1}
                      max={selectedNovel.chapters.length}
                      placeholder={`${selectedNovel.chapters.length}`}
                      onChange={(e) => setSettings({ endChapter: e.target.value ? parseInt(e.target.value) : null })}
                      className="glass-input rounded-lg px-2.5 py-1.5 text-xs"
                    />
                  </div>
                  <p className="col-span-2 text-[9px] text-cyber-muted -mt-0.5">Tổng số chương: <strong className="text-slate-300">{selectedNovel.chapters.length}</strong>. Để trống = dịch tất cả.</p>
                </div>

                <button
                  onClick={() => handleStart(selectedNovel.novel.id)}
                  disabled={progress?.isRunning && progress.novelId === selectedNovel.novel.id}
                  className="bg-cyber-purple hover:bg-cyber-purple/90 text-white font-bold py-2.5 px-3 rounded-xl text-xs flex items-center justify-center gap-1.5 transition-all shadow-md shadow-cyber-purple/10 disabled:opacity-50"
                >
                  <Play className="w-3.5 h-3.5" /> Chạy Dịch
                </button>
                <button
                  onClick={pauseTranslation}
                  disabled={!progress?.isRunning || progress.novelId !== selectedNovel.novel.id}
                  className="bg-slate-900 hover:bg-slate-800 text-slate-300 font-bold py-2.5 px-3 rounded-xl text-xs flex items-center justify-center gap-1.5 border border-cyber-border transition-all disabled:opacity-50"
                >
                  <Pause className="w-3.5 h-3.5 text-yellow-500" /> Tạm Dừng
                </button>
                <button
                  onClick={clearJob}
                  className="bg-slate-950 hover:bg-slate-900 text-cyber-danger font-bold py-2.5 px-3 rounded-xl text-xs flex items-center justify-center gap-1.5 border border-cyber-border/40 transition-all col-span-2"
                >
                  <RotateCcw className="w-3.5 h-3.5" /> Xóa Trạng Thái Task
                </button>
                <button
                  onClick={() => manualExport(selectedNovel.novel.id)}
                  className="bg-gradient-to-r from-cyber-accent to-cyber-purple hover:opacity-90 text-cyber-bg font-bold py-2.5 px-3 rounded-xl text-xs flex items-center justify-center gap-1.5 transition-all col-span-2 mt-1 shadow-lg"
                >
                  <Download className="w-3.5 h-3.5" /> Đóng Gói Thủ Công
                </button>
              </div>
            </div>
          )}

          {/* Từ Điển Riêng Của Truyện (Novel-specific Glossary Sidebar Card) */}
          {selectedNovel && (
            <div className="glass-panel rounded-2xl p-4 lg:p-6 flex flex-col gap-4 border border-cyber-accent/20">
              <h2 className="text-sm font-bold text-slate-100 flex items-center gap-2 border-b border-cyber-border pb-3">
                <Globe className="w-4 h-4 text-cyber-accent animate-pulse" /> Từ Điển Riêng Của Truyện
              </h2>

              {/* Add form */}
              <form onSubmit={handleQuickAddGlossary} className="flex flex-col gap-2 bg-slate-950/40 p-3 rounded-xl border border-cyber-border/40">
                <div className="grid grid-cols-2 gap-2">
                  <div className="flex flex-col gap-1">
                    <label className="text-[9px] text-cyber-muted font-semibold uppercase">Tiếng Trung</label>
                    <input
                      type="text"
                      placeholder="Ví dụ: 陆大有"
                      value={quickZh}
                      onChange={(e) => setQuickZh(e.target.value)}
                      className="glass-input rounded-lg px-2 py-1.5 text-xs bg-[#070A13]"
                      required
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-[9px] text-cyber-muted font-semibold uppercase">Dịch Nghĩa Việt</label>
                    <input
                      type="text"
                      placeholder="Ví dụ: Lục Đại Hữu"
                      value={quickVi}
                      onChange={(e) => setQuickVi(e.target.value)}
                      className="glass-input rounded-lg px-2 py-1.5 text-xs bg-[#070A13]"
                      required
                    />
                  </div>
                </div>
                <button
                  type="submit"
                  disabled={isAddingQuickGlossary}
                  className="w-full bg-cyber-accent/10 hover:bg-cyber-accent/25 border border-cyber-accent/30 text-cyber-accent font-bold py-1.5 rounded-lg text-[10px] uppercase flex items-center justify-center gap-1 transition-all disabled:opacity-50"
                >
                  <Plus className="w-3.5 h-3.5" />
                  {isAddingQuickGlossary ? 'Đang thêm...' : 'Thêm Thuật Ngữ'}
                </button>
              </form>

              {/* Scrollable list */}
              <div className="max-h-52 overflow-y-auto flex flex-col gap-1.5 border border-cyber-border/30 p-2 rounded-xl bg-slate-950/20">
                {novelGlossary.length === 0 ? (
                  <span className="text-[10px] text-slate-500 italic text-center py-4">Từ điển truyện trống. Thêm tên riêng (Hán Việt/Pinyin) để dịch chuẩn hơn!</span>
                ) : (
                  novelGlossary.map((g) => (
                    <div key={g.id} className="flex items-center justify-between text-xs py-1.5 px-2.5 hover:bg-slate-900/60 rounded-lg border border-cyber-border/10 transition-all font-mono">
                      <div className="flex items-center gap-1.5 min-w-0">
                        <span className="text-cyber-accent font-medium truncate" title={g.chinese_term}>{g.chinese_term}</span>
                        <span className="text-slate-500 flex-shrink-0">→</span>
                        <span className="text-slate-200 truncate" title={g.vietnamese_term}>{g.vietnamese_term}</span>
                      </div>
                      <button
                        onClick={() => handleQuickDeleteGlossary(g.id)}
                        className="text-slate-500 hover:text-cyber-danger p-1 hover:bg-cyber-danger/10 rounded-md transition-colors"
                        title="Xóa"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

          {/* Model & AI Settings Card */}
          <div className="glass-panel rounded-2xl p-6 flex flex-col gap-4">
            <h2 className="text-md font-bold text-slate-100 flex items-center gap-2 border-b border-cyber-border pb-3">
              <Settings className="w-4 h-4 text-cyber-accent" /> Cấu Hình Translation AI
            </h2>

            {/* Provider */}
            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] text-cyber-muted uppercase tracking-wider font-bold">Nhà Cung Cấp AI</label>
              <select
                value={provider}
                onChange={(e) => {
                  const p = e.target.value
                  const models = getModelsForProvider(p)
                  setSettings({ provider: p, model: models[0] })
                }}
                className="glass-input rounded-xl px-3 py-2 text-xs bg-[#070A13]"
              >
                <option value="gemini">Google Gemini</option>
                <option value="openrouter">OpenRouter (DeepSeek...)</option>
                <option value="openai">OpenAI (ChatGPT)</option>
                <option value="claude">Anthropic Claude</option>
              </select>
            </div>

            {/* Model */}
            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] text-cyber-muted uppercase tracking-wider font-bold">Mô Hình (Model)</label>
              <select
                value={model}
                onChange={(e) => setSettings({ model: e.target.value })}
                className="glass-input rounded-xl px-3 py-2 text-xs bg-[#070A13]"
              >
                {getModelsForProvider(provider).map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
                {!getModelsForProvider(provider).includes(model) && (
                  <option value={model}>{model} (Tự chọn)</option>
                )}
              </select>
              <input
                type="text"
                value={model}
                onChange={(e) => setSettings({ model: e.target.value })}
                placeholder="Hoặc tự nhập tên Model khác..."
                className="glass-input rounded-xl px-3 py-2 text-xs mt-1"
              />
            </div>

            {/* Delay */}
            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] text-cyber-muted uppercase tracking-wider font-bold">Độ trễ mỗi chương (giây)</label>
              <input
                type="number"
                value={delay}
                min={0.1}
                max={60}
                step={0.5}
                onChange={(e) => setSettings({ delay: parseFloat(e.target.value) || 3 })}
                className="glass-input rounded-xl px-3 py-2 text-xs"
              />
            </div>

            {/* Concurrency */}
            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] text-cyber-muted uppercase tracking-wider font-bold">Số luồng dịch song song (concurrency)</label>
              <input
                type="number"
                value={concurrency}
                min={1}
                max={15}
                step={1}
                onChange={(e) => setSettings({ concurrency: parseInt(e.target.value) || 3 })}
                className="glass-input rounded-xl px-3 py-2 text-xs"
              />
            </div>

            {/* API Key */}
            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] text-cyber-muted uppercase tracking-wider font-bold flex items-center justify-between">
                <span>API Keys</span>
                <span className="flex items-center gap-1.5">
                  {isSavedToEnv && (
                    <span className="flex items-center gap-1 text-[8px] text-cyber-success font-semibold animate-fade-in">
                      <CheckCircle className="w-2.5 h-2.5" />
                      Đã lưu vào .env
                    </span>
                  )}
                  <span className="text-[8px] text-cyber-muted normal-case font-normal">(Phân tách bởi dấu chấm phẩy ;)</span>
                </span>
              </label>
              <div className="flex gap-2">
                <input
                  type="password"
                  value={apiKeys}
                  onChange={(e) => {
                    setSettings({ apiKeys: e.target.value })
                    setKeyTestResult(null)
                    setIsSavedToEnv(false)
                    // Hiển thị "Đã lưu" sau khi debounce save xong (~900ms)
                    clearTimeout((window as any)._savedBadgeTimer)
                      ; (window as any)._savedBadgeTimer = setTimeout(() => setIsSavedToEnv(true), 900)
                  }}
                  placeholder="Nhập API Key 1; API Key 2;..."
                  className="flex-1 glass-input rounded-xl px-3 py-2 text-xs"
                />
                <button
                  onClick={handleTestKey}
                  disabled={isTestingKey || !apiKeys.trim()}
                  className="bg-slate-900 hover:bg-slate-800 text-cyber-accent font-bold px-3 py-2 rounded-xl text-[10px] flex items-center gap-1.5 border border-cyber-accent/30 transition-all whitespace-nowrap disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {isTestingKey ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Key className="w-3 h-3" />}
                  Test Key
                </button>
              </div>
              {/* Test Result Display */}
              {keyTestResult && (
                <div className={`flex items-start gap-2 p-2.5 rounded-lg text-xs animate-fade-in ${keyTestResult.success
                    ? 'bg-cyber-success/10 border border-cyber-success/30 text-cyber-success'
                    : 'bg-cyber-danger/10 border border-cyber-danger/30 text-cyber-danger'
                  }`}>
                  {keyTestResult.success
                    ? <CheckCircle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
                    : <XCircle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />}
                  <span className="break-all">{keyTestResult.message}</span>
                </div>
              )}
            </div>

            {/* Custom translation prompt */}
            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] text-cyber-muted uppercase tracking-wider font-bold">Prompt Biên Tập Bổ Sung</label>
              <textarea
                value={customPrompt}
                onChange={(e) => setSettings({ customPrompt: e.target.value })}
                placeholder="Yêu cầu thêm: dịch mượt hơn, ưu tiên ngôi thứ ba xưng hô tỷ-muội..."
                rows={4}
                className="glass-input rounded-xl p-3 text-xs resize-none"
              />
            </div>
          </div>

        </div>
      </main>

      {/* Footer details */}
      <footer className="glass-panel border-t border-cyber-border px-6 py-4 text-center text-xs text-cyber-muted">
        <span>AiRead v2 Rebuild © 2026. Thiết kế giao diện Cyberpunk Glassmorphism cao cấp.</span>
      </footer>
    </div>
  )
}
