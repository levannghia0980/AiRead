import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useNovelStore } from './store/useNovelStore'
import Navbar from './components/Navbar'
import LibraryTab from './components/LibraryTab'
import GlossaryTab from './components/GlossaryTab'
import AudioStudio from './components/AudioStudio'
import CrawlerPanel from './components/translation/CrawlerPanel'
import ActiveJobControls from './components/translation/ActiveJobControls'
import ModelSettingsPanel from './components/translation/ModelSettingsPanel'
import NovelGlossarySidebar from './components/translation/NovelGlossarySidebar'
import TerminalLogs from './components/translation/TerminalLogs'

// Custom Hooks
import useSSE from './hooks/useSSE'
import useNovelCrawler from './hooks/useNovelCrawler'

export default function App() {
  // Global Store State
  const {
    novels,
    selectedNovel,
    glossary,
    corrections,
    logs,
    progress,
    provider,
    model,
    apiKeys,
    customPrompt,
    delay,
    batchSize,
    startChapter,
    endChapter,
    translationStyle,
    enableUnblock,
    enableLlmExtract,
    enableNamesDict,
    enableGgCorrections,
    forceRetranslate,
    setSettings,
    testApiKey,
    fetchNovels,
    fetchNovelDetails,
    deleteNovel,
    fetchGlossary,
    addGlossaryTerm,
    updateGlossaryTerm,
    applyGlossaryToAllChapters,
    deleteGlossaryTerm,
    fetchCorrections,
    addCorrection,
    updateCorrection,
    deleteCorrection,
    startTranslation,
    pauseTranslation,
    clearJob,
    resetChapters,
    restartNovel,
    fetchChapterText,
    updateChapterText,
    downloadNovel,
    setLogs,
    loadSettingsFromEnv,
    saveSettingsToEnv
  } = useNovelStore()

  // 1. Connect Realtime SSE Stream Hook
  useSSE()



  // 3. Custom Crawler Hook
  const {
    inputUrl,
    setInputUrl,
    isAnalyzing,
    analyzedData,
    isSaving,
    handleAnalyzeUrl,
    handleSaveNovel
  } = useNovelCrawler()

  // Local UI Tab & Search State
  const [activeTab, setActiveTab] = useState<'translate' | 'glossary' | 'library' | 'audio'>('translate')
  const [showChaptersList, setShowChaptersList] = useState(false)
  const [chapterSearch, setChapterSearch] = useState('')

  // API Key Test State
  const [isTestingKey, setIsTestingKey] = useState(false)
  const [keyTestResult, setKeyTestResult] = useState<{ success: boolean; message: string } | null>(null)
  const [isSavedToEnv, setIsSavedToEnv] = useState(false)

  // Download & Reset State
  const [isDownloading, setIsDownloading] = useState(false)
  const [isResetting, setIsResetting] = useState(false)

  // Reader State
  const [readingChapter, setReadingChapter] = useState<any>(null)
  const [saveResult] = useState<any>(null)
  const [isEditing, setIsEditing] = useState(false)
  const [isSavingEdit, setIsSavingEdit] = useState(false)
  const editorRef = useRef<HTMLDivElement>(null)

  // Novel Glossary State
  const [novelGlossary, setNovelGlossary] = useState<any[]>([])
  const [quickZh, setQuickZh] = useState('')
  const [quickVi, setQuickVi] = useState('')
  const [quickGender, setQuickGender] = useState('')
  const [quickRole, setQuickRole] = useState('')
  const [isAddingQuickGlossary, setIsAddingQuickGlossary] = useState(false)

  useEffect(() => {
    fetchNovels()
    loadSettingsFromEnv()
  }, [])

  // Fetch novel glossary on novel change
  useEffect(() => {
    if (selectedNovel?.novel.id) {
      fetchNovelGlossary(selectedNovel.novel.id)
    }
  }, [selectedNovel?.novel.id])

  const fetchNovelGlossary = useCallback(async (novelId: number) => {
    try {
      const res = await fetch(`/api/novels/${novelId}/glossary`)
      if (res.ok) {
        const data = await res.json()
        setNovelGlossary(data)
      }
    } catch (e) {
      console.error("Failed to fetch novel glossary", e)
    }
  }, [])

  const handleAddQuickGlossary = useCallback(async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedNovel || !quickZh.trim() || !quickVi.trim()) return
    setIsAddingQuickGlossary(true)
    try {
      await addGlossaryTerm(selectedNovel.novel.id, quickZh.trim(), quickVi.trim(), 'NAME', null, quickGender, quickRole)
      await fetchNovelGlossary(selectedNovel.novel.id)
      setQuickZh('')
      setQuickVi('')
      setQuickGender('')
      setQuickRole('')
    } finally {
      setIsAddingQuickGlossary(false)
    }
  }, [selectedNovel, quickZh, quickVi, quickGender, quickRole, addGlossaryTerm, fetchNovelGlossary])

  const handleDeleteGlossaryTerm = useCallback(async (termId: number) => {
    if (!selectedNovel) return
    await deleteGlossaryTerm(selectedNovel.novel.id, termId)
    await fetchNovelGlossary(selectedNovel.novel.id)
  }, [selectedNovel, deleteGlossaryTerm, fetchNovelGlossary])

  const handleTestKey = useCallback(async () => {
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
  }, [testApiKey])

  // ─── Browser History & Query Param Routing System ───
  const changeTab = useCallback((newTab: 'translate' | 'glossary' | 'library' | 'audio', replaceState = false) => {
    setActiveTab(newTab)
    setReadingChapter(null)
    const newSearch = `?tab=${newTab}`
    if (window.location.search !== newSearch) {
      if (replaceState) {
        window.history.replaceState({ tab: newTab }, '', newSearch)
      } else {
        window.history.pushState({ tab: newTab }, '', newSearch)
      }
    }
  }, [])

  // Listen to browser Back/Forward (popstate) buttons for full history stack
  useEffect(() => {
    const handlePopState = () => {
      const params = new URLSearchParams(window.location.search)
      const tabParam = params.get('tab') || 'translate'
      const chapterParam = params.get('chapter')
      const novelParam = params.get('novel')

      if (['translate', 'glossary', 'library', 'audio'].includes(tabParam)) {
        setActiveTab(tabParam as any)
      } else {
        setActiveTab('translate')
      }

      if (tabParam === 'library' && chapterParam && novelParam) {
        const nId = Number(novelParam)
        const cNo = Number(chapterParam)
        if (nId && cNo) {
          fetchNovelDetails(nId).then(() => {
            fetchChapterText(nId, cNo).then(data => {
              if (data) setReadingChapter(data)
            })
          })
        }
      } else {
        setReadingChapter(null)
      }
    }

    if (!window.location.search) {
      window.history.replaceState({ tab: 'translate' }, '', '?tab=translate')
    } else {
      const params = new URLSearchParams(window.location.search)
      const tabParam = params.get('tab')
      const chapterParam = params.get('chapter')
      const novelParam = params.get('novel')

      if (tabParam && ['translate', 'glossary', 'library', 'audio'].includes(tabParam)) {
        setActiveTab(tabParam as any)
        if (tabParam === 'library' && chapterParam && novelParam) {
          const nId = Number(novelParam)
          const cNo = Number(chapterParam)
          fetchNovelDetails(nId).then(() => {
            fetchChapterText(nId, cNo).then(data => {
              if (data) setReadingChapter(data)
            })
          })
        }
      }
    }

    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [fetchChapterText, fetchNovelDetails])

  const handleReadChapter = useCallback(async (novelId: number, chapterNo: number) => {
    setIsEditing(false)
    try {
      if (!selectedNovel || selectedNovel.novel.id !== novelId) {
        await fetchNovelDetails(novelId)
      }
      const data = await fetchChapterText(novelId, chapterNo)
      if (data) {
        setReadingChapter(data)
        setActiveTab('library')
        window.history.pushState(
          { tab: 'library', novelId, chapterNo },
          '',
          `?tab=library&novel=${novelId}&chapter=${chapterNo}`
        )
      }
    } catch (e) {
      console.error(e)
    }
  }, [fetchChapterText, fetchNovelDetails, selectedNovel])

  const handleSaveEdit = useCallback(async () => {
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
        setReadingChapter((prev: any) => prev ? { ...prev, translated_text: newHtml } : null)
        setIsEditing(false)
      } else {
        alert("Không thể lưu bản dịch chỉnh sửa. Có lỗi xảy ra.")
      }
    } catch (e: any) {
      alert("Lỗi kết nối: " + e.message)
    } finally {
      setIsSavingEdit(false)
    }
  }, [selectedNovel, readingChapter, updateChapterText])

  const handleResetChapters = useCallback(async (novelId: number, chapterNos?: number[]) => {
    const confirmMsg = chapterNos
      ? `Bạn có chắc muốn XÓA BẢN DỊCH, XÓA CACHE và CÀO LẠI từ đầu chương ${chapterNos.join(', ')} không?`
      : "Bạn có chắc muốn XÓA BẢN DỊCH VÀ CACHE của TOÀN BỘ CÁC CHƯƠNG để cào/dịch lại từ đầu không?"
    if (!window.confirm(confirmMsg)) return

    setIsResetting(true)
    try {
      await resetChapters(novelId, chapterNos)
      await fetchNovelDetails(novelId)
    } catch (e: any) {
      alert(`Lỗi khi reset chương: ${e.message}`)
    } finally {
      setIsResetting(false)
    }
  }, [resetChapters, fetchNovelDetails])

  const [isRestarting, setIsRestarting] = useState(false)
  const handleRestartNovel = useCallback(async (novelId: number) => {
    setIsRestarting(true)
    try {
      const result = await restartNovel(novelId)
      if (result.success) {
        alert(result.message)
      } else {
        alert(`Lỗi: ${result.message}`)
      }
    } catch (e: any) {
      alert(`Lỗi restart: ${e.message}`)
    } finally {
      setIsRestarting(false)
    }
  }, [restartNovel])

  const [isFixingAll, setIsFixingAll] = useState(false)
  const handleQuickFixAll = useCallback(async (novelId: number) => {
    if (!apiKeys || !apiKeys.trim()) {
      alert("Bạn cần cấu hình API Key ở cột cấu hình bên phải trước khi dùng tính năng Sửa nhanh!")
      return
    }
    if (!window.confirm("Bạn có chắc muốn dùng AI SỬA NHANH TẤT CẢ các câu dính chữ vàng trong 1 lượt duy nhất không? (Tất cả các câu chữ vàng sẽ được gom gửi AI 1 lượt duy nhất và lắp lại đúng vị trí mà không dịch lại toàn bộ chương).")) return

    setIsFixingAll(true)
    try {
      const response = await fetch(`/api/novels/${novelId}/quick-fix-all`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, model, api_key: apiKeys, prompt: customPrompt })
      })
      const result = await response.json()
      if (response.ok && result.success) {
        alert(`✅ ${result.message}`)
        await fetchNovelDetails(novelId)
      } else {
        alert(`Sửa nhanh thất bại: ${result.detail || result.message || 'Lỗi không xác định'}`)
      }
    } catch (e: any) {
      alert(`Lỗi kết nối khi sửa nhanh: ${e.message}`)
    } finally {
      setIsFixingAll(false)
    }
  }, [apiKeys, provider, model, customPrompt, fetchNovelDetails])

  const [isFixingRed, setIsFixingRed] = useState(false)
  const handleBatchFixRed = useCallback(async (novelId: number) => {
    if (!window.confirm("Bạn có chắc muốn gom tất cả lỗi Hán tự dịch sai để gửi AI xử lý 1 lượt duy nhất không?")) return

    setIsFixingRed(true)
    try {
      const response = await fetch(`/api/translation/novel/${novelId}/batch-fix-swept-errors`, {
        method: 'POST',
      })
      const result = await response.json()
      if (response.ok && result.status === 'success') {
        alert(`✅ ${result.message}`)
        await fetchNovelDetails(novelId)
      } else {
        alert(`Sửa lỗi Hán tự thất bại: ${result.detail || result.message || 'Lỗi không xác định'}`)
      }
    } catch (e: any) {
      alert(`Lỗi hệ thống: ${e.message}`)
    } finally {
      setIsFixingRed(false)
    }
  }, [fetchNovelDetails])

  const handleDownloadNovel = useCallback(async (novelId: number, fmt: 'txt' | 'docx') => {
    setIsDownloading(true)
    try {
      await downloadNovel(novelId, fmt)
    } catch (e: any) {
      alert(`Lỗi tải file: ${e.message}`)
    } finally {
      setIsDownloading(false)
    }
  }, [downloadNovel])

  return (
    <div className="min-h-[100dvh] md:h-screen flex flex-col overflow-y-auto md:overflow-hidden bg-[#070A13] text-slate-200 font-sans selection:bg-cyber-accent selection:text-white">
      {/* Top Navbar */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={changeTab}
        selectedNovelTitle={selectedNovel?.novel.title}
        isRunning={progress?.isRunning}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-3 sm:px-4 md:px-6 pb-24 md:pb-6 pt-20 overflow-visible md:overflow-hidden min-h-0 flex flex-col">
        {/* AudioStudio tab removed as requested */}

        {activeTab === 'library' && (
          <LibraryTab
            novels={novels}
            selectedNovel={selectedNovel}
            fetchNovelDetails={fetchNovelDetails}
            deleteNovel={deleteNovel}
            readingChapter={readingChapter}
            setReadingChapter={setReadingChapter}
            isEditing={isEditing}
            setIsEditing={setIsEditing}
            isSavingEdit={isSavingEdit}
            handleSaveEdit={handleSaveEdit}
            editorRef={editorRef}
            handleDownloadNovel={handleDownloadNovel}
            isDownloading={isDownloading}
            handleResetChapters={handleResetChapters}
            isResetting={isResetting}
            chapterSearch={chapterSearch}
            setChapterSearch={setChapterSearch}
            showChaptersList={showChaptersList}
            setShowChaptersList={setShowChaptersList}
            saveResult={saveResult}
            handleQuickFixAll={handleQuickFixAll}
            isFixingAll={isFixingAll}
            handleBatchFixRed={handleBatchFixRed}
            isFixingRed={isFixingRed}
            handleReadChapter={handleReadChapter}
            handleRestartNovel={handleRestartNovel}
            isRestarting={isRestarting}
          />
        )}

        {activeTab === 'glossary' && (
          <GlossaryTab
            glossary={glossary}
            corrections={corrections}
            novels={novels}
            fetchGlossary={fetchGlossary}
            addGlossaryTerm={addGlossaryTerm}
            updateGlossaryTerm={updateGlossaryTerm}
            applyGlossaryToAllChapters={applyGlossaryToAllChapters}
            deleteGlossaryTerm={deleteGlossaryTerm}
            fetchCorrections={fetchCorrections}
            addCorrection={addCorrection}
            updateCorrection={updateCorrection}
            deleteCorrection={deleteCorrection}
          />
        )}

        {activeTab === 'translate' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 md:h-full">
            {/* Left Column (2 Cols wide): Terminal Logs */}
            <div className="lg:col-span-2 flex flex-col md:h-full min-h-[350px] md:min-h-0">
              <TerminalLogs logs={logs} setLogs={setLogs} />
            </div>

            {/* Right Column (1 Col wide): Crawler, Active Controls, Settings, Glossary Sidebar */}
            <div className="flex flex-col gap-4 overflow-y-auto pr-1">
              <CrawlerPanel
                inputUrl={inputUrl}
                setInputUrl={setInputUrl}
                isAnalyzing={isAnalyzing}
                handleAnalyzeUrl={handleAnalyzeUrl}
                analyzedData={analyzedData}
                handleSaveNovel={handleSaveNovel}
                isSaving={isSaving}
                novels={novels}
                selectedNovelId={selectedNovel?.novel.id}
                fetchNovelDetails={fetchNovelDetails}
              />

              <ActiveJobControls
                selectedNovel={selectedNovel}
                progress={progress}
                startTranslation={startTranslation}
                pauseTranslation={pauseTranslation}
                clearJob={clearJob}
              />

              <ModelSettingsPanel
                provider={provider}
                model={model}
                apiKeys={apiKeys}
                customPrompt={customPrompt}
                delay={delay}
                batchSize={batchSize}
                startChapter={startChapter}
                endChapter={endChapter}
                translationStyle={translationStyle}
                enableUnblock={enableUnblock}
                enableLlmExtract={enableLlmExtract}
                enableNamesDict={enableNamesDict}
                enableGgCorrections={enableGgCorrections}
                forceRetranslate={forceRetranslate}
                setSettings={setSettings}
                handleTestKey={handleTestKey}
                isTestingKey={isTestingKey}
                keyTestResult={keyTestResult}
                saveSettingsToEnv={saveSettingsToEnv}
                isSavedToEnv={isSavedToEnv}
                setIsSavedToEnv={setIsSavedToEnv}
              />

              <NovelGlossarySidebar
                selectedNovel={selectedNovel}
                novelGlossary={novelGlossary}
                quickZh={quickZh}
                setQuickZh={setQuickZh}
                quickVi={quickVi}
                setQuickVi={setQuickVi}
                quickGender={quickGender}
                setQuickGender={setQuickGender}
                quickRole={quickRole}
                setQuickRole={setQuickRole}
                isAddingQuickGlossary={isAddingQuickGlossary}
                handleAddQuickGlossary={handleAddQuickGlossary}
                handleDeleteGlossaryTerm={handleDeleteGlossaryTerm}
              />
            </div>
          </div>
        )}

        {activeTab === 'audio' && (
          <AudioStudio
            novels={novels.map(n => ({
              id: n.id,
              title: n.title_rough || n.title_raw || n.title || "Chưa có tên",
              author: n.author,
              cover_url: n.cover_url,
              total_chapters: n.total_chapters || 0,
              completed_chapters: n.completed_chapters || 0
            }))}
          />
        )}
      </main>
    </div>
  )
}
