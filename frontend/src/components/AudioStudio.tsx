import React, { useState, useEffect, useRef } from 'react'
import {
  Headphones,
  Play,
  Pause,
  RotateCcw,
  RotateCw,
  Volume2,
  VolumeX,
  Download,
  Trash2,
  RefreshCw,
  CheckCircle,
  Clock,
  Sparkles,
  Layers,
  Music,
  Zap,
  ArrowLeft,
  BookOpen,
  FileText,
  Type
} from 'lucide-react'

interface NovelOption {
  id: number
  title: string
  author?: string
  cover_url?: string
  total_chapters?: number
  completed_chapters?: number
}

interface VolumeInfo {
  volume_no: number
  start_chapter: number
  end_chapter: number
  chapter_count: number
  cached_chapters_count?: number
  word_count: number
  estimated_hours: number
  is_created: boolean
  filename?: string
  size_mb?: number
  file_size?: string
  download_url?: string
  is_custom?: boolean
}

interface AudioStudioProps {
  novels: NovelOption[]
}

export default function AudioStudio({ novels }: AudioStudioProps) {
  const [activeView, setActiveView] = useState<'list' | 'detail'>('list')
  const [selectedNovelId, setSelectedNovelId] = useState<number>(0)
  const [selectedNovel, setSelectedNovel] = useState<NovelOption | null>(null)
  
  const [volumeData, setVolumeData] = useState<{
    novel_title: string
    total_volumes: number
    created_volumes_count: number
    volumes: VolumeInfo[]
  } | null>(null)

  const [loading, setLoading] = useState(false)
  const [filter, setFilter] = useState<'ALL' | 'CREATED' | 'UNCREATED'>('ALL')
  const [jobStatus, setJobStatus] = useState<any>(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const [voiceProfile, setVoiceProfile] = useState<string>('default')
  const [chaptersPerVolume, setChaptersPerVolume] = useState<number>(10)
  
  // Quick generate loading states
  const [quickGeneratingNovelId, setQuickGeneratingNovelId] = useState<number | null>(null)

  // Custom range states
  const [customStartChapter, setCustomStartChapter] = useState<number | null>(null)
  const [customEndChapter, setCustomEndChapter] = useState<number | null>(null)

  // Audio Player State
  const [currentPlaying, setCurrentPlaying] = useState<VolumeInfo | null>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [volume, setVolume] = useState(1.0)
  const [isMuted, setIsMuted] = useState(false)
  const [playbackRate, setPlaybackRate] = useState(1.5)

  // Reader State
  const [readingChapterNo, setReadingChapterNo] = useState<number | null>(null)
  const [readingChapterText, setReadingChapterText] = useState<{
    chapter_no: number
    title: string
    translated_text: string
  } | null>(null)
  const [readerLoading, setReaderLoading] = useState(false)
  const [readerFontSize, setReaderFontSize] = useState<number>(14) // px

  const audioRef = useRef<HTMLAudioElement | null>(null)

  // Sync selected novel object
  useEffect(() => {
    if (selectedNovelId) {
      const found = novels.find(n => n.id === selectedNovelId)
      if (found) setSelectedNovel(found)
    } else {
      setSelectedNovel(null)
    }
  }, [selectedNovelId, novels])

  // Fetch volume list
  const fetchVolumes = async (novelId: number) => {
    if (!novelId) return
    setLoading(true)
    try {
      const res = await fetch(`/api/novels/${novelId}/audio/volumes?chapters_per_volume=${chaptersPerVolume}`)
      if (res.ok) {
        const data = await res.json()
        setVolumeData(data)
      }
    } catch (e) {
      console.error("Failed to fetch audio volumes", e)
    } finally {
      setLoading(false)
    }
  }

  // Effect to load details when viewing novel
  useEffect(() => {
    if (selectedNovelId && activeView === 'detail') {
      fetchVolumes(selectedNovelId)
      checkJobStatus(selectedNovelId)
      setReadingChapterNo(null)
      setReadingChapterText(null)
    }
  }, [selectedNovelId, activeView, chaptersPerVolume])

  // Fetch and show chapter text
  const fetchChapterText = async (novelId: number, chapterNo: number) => {
    setReaderLoading(true)
    try {
      const res = await fetch(`/api/novels/${novelId}/chapters/${chapterNo}/text`)
      if (res.ok) {
        const data = await res.json()
        setReadingChapterText(data)
      }
    } catch (e) {
      console.error("Failed to fetch chapter text", e)
    } finally {
      setReaderLoading(false)
    }
  }

  useEffect(() => {
    if (selectedNovelId && readingChapterNo) {
      fetchChapterText(selectedNovelId, readingChapterNo)
    } else {
      setReadingChapterText(null)
    }
  }, [readingChapterNo, selectedNovelId])

  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stopPolling = React.useCallback(() => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current)
      pollIntervalRef.current = null
    }
  }, [])

  const pollJob = React.useCallback((novelId: number) => {
    stopPolling()

    pollIntervalRef.current = setInterval(async () => {
      try {
        const res = await fetch(`/api/novels/${novelId}/audio/status`)
        if (res.ok) {
          const status = await res.json()
          setJobStatus(status)
          if (!status.is_running) {
            setIsGenerating(false)
            stopPolling()
            fetchVolumes(novelId) // Chỉ fetch lại volumes 1 lần duy nhất khi hoàn thành
          }
        }
      } catch (e) {
        setIsGenerating(false)
        stopPolling()
      }
    }, 3000)
  }, [stopPolling])

  // Poll Job Status
  const checkJobStatus = async (novelId: number) => {
    try {
      const res = await fetch(`/api/novels/${novelId}/audio/status`)
      if (res.ok) {
        const status = await res.json()
        setJobStatus(status)
        if (status.is_running) {
          setIsGenerating(true)
          pollJob(novelId)
        } else {
          stopPolling()
        }
      }
    } catch (e) {
      console.error(e)
    }
  }

  // Clear polling interval on unmount or novel change
  useEffect(() => {
    return () => {
      stopPolling()
    }
  }, [selectedNovelId, stopPolling])

  // Cancel Running Job
  const handleCancelJob = async () => {
    if (!selectedNovelId) return
    try {
      const res = await fetch(`/api/novels/${selectedNovelId}/audio/cancel`, { method: 'POST' })
      const data = await res.json()
      alert(data.message)
    } catch (e) {
      console.error(e)
    }
  }

  // Generate Custom Range Audiobook
  const handleGenerateCustomRange = async () => {
    if (!selectedNovelId || !customStartChapter || !customEndChapter) return
    if (customStartChapter > customEndChapter) {
      alert("Chương bắt đầu không được lớn hơn chương kết thúc.")
      return
    }
    
    setIsGenerating(true)
    try {
      const res = await fetch(
        `/api/novels/${selectedNovelId}/audio/generate_range?start_chapter=${customStartChapter}&end_chapter=${customEndChapter}&voice_profile=${voiceProfile}`,
        { method: 'POST' }
      )
      const data = await res.json()
      if (res.ok) {
        alert(data.message || "Đã bắt đầu tạo audio cho khoảng chương tùy chỉnh.")
        fetchVolumes(selectedNovelId)
        pollJob(selectedNovelId)
      } else {
        alert(data.detail || "Không thể tạo audio.")
        setIsGenerating(false)
      }
    } catch (e) {
      console.error(e)
      alert("Lỗi kết nối khi tạo audio.")
      setIsGenerating(false)
    }
  }

  // Trigger Targeted Volume Generation
  const handleGenerateSingleVolume = async (volNo: number) => {
    if (!selectedNovelId) return
    setIsGenerating(true)
    try {
      const res = await fetch(`/api/novels/${selectedNovelId}/audio/generate_volume/${volNo}?voice_profile=${voiceProfile}&chapters_per_volume=${chaptersPerVolume}`, { method: 'POST' })
      const data = await res.json()
      alert(data.message)
      pollJob(selectedNovelId)
    } catch (e) {
      console.error(e)
      setIsGenerating(false)
    }
  }

  // Quick Action: Generate next pending volume from the list page
  const handleQuickGenerateNext = async (novelId: number) => {
    setQuickGeneratingNovelId(novelId)
    try {
      // 1. Fetch current volumes status
      const resVol = await fetch(`/api/novels/${novelId}/audio/volumes?chapters_per_volume=${chaptersPerVolume}`)
      if (!resVol.ok) {
        alert("Không thể lấy danh sách tập của truyện.")
        return
      }
      const dataVol = await resVol.json()
      
      if (!dataVol.volumes || dataVol.volumes.length === 0) {
        alert("Chưa có chương nào được dịch hoàn tất để chia tập audio.")
        return
      }

      // 2. Find first uncreated volume
      const nextVol = dataVol.volumes.find((v: VolumeInfo) => !v.is_created)
      if (!nextVol) {
        alert("Tất cả các tập audio của truyện này đã được tạo xong!")
        return
      }

      // 3. Trigger generation
      const resGen = await fetch(`/api/novels/${novelId}/audio/generate_volume/${nextVol.volume_no}?voice_profile=default&chapters_per_volume=${chaptersPerVolume}`, { method: 'POST' })
      const dataGen = await resGen.json()
      alert(`Đã kích hoạt tạo Tập {nextVol.volume_no} ({nextVol.start_chapter} - {nextVol.end_chapter}):\n${dataGen.message}`)
      
      // Select and enter details view to track progress
      setSelectedNovelId(novelId)
      setActiveView('detail')
    } catch (e) {
      console.error(e)
      alert("Lỗi khi kích hoạt tạo audio nhanh.")
    } finally {
      setQuickGeneratingNovelId(null)
    }
  }

  // Audio Playback logic
  const handlePlayVolume = (vol: VolumeInfo) => {
    if (!vol.download_url) return
    if (currentPlaying?.volume_no === vol.volume_no) {
      if (isPlaying) {
        audioRef.current?.pause()
        setIsPlaying(false)
      } else {
        audioRef.current?.play()
        setIsPlaying(true)
      }
    } else {
      setCurrentPlaying(vol)
      setIsPlaying(true)
      
      // Auto select first chapter of this volume to show text
      setReadingChapterNo(vol.start_chapter)
    }
  }

  // Delete Audio File handlers
  const handleDeleteAudioFile = async (vol: VolumeInfo) => {
    if (!vol.filename) return
    if (!confirm(`Bạn có chắc chắn muốn xóa file audio "${vol.filename}"?`)) return
    
    try {
      let res = await fetch(`/api/novels/${selectedNovelId}/audio/files/${encodeURIComponent(vol.filename)}`, {
        method: 'DELETE'
      })
      if (!res.ok && res.status === 405) {
        res = await fetch(`/api/novels/${selectedNovelId}/audio/delete_file/${encodeURIComponent(vol.filename)}`, {
          method: 'POST'
        })
      }
      const data = await res.json()
      if (res.ok) {
        if (currentPlaying?.volume_no === vol.volume_no) {
          audioRef.current?.pause()
          setIsPlaying(false)
          setCurrentPlaying(null)
        }
        fetchVolumes(selectedNovelId)
      } else {
        alert(data.detail || "Không thể xóa file audio.")
      }
    } catch (e) {
      console.error(e)
      alert("Lỗi khi xóa file audio.")
    }
  }

  const handleDeleteAllAudioFiles = async () => {
    if (!selectedNovelId || !volumeData || volumeData.created_volumes_count === 0) return
    if (!confirm(`Bạn có chắc chắn muốn xóa TOÀN BỘ ${volumeData.created_volumes_count} file audio đã tạo của truyện "${volumeData.novel_title}"?`)) return

    try {
      let res = await fetch(`/api/novels/${selectedNovelId}/audio/files`, {
        method: 'DELETE'
      })
      if (!res.ok && res.status === 405) {
        res = await fetch(`/api/novels/${selectedNovelId}/audio/delete_all`, {
          method: 'POST'
        })
      }
      const data = await res.json()
      if (res.ok) {
        audioRef.current?.pause()
        setIsPlaying(false)
        setCurrentPlaying(null)
        alert(data.message || "Đã xóa toàn bộ file audio.")
        fetchVolumes(selectedNovelId)
      } else {
        alert(data.detail || "Lỗi khi xóa toàn bộ file audio.")
      }
    } catch (e) {
      console.error(e)
      alert("Lỗi kết nối khi xóa toàn bộ file audio.")
    }
  }

  useEffect(() => {
    if (audioRef.current && currentPlaying?.download_url) {
      audioRef.current.src = currentPlaying.download_url
      audioRef.current.playbackRate = playbackRate
      audioRef.current.play()
        .then(() => setIsPlaying(true))
        .catch(err => console.error("Playback failed", err))
    }
  }, [currentPlaying])

  const togglePlay = () => {
    if (!audioRef.current) return
    if (isPlaying) {
      audioRef.current.pause()
      setIsPlaying(false)
    } else {
      audioRef.current.play()
      setIsPlaying(true)
    }
  }

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseFloat(e.target.value)
    setCurrentTime(val)
    if (audioRef.current) {
      audioRef.current.currentTime = val
    }
  }

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseFloat(e.target.value)
    setVolume(val)
    if (audioRef.current) {
      audioRef.current.volume = val
      setIsMuted(val === 0)
    }
  }

  const toggleMute = () => {
    if (!audioRef.current) return
    if (isMuted) {
      audioRef.current.volume = volume || 1.0
      setIsMuted(false)
    } else {
      audioRef.current.volume = 0
      setIsMuted(true)
    }
  }

  const handleRateChange = (newRate: number) => {
    setPlaybackRate(newRate)
    if (audioRef.current) {
      audioRef.current.playbackRate = newRate
    }
  }

  const skipTime = (seconds: number) => {
    if (!audioRef.current) return
    audioRef.current.currentTime = Math.max(0, Math.min(duration, audioRef.current.currentTime + seconds))
  }

  const formatTime = (secs: number) => {
    if (isNaN(secs)) return "00:00"
    const h = Math.floor(secs / 3600)
    const m = Math.floor((secs % 3600) / 60)
    const s = Math.floor(secs % 60)
    if (h > 0) {
      return `${h}:${m < 10 ? '0' : ''}${m}:${s < 10 ? '0' : ''}${s}`
    }
    return `${m}:${s < 10 ? '0' : ''}${s}`
  }

  // Filtered volumes helper
  const filteredVolumes = (volumeData?.volumes || []).filter(v => {
    if (filter === 'CREATED') return v.is_created
    if (filter === 'UNCREATED') return !v.is_created
    return true
  })

  // List view: Novels showing completed chapter count
  const renderNovelsList = () => {
    return (
      <div className="flex-1 p-6 overflow-y-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
              <Headphones className="w-6 h-6 text-emerald-400" />
              Audio Studio — Quản Lý Sách Nói
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              Danh sách truyện dịch và số chương đã hoàn thành. Nhấp vào truyện để mở trình phát hoặc bắt đầu tạo audio.
            </p>
          </div>
        </div>

        {novels.length === 0 ? (
          <div className="text-center py-20 border border-dashed border-slate-800 rounded-2xl bg-slate-900/10">
            <BookOpen className="w-12 h-12 text-slate-600 mx-auto mb-3" />
            <p className="text-slate-400 text-sm">Chưa có truyện nào trong thư viện.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {novels.map((novel) => {
              const totalCh = novel.total_chapters || 0
              const doneCh = novel.completed_chapters || 0
              const isProcessing = quickGeneratingNovelId === novel.id

              return (
                <div
                  key={novel.id}
                  className="bg-slate-900/40 border border-slate-800/80 hover:border-emerald-500/30 rounded-2xl p-5 flex flex-col justify-between gap-4 transition-all hover:shadow-lg hover:shadow-emerald-950/10"
                >
                  <div className="flex gap-4">
                    {novel.cover_url ? (
                      <img src={novel.cover_url} alt={novel.title} className="w-16 h-22 object-cover rounded-xl border border-slate-800 shadow" />
                    ) : (
                      <div className="w-16 h-22 bg-slate-950 flex items-center justify-center rounded-xl border border-slate-800">
                        <BookOpen className="w-7 h-7 text-slate-700" />
                      </div>
                    )}
                    <div className="flex-1 min-w-0">
                      <h3 className="font-bold text-sm text-slate-100 leading-snug truncate" title={novel.title}>
                        {novel.title}
                      </h3>
                      <p className="text-xs text-slate-400 truncate mt-1">Tác giả: {novel.author || "Khuyết Danh"}</p>
                      
                      {/* Chapter progress */}
                      <div className="mt-3 flex items-center justify-between text-xs">
                        <span className="text-slate-400">Đã dịch:</span>
                        <span className="font-semibold text-emerald-400 font-mono">{doneCh}/{totalCh} chương</span>
                      </div>
                      <div className="w-full bg-slate-950 h-1.5 rounded-full overflow-hidden mt-1.5 border border-slate-800">
                        <div 
                          className="bg-gradient-to-r from-emerald-500 to-teal-400 h-full rounded-full transition-all duration-300"
                          style={{ width: `${totalCh > 0 ? (doneCh / totalCh) * 100 : 0}%` }}
                        />
                      </div>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="pt-3 border-t border-slate-800/60 flex items-center gap-3">
                    <button
                      onClick={() => {
                        setSelectedNovelId(novel.id)
                        setActiveView('detail')
                      }}
                      className="flex-1 py-2 px-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold transition-all flex items-center justify-center gap-1.5"
                    >
                      <Layers className="w-3.5 h-3.5" />
                      Vào Studio
                    </button>

                    <button
                      onClick={() => handleQuickGenerateNext(novel.id)}
                      disabled={isProcessing || doneCh === 0}
                      className="flex-1 py-2 px-3 rounded-xl bg-emerald-500/10 hover:bg-emerald-500 text-emerald-400 hover:text-slate-950 border border-emerald-500/20 text-xs font-bold transition-all flex items-center justify-center gap-1.5 disabled:opacity-40"
                      title="Tự động chia và tạo tập audio tiếp theo sau tập đã hoàn thành"
                    >
                      {isProcessing ? (
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Zap className="w-3.5 h-3.5" />
                      )}
                      Tạo Tập Tiếp Theo
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    )
  }

  // Detail view: Audio generator, player, converted list, and chapter reader
  const renderDetailView = () => {
    if (!selectedNovel) return null

    // Determine chapters in currently playing volume
    const playingVolumeChapters = currentPlaying && volumeData
      ? Array.from(
          { length: currentPlaying.end_chapter - currentPlaying.start_chapter + 1 },
          (_, i) => currentPlaying.start_chapter + i
        )
      : []

    return (
      <div className="flex-1 flex flex-col min-h-0 overflow-hidden bg-slate-950">
        {/* Detail Header */}
        <div className="border-b border-slate-900 px-6 py-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-4 bg-slate-900/10 flex-shrink-0">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setActiveView('list')}
              className="p-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-400 hover:text-slate-200 transition-all"
            >
              <ArrowLeft className="w-4 h-4" />
            </button>
            <div>
              <h1 className="text-md font-bold text-slate-100 flex items-center gap-2">
                📖 {selectedNovel.title}
              </h1>
              <p className="text-[11px] text-slate-400 mt-0.5">
                Giọng mặc định nữ Hoài My (<code className="text-emerald-400">vi-VN-HoaiMyNeural</code>) • Phân tập cố định {chaptersPerVolume} chương
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            <select
              value={chaptersPerVolume}
              onChange={(e) => setChaptersPerVolume(Number(e.target.value))}
              className="bg-slate-900 border border-emerald-500/20 rounded-xl px-3 py-2 text-xs font-semibold text-emerald-300 focus:outline-none focus:border-emerald-400/50"
              title="Số chương mỗi tập"
            >
              <option value={1}>🎧 1 Chương / Tập</option>
              <option value={2}>🎧 2 Chương / Tập</option>
              <option value={5}>🎧 5 Chương / Tập</option>
              <option value={10}>🎧 10 Chương / Tập</option>
              <option value={15}>🎧 15 Chương / Tập</option>
              <option value={20}>🎧 20 Chương / Tập</option>
              <option value={30}>🎧 30 Chương / Tập</option>
              <option value={50}>🎧 50 Chương / Tập</option>
              <option value={100}>🎧 100 Chương / Tập</option>
            </select>

            <select
              value={voiceProfile}
              onChange={(e) => setVoiceProfile(e.target.value)}
              className="bg-slate-900 border border-emerald-500/20 rounded-xl px-3 py-2 text-xs font-semibold text-emerald-300 focus:outline-none focus:border-emerald-400/50"
              title="Chọn giọng đọc"
            >
              <option value="default">🎙️ Mặc Định (Nữ Hoài My)</option>
              <option value="ngon_tinh">🎙️ Ngôn Tình (Nữ Hoài My)</option>
              <option value="tien_hiep">🎙️ Tiên Hiệp (Nam Minh)</option>
              <option value="kiem_hiep">🎙️ Kiếm Hiệp (Nam Minh +25%)</option>
            </select>

            {isGenerating ? (
              <button
                onClick={handleCancelJob}
                className="bg-rose-600/90 hover:bg-rose-600 text-white font-bold px-4 py-2 rounded-xl text-xs flex items-center gap-2 transition-all"
              >
                🛑 Hủy Tiến Trình
              </button>
            ) : (
              <button
                onClick={() => handleQuickGenerateNext(selectedNovel.id)}
                className="bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold px-4 py-2 rounded-xl text-xs flex items-center gap-2 transition-all shadow-md shadow-emerald-950/20"
              >
                <Zap className="w-4 h-4" />
                Tạo Tập Tiếp Theo
              </button>
            )}
          </div>
        </div>

        {/* Job status banner if generating */}
        {jobStatus?.is_running && (() => {
          const pct = jobStatus.progress_pct ?? jobStatus.progress?.percent ?? 0
          const done = jobStatus.progress?.done_chunks ?? 0
          const total = jobStatus.progress?.total_chunks ?? 0
          const workers = jobStatus.progress?.worker_count || 6
          const speed = jobStatus.progress?.speed_chunks_per_min ?? 0
          const volLabel = (jobStatus.volume_no && jobStatus.volume_no >= 1000000) ? "khoảng chương tùy chỉnh" : `Tập ${jobStatus.volume_no || ''}`
          const msg = jobStatus.msg || (done === 0 
            ? `🚀 Đang khởi động ${workers} Workers tổng hợp audio ${volLabel}...`
            : `Đang tổng hợp audio ${volLabel}: ${done}/${total} chương (${pct}%)`)
          const eta = (done === 0 || !jobStatus.eta_display)
            ? "Đang tính toán..."
            : jobStatus.eta_display
          
          return (
            <div className="mx-6 mt-4 p-3 rounded-xl bg-emerald-950/40 border border-emerald-500/30 text-emerald-300 text-xs flex flex-col gap-2 flex-shrink-0 shadow-lg shadow-emerald-950/20">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div className="flex items-center gap-2">
                  <RefreshCw className="w-4 h-4 animate-spin text-emerald-400" />
                  <span className="font-semibold text-slate-100">{msg}</span>
                </div>
                <div className="flex items-center gap-3 font-mono text-[11px]">
                  {total > 0 && (
                    <span className="text-emerald-400 bg-emerald-900/40 px-2 py-0.5 rounded-md border border-emerald-500/20">
                      📚 {done}/{total} chương ({workers > 0 ? `${workers} workers` : 'FFmpeg mode'})
                    </span>
                  )}
                  {eta && (
                    <span className="text-slate-300">⏱️ Còn: <strong className="text-emerald-300 font-bold">{eta}</strong></span>
                  )}
                  {speed > 0 && (
                    <span className="text-teal-300">⚡ {(speed).toFixed(1)} chương/phút</span>
                  )}
                  <span className="font-bold text-emerald-400 text-sm bg-emerald-500/10 px-2 py-0.5 rounded-lg border border-emerald-500/30">{pct}%</span>
                </div>
              </div>
              <div className="w-full bg-slate-900 rounded-full h-2 overflow-hidden border border-slate-800">
                <div 
                  className="bg-gradient-to-r from-emerald-500 via-teal-400 to-cyan-400 h-full rounded-full transition-all duration-300 shadow-sm" 
                  style={{ width: `${Math.min(100, Math.max(0, pct))}%` }} 
                />
              </div>
            </div>
          )
        })()}

        {/* Detailed Grid (Left: List of converted audios, Right: Player & Reader) */}
        <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-6 p-6 overflow-hidden min-h-0">
          
          {/* Left Panel: Audio Volume List (4 columns) */}
          <div className="lg:col-span-4 flex flex-col overflow-hidden min-h-0 bg-slate-900/20 border border-slate-900 rounded-2xl p-4">
            <div className="flex items-center justify-between mb-4 flex-shrink-0">
              <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
                <Layers className="w-4 h-4 text-emerald-400" />
                Danh Sách Tập (Mỗi tập {chaptersPerVolume} chương)
              </h3>
              <div className="flex items-center gap-2">
                {volumeData && (
                  <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[10px] font-bold font-mono">
                    {volumeData.created_volumes_count}/{volumeData.total_volumes} OK
                  </span>
                )}
                {volumeData && volumeData.created_volumes_count > 0 && (
                  <button
                    onClick={handleDeleteAllAudioFiles}
                    className="text-[10px] text-red-400 hover:text-red-300 flex items-center gap-1 bg-red-500/10 hover:bg-red-500/20 px-2 py-0.5 rounded-lg border border-red-500/20 transition-all font-bold"
                    title="Xóa tất cả audio đã tạo của truyện này"
                  >
                    <Trash2 className="w-3 h-3" /> Xóa Hết
                  </button>
                )}
              </div>
            </div>

            {/* Tạo Audio Theo Khoảng Chương Tùy Chỉnh (Luồng đi y hệt dịch truyện) */}
            <div className="bg-slate-900/60 border border-emerald-500/15 rounded-2xl p-4 mb-4 flex flex-col gap-3 flex-shrink-0">
              <h4 className="text-xs font-bold text-emerald-400 flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-emerald-400" /> Tạo Audio Khoảng Tùy Chỉnh
              </h4>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] text-slate-400 block mb-1 font-semibold">Từ Chương Số</label>
                  <input
                    type="number"
                    min={1}
                    placeholder="Ví dụ: 1"
                    value={customStartChapter ?? ""}
                    onChange={(e) => setCustomStartChapter(e.target.value ? parseInt(e.target.value) : null)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-slate-100 font-bold focus:outline-none focus:border-emerald-500/40"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-slate-400 block mb-1 font-semibold">Đến Chương Số</label>
                  <input
                    type="number"
                    min={1}
                    placeholder="Ví dụ: 50"
                    value={customEndChapter ?? ""}
                    onChange={(e) => setCustomEndChapter(e.target.value ? parseInt(e.target.value) : null)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-slate-100 font-bold focus:outline-none focus:border-emerald-500/40"
                  />
                </div>
              </div>
              
              <button
                onClick={handleGenerateCustomRange}
                disabled={isGenerating || !customStartChapter || !customEndChapter}
                className="w-full py-2 px-3 rounded-xl bg-gradient-to-r from-emerald-500/20 to-teal-500/20 hover:from-emerald-500 hover:to-teal-500 text-emerald-400 hover:text-slate-950 border border-emerald-500/30 hover:border-transparent text-xs font-bold transition-all flex items-center justify-center gap-1.5 disabled:opacity-40"
              >
                <Sparkles className="w-3.5 h-3.5" />
                Bắt Đầu Tạo Audio Khoảng Này
              </button>
            </div>

            {/* Audio 3-Status Summary Badges */}
            <div className="grid grid-cols-3 gap-2 mb-3 flex-shrink-0">
              <div className="bg-slate-950/80 p-2 rounded-xl border border-emerald-500/30 flex items-center justify-between">
                <span className="text-[10px] text-slate-400 font-semibold flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-emerald-400"></span> Đã xong
                </span>
                <span className="text-xs font-bold font-mono text-emerald-400">{volumeData?.created_volumes_count || 0}</span>
              </div>
              <div className={`bg-slate-950/80 p-2 rounded-xl border transition-all flex items-center justify-between ${jobStatus?.is_running ? 'border-amber-500/50 shadow-sm shadow-amber-500/10' : 'border-slate-900'}`}>
                <span className="text-[10px] text-slate-400 font-semibold flex items-center gap-1">
                  <span className={`w-2 h-2 rounded-full ${jobStatus?.is_running ? 'bg-amber-400 animate-ping' : 'bg-slate-600'}`}></span> Đang làm
                </span>
                <span className={`text-xs font-bold font-mono ${jobStatus?.is_running ? 'text-amber-400' : 'text-slate-500'}`}>{jobStatus?.is_running ? 1 : 0}</span>
              </div>
              <div className="bg-slate-950/80 p-2 rounded-xl border border-slate-900 flex items-center justify-between">
                <span className="text-[10px] text-slate-400 font-semibold flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-slate-500"></span> Chưa xong
                </span>
                <span className="text-xs font-bold font-mono text-slate-300">
                  {Math.max(0, (volumeData?.total_volumes || 0) - (volumeData?.created_volumes_count || 0) - (jobStatus?.is_running ? 1 : 0))}
                </span>
              </div>
            </div>

            {/* Filter buttons */}
            <div className="flex gap-1 bg-slate-950 p-1 rounded-xl border border-slate-900 text-[10px] font-bold mb-3 flex-shrink-0">
              <button
                onClick={() => setFilter('ALL')}
                className={`flex-1 py-1 px-2 rounded-lg transition-all ${filter === 'ALL' ? 'bg-emerald-500 text-slate-950' : 'text-slate-400 hover:text-slate-200'}`}
              >
                Tất Cả ({volumeData?.total_volumes || 0})
              </button>
              <button
                onClick={() => setFilter('CREATED')}
                className={`flex-1 py-1 px-2 rounded-lg transition-all ${filter === 'CREATED' ? 'bg-emerald-500 text-slate-950' : 'text-slate-400 hover:text-slate-200'}`}
              >
                Đã Có ({volumeData?.created_volumes_count || 0})
              </button>
              <button
                onClick={() => setFilter('UNCREATED')}
                className={`flex-1 py-1 px-2 rounded-lg transition-all ${filter === 'UNCREATED' ? 'bg-emerald-500 text-slate-950' : 'text-slate-400 hover:text-slate-200'}`}
              >
                Chưa Có ({Math.max(0, (volumeData?.total_volumes || 0) - (volumeData?.created_volumes_count || 0))})
              </button>
            </div>

            {/* List */}
            <div className="flex-1 overflow-y-auto min-h-0 pr-1 flex flex-col gap-2">
              {loading ? (
                <div className="flex items-center justify-center py-10 text-slate-400 text-xs gap-2">
                  <RefreshCw className="w-4 h-4 animate-spin text-emerald-400" />
                  Đang tải tập...
                </div>
              ) : filteredVolumes.length === 0 ? (
                <div className="text-center py-10 text-slate-500 text-xs">
                  Không có tập nào khớp bộ lọc.
                </div>
              ) : (
                filteredVolumes.map((vol) => {
                  const isCurrent = currentPlaying?.volume_no === vol.volume_no
                  
                  return (
                    <div
                      key={vol.volume_no}
                      className={`p-3 rounded-xl border transition-all flex flex-col gap-2.5 ${
                        isCurrent
                          ? 'bg-emerald-950/20 border-emerald-500/40 shadow-sm'
                          : vol.is_created
                          ? 'bg-slate-900/40 border-slate-900 hover:border-slate-800'
                          : 'bg-slate-950/20 border-slate-900/50 opacity-80 hover:opacity-100'
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-[10px] font-bold px-2 py-0.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-200 font-mono">
                              {vol.is_custom ? "Tùy Chỉnh" : `Tập ${vol.volume_no}`}
                            </span>
                            {vol.is_custom && (
                              <span className="text-[9px] font-bold text-amber-400 flex items-center gap-0.5 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/20 font-mono">
                                <Sparkles className="w-2.5 h-2.5" /> Tùy chọn
                              </span>
                            )}
                            {vol.is_created ? (
                              <span className="text-[9px] font-bold text-emerald-400 flex items-center gap-0.5">
                                <CheckCircle className="w-3 h-3" /> Audio OK
                              </span>
                            ) : (vol.cached_chapters_count || 0) > 0 ? (
                              <span className="text-[9px] font-bold text-teal-300 flex items-center gap-0.5 bg-teal-500/10 px-1.5 py-0.5 rounded border border-teal-500/20 font-mono">
                                <Zap className="w-2.5 h-2.5" /> Đã cache {vol.cached_chapters_count}/{vol.chapter_count} ch
                              </span>
                            ) : (
                              <span className="text-[9px] font-bold text-amber-500 flex items-center gap-0.5">
                                <Clock className="w-3 h-3" /> Chưa tạo
                              </span>
                            )}
                          </div>
                          <h4 className="text-xs font-bold text-slate-200 mt-2">
                            Chương {vol.start_chapter} - {vol.end_chapter}
                          </h4>
                          <p className="text-[10px] text-slate-400 mt-1 font-mono">
                            📝 {(vol.word_count || 0).toLocaleString()} từ • {vol.is_created ? (vol.file_size || `${vol.size_mb || 0} MB`) : `~${vol.estimated_hours || 0}h`}
                          </p>
                        </div>
                      </div>

                      {/* Action */}
                      <div className="pt-2 border-t border-slate-900 flex items-center gap-2">
                        {vol.is_created ? (
                          <>
                            <button
                              onClick={() => handlePlayVolume(vol)}
                              className={`flex-1 text-[11px] font-bold py-1.5 px-2.5 rounded-lg border flex items-center justify-center gap-1 transition-all ${
                                isCurrent && isPlaying
                                  ? 'bg-emerald-500 text-slate-950 border-emerald-400'
                                  : 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20 hover:bg-emerald-500/20'
                              }`}
                            >
                              {isCurrent && isPlaying ? (
                                <>
                                  <Pause className="w-3 h-3 fill-slate-950" /> Tạm Dừng
                                </>
                              ) : (
                                <>
                                  <Play className="w-3 h-3 fill-emerald-300" /> Nghe Tập Này
                                </>
                              )}
                            </button>
                            <a
                              href={vol.download_url}
                              download
                              className="p-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 transition-all"
                              title="Tải MP3"
                            >
                              <Download className="w-3.5 h-3.5" />
                            </a>
                            <button
                              onClick={() => handleDeleteAudioFile(vol)}
                              className="p-1.5 rounded-lg bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 text-red-400 hover:border-red-500/40 transition-all"
                              title="Xóa file audio này"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </>
                        ) : (
                          <button
                            onClick={() => handleGenerateSingleVolume(vol.volume_no)}
                            disabled={isGenerating}
                            className="w-full text-[11px] font-bold py-1.5 px-2.5 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/20 hover:border-amber-500/30 transition-all flex items-center justify-center gap-1 disabled:opacity-40"
                          >
                            <Sparkles className="w-3 h-3" />
                            Tạo Tập Này ({chaptersPerVolume} ch)
                          </button>
                        )}
                      </div>
                    </div>
                  )
                })
              )}
            </div>
          </div>

          {/* Right Panel: Audio Player & Text Reader (8 columns) */}
          <div className="lg:col-span-8 flex flex-col overflow-hidden min-h-0 gap-4">
            
            {/* Custom Audio Player Panel */}
            <div className="p-4 rounded-2xl border border-emerald-500/20 bg-gradient-to-r from-slate-900 to-emerald-950/20 flex flex-col gap-3 flex-shrink-0">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 flex-shrink-0">
                    <Music className="w-5 h-5 animate-pulse" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-emerald-400">Đang Phát Audio</p>
                    <h3 className="text-xs font-bold text-slate-100 truncate max-w-sm" title={currentPlaying?.filename || "Chưa phát"}>
                      {currentPlaying ? currentPlaying.filename : "Bấm 'Nghe Tập Này' ở cột bên trái để nghe và đọc truyện"}
                    </h3>
                  </div>
                </div>

                {/* Speed Selector (1x, 1.5x, 2x, 3x, 4x) */}
                <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-xl border border-slate-900 self-start md:self-auto flex-shrink-0">
                  <span className="text-[9px] text-slate-400 font-bold px-1.5">Tốc độ:</span>
                  {[1.0, 1.5, 2.0, 3.0, 4.0].map(rate => (
                    <button
                      key={rate}
                      onClick={() => handleRateChange(rate)}
                      className={`text-[10px] font-bold px-2 py-1 rounded-lg transition-all ${
                        playbackRate === rate
                          ? 'bg-emerald-500 text-slate-950'
                          : 'text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      {rate}x
                    </button>
                  ))}
                </div>
              </div>

              {/* Progress Slider */}
              <div className="flex items-center gap-3">
                <span className="text-[10px] font-mono text-slate-400 w-12 text-right">{formatTime(currentTime)}</span>
                <input
                  type="range"
                  min={0}
                  max={duration || 100}
                  value={currentTime}
                  onChange={handleSeek}
                  className="flex-1 accent-emerald-500 cursor-pointer h-1.5 bg-slate-905 rounded-lg"
                />
                <span className="text-[10px] font-mono text-slate-400 w-12">{formatTime(duration)}</span>
              </div>

              {/* Player buttons */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => skipTime(-10)}
                    className="p-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 transition-all text-xs"
                    title="Lùi 10s"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                  </button>

                  <button
                    onClick={togglePlay}
                    disabled={!currentPlaying}
                    className="w-9 h-9 rounded-full bg-emerald-500 hover:bg-emerald-400 text-slate-950 flex items-center justify-center font-bold shadow transition-all disabled:opacity-40"
                  >
                    {isPlaying ? <Pause className="w-4 h-4 fill-slate-950" /> : <Play className="w-4 h-4 fill-slate-950 ml-0.5" />}
                  </button>

                  <button
                    onClick={() => skipTime(10)}
                    className="p-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 transition-all text-xs"
                    title="Tới 10s"
                  >
                    <RotateCw className="w-3.5 h-3.5" />
                  </button>
                </div>

                {/* Volume slider */}
                <div className="flex items-center gap-2">
                  <button onClick={toggleMute} className="text-slate-400 hover:text-emerald-400 transition-colors">
                    {isMuted || volume === 0 ? <VolumeX className="w-3.5 h-3.5 text-rose-400" /> : <Volume2 className="w-3.5 h-3.5" />}
                  </button>
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.05}
                    value={isMuted ? 0 : volume}
                    onChange={handleVolumeChange}
                    className="w-20 accent-emerald-500 cursor-pointer h-1 bg-slate-900 rounded-lg"
                  />
                </div>
              </div>
            </div>

            {/* Novel Text Reader ("có hiện lên truyện") */}
            <div className="flex-1 flex flex-col overflow-hidden min-h-0 bg-slate-900/10 border border-slate-900 rounded-2xl p-4">
              
              {/* Reader control panel */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-900 pb-3 flex-shrink-0">
                <div className="flex items-center gap-2 min-w-0">
                  <FileText className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                  <span className="text-xs font-bold text-slate-200">Đọc Truyện & Nghe Nhạc</span>
                  {currentPlaying && (
                    <span className="text-[10px] text-slate-400 bg-slate-900 border border-slate-800 px-2 py-0.5 rounded font-mono truncate">
                      Tập {currentPlaying.volume_no} ({currentPlaying.start_chapter} - {currentPlaying.end_chapter})
                    </span>
                  )}
                </div>

                {/* Font size and chapter navigation */}
                <div className="flex items-center gap-2 self-start sm:self-auto flex-shrink-0">
                  <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-900">
                    <button
                      onClick={() => setReaderFontSize(f => Math.max(11, f - 1))}
                      className="p-1 text-[10px] text-slate-400 hover:text-slate-200 font-bold"
                      title="Thu nhỏ chữ"
                    >
                      A-
                    </button>
                    <span className="text-[9px] text-slate-400 px-1 font-mono"><Type className="w-3 h-3 inline mr-1" />{readerFontSize}</span>
                    <button
                      onClick={() => setReaderFontSize(f => Math.min(24, f + 1))}
                      className="p-1 text-[10px] text-slate-400 hover:text-slate-200 font-bold"
                      title="Phóng to chữ"
                    >
                      A+
                    </button>
                  </div>

                  {/* Chapter Select Dropdown within current Volume */}
                  {currentPlaying && (
                    <select
                      value={readingChapterNo || ""}
                      onChange={(e) => setReadingChapterNo(Number(e.target.value))}
                      className="bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1 text-[11px] font-bold text-slate-300 focus:outline-none focus:border-emerald-500/40"
                    >
                      <option value="">-- Chọn Chương Để Đọc --</option>
                      {playingVolumeChapters.map(chNo => (
                        <option key={chNo} value={chNo}>📖 Chương {chNo}</option>
                      ))}
                    </select>
                  )}
                </div>
              </div>

              {/* Reader content area */}
              <div className="flex-1 overflow-y-auto min-h-0 mt-3 pr-1">
                {readerLoading ? (
                  <div className="flex flex-col items-center justify-center py-20 text-slate-500 text-xs gap-2">
                    <RefreshCw className="w-5 h-5 animate-spin text-emerald-400" />
                    Đang tải văn bản chương...
                  </div>
                ) : readingChapterText ? (
                  <article className="prose prose-invert max-w-none">
                    <h3 className="text-sm font-bold text-emerald-400 mb-3 border-b border-slate-900 pb-2 font-serif">
                      {readingChapterText.title}
                    </h3>
                    <div 
                      className="text-slate-300 leading-relaxed font-sans whitespace-pre-line"
                      style={{ fontSize: `${readerFontSize}px` }}
                      dangerouslySetInnerHTML={{ __html: readingChapterText.translated_text }}
                    />
                  </article>
                ) : (
                  <div className="flex flex-col items-center justify-center py-20 text-slate-500 text-xs text-center">
                    <BookOpen className="w-8 h-8 text-slate-700 mb-2" />
                    {currentPlaying ? (
                      <p>Vui lòng chọn một chương ở góc trên bên phải để bắt đầu đọc truyện.</p>
                    ) : (
                      <p>Hãy bấm 'Nghe Tập Này' ở cột bên trái để tải truyện lên giao diện đọc.</p>
                    )}
                  </div>
                )}
              </div>

            </div>

          </div>

        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full bg-slate-950 text-slate-100 overflow-hidden relative">
      {/* Hidden HTML Audio Element */}
      <audio
        ref={audioRef}
        onTimeUpdate={() => setCurrentTime(audioRef.current?.currentTime || 0)}
        onLoadedMetadata={() => setDuration(audioRef.current?.duration || 0)}
        onEnded={() => setIsPlaying(false)}
      />

      {activeView === 'list' ? renderNovelsList() : renderDetailView()}
    </div>
  )
}
