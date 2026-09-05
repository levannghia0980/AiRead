import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import { useNovelStore } from '../store/useNovelStore'
import {
  Headphones,
  Play,
  Pause,
  Volume2,
  VolumeX,
  Download,
  RefreshCw,
  Sparkles,
  Zap,
  ArrowLeft,
  BookOpen,
  SkipBack,
  SkipForward,
  Layers,
  ChevronDown,
  RotateCcw,
  RotateCw,
  Gauge,
  Music,
  CheckCircle2,
  Sliders,
  Radio,
  Trash2,
  FileText
} from 'lucide-react'

interface ChapterPlaylistItem {
  chapter_no: number
  title: string
  has_audio: boolean
  has_json?: boolean
  audio_url: string | null
  json_url?: string | null
  file_size?: string | null
  size_bytes?: number
}

export default function AudioStudio() {
  const storeNovels = useNovelStore((state) => state.novels)
  const fetchNovels = useNovelStore((state) => state.fetchNovels)

  const [activeView, setActiveView] = useState<'list' | 'detail'>('detail')
  const [selectedNovelId, setSelectedNovelId] = useState<number>(0)
  const [mobileTab, setMobileTab] = useState<'player' | 'playlist' | 'tools'>('playlist')

  // Ensure novels list is loaded
  useEffect(() => {
    if (!storeNovels || storeNovels.length === 0) {
      fetchNovels()
    }
  }, [storeNovels, fetchNovels])

  // Pick first novel if none selected
  useEffect(() => {
    if (storeNovels && storeNovels.length > 0 && !selectedNovelId) {
      setSelectedNovelId(storeNovels[0].id)
    }
  }, [storeNovels, selectedNovelId])

  const [playlist, setPlaylist] = useState<ChapterPlaylistItem[]>([])
  const [loading, setLoading] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [filter, setFilter] = useState<'ALL' | 'AUDIO_READY' | 'AUDIO_PENDING'>('ALL')
  
  // Audio Player State
  const [currentChapterNo, setCurrentChapterNo] = useState<number | null>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [volume, setVolume] = useState(1.0)
  const [playbackRate, setPlaybackRate] = useState<number>(() => {
    const saved = localStorage.getItem('audio_playback_rate')
    return saved ? Number(saved) : 1.0
  })
  const [isMuted, setIsMuted] = useState(false)
  const [autoNext, setAutoNext] = useState(true)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  // Batch TTS Range & Config
  const [ttsRangeStart, setTtsRangeStart] = useState<number>(1)
  const [ttsRangeEnd, setTtsRangeEnd] = useState<number>(50)
  const [voiceProfile, setVoiceProfile] = useState<string>('default')
  const [parallelWorkers, setParallelWorkers] = useState<number>(() => {
    const saved = localStorage.getItem('tts_parallel_workers')
    return saved ? Number(saved) : 8
  })

  // Export / Download Range & Config
  const [exportRangeStart, setExportRangeStart] = useState<number>(1)
  const [exportRangeEnd, setExportRangeEnd] = useState<number>(50)
  const [exportSpeed, setExportSpeedState] = useState<number>(() => {
    const saved = localStorage.getItem('tts_export_speed')
    return saved ? Number(saved) : 1.5
  })
  const setExportSpeed = (spd: number) => {
    setExportSpeedState(spd)
    localStorage.setItem('tts_export_speed', String(spd))
  }

  // Auto Partition Bundles (10h - <12h)
  const [autoBundles, setAutoBundles] = useState<any[]>([])
  const [loadingBundles, setLoadingBundles] = useState(false)

  const fetchAutoBundles = useCallback(async (novelId: number, speed: number = 1.5) => {
    if (!novelId) return
    setLoadingBundles(true)
    try {
      const res = await fetch(`/api/novels/${novelId}/audio/auto_partition_bundles?speed=${speed}&min_hours=10.0&max_hours=11.95`)
      if (res.ok) {
        const data = await res.json()
        setAutoBundles(data.bundles || [])
      }
    } catch (e) {
      console.error('Failed to fetch auto bundles:', e)
    } finally {
      setLoadingBundles(false)
    }
  }, [])

  // TTS Job Progress & Status
  const [jobStatus, setJobStatus] = useState<any>(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const [isMerging, setIsMerging] = useState(false)
  const [mergeResult, setMergeResult] = useState<any>(null)

  // Fetch playlist callback
  const fetchPlaylist = useCallback(async (novelId: number) => {
    if (!novelId) return
    setLoading(true)
    try {
      const res = await fetch(`/api/novels/${novelId}/audio/playlist`)
      if (res.ok) {
        const data = await res.json()
        const items = data.playlist || []
        setPlaylist(items)
        if (items.length > 0) {
          // 1. Khoảng Tạo TTS: Tự động tìm chương nhỏ nhất chưa có Audio
          const firstUnready = items.find((it: ChapterPlaylistItem) => !it.has_audio)
          if (firstUnready) {
            setTtsRangeStart(firstUnready.chapter_no)
          } else {
            setTtsRangeStart(items[0].chapter_no)
          }
          const lastCh = items[items.length - 1].chapter_no
          setTtsRangeEnd(lastCh)

          // 2. Khoảng Xuất / Tải File: Tự động tìm khoảng các chương ĐÃ CÓ AUDIO
          const readyItems = items.filter((it: ChapterPlaylistItem) => it.has_audio)
          if (readyItems.length > 0) {
            setExportRangeStart(readyItems[0].chapter_no)
            setExportRangeEnd(readyItems[readyItems.length - 1].chapter_no)
          } else {
            setExportRangeStart(items[0].chapter_no)
            setExportRangeEnd(lastCh)
          }
        }
      }
    } catch (e) {
      console.error('Failed to fetch audio playlist:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  // Auto fetch playlist & auto bundles when selected novel or speed changes
  useEffect(() => {
    if (selectedNovelId) {
      fetchPlaylist(selectedNovelId)
      fetchAutoBundles(selectedNovelId, exportSpeed)
    }
  }, [selectedNovelId, fetchPlaylist, fetchAutoBundles, exportSpeed])

  const [savedHistory, setSavedHistory] = useState<any>(null)

  // Check saved listening history for current novel
  useEffect(() => {
    if (selectedNovelId) {
      try {
        const saved = localStorage.getItem(`airead_audio_pos_${selectedNovelId}`)
        if (saved) {
          const parsed = JSON.parse(saved)
          setSavedHistory(parsed)
        } else {
          setSavedHistory(null)
        }
      } catch {
        setSavedHistory(null)
      }
    }
  }, [selectedNovelId, currentChapterNo])

  // Auto restore last played chapter from localStorage when novel changes
  useEffect(() => {
    if (selectedNovelId && !currentChapterNo) {
      try {
        const saved = localStorage.getItem(`airead_audio_pos_${selectedNovelId}`)
        if (saved) {
          const parsed = JSON.parse(saved)
          if (parsed && parsed.chapterNo) {
            setCurrentChapterNo(parsed.chapterNo)
            if (parsed.time) setCurrentTime(parsed.time)
            if (parsed.duration) setDuration(parsed.duration)
          }
        }
      } catch (e) {
        // Ignore JSON parse errors
      }
    }
  }, [selectedNovelId, currentChapterNo])

  const isGeneratingRef = useRef(false)
  const lastDoneChapterRef = useRef<number>(-1)
  useEffect(() => {
    isGeneratingRef.current = isGenerating
  }, [isGenerating])

  // Pure Event-Driven SSE TTS Progress Listener with Real-time Playlist Updates
  useEffect(() => {
    if (activeView !== 'detail' || !selectedNovelId) return

    const eventSource = new EventSource(`/api/novels/${selectedNovelId}/audio/events`)
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.is_running) {
          setJobStatus(data)
          setIsGenerating(true)

          // Cập nhật real-time danh sách chương ngay khi có 1 chương vừa tạo xong
          if (data.done_chapters !== undefined && data.done_chapters !== lastDoneChapterRef.current) {
            lastDoneChapterRef.current = data.done_chapters
            fetchPlaylist(selectedNovelId)
          }
        } else {
          if (isGeneratingRef.current) {
            setIsGenerating(false)
            setJobStatus(null)
            fetchPlaylist(selectedNovelId)
          }
        }
      } catch (e) {
        console.error('SSE Error:', e)
      }
    }

    eventSource.onerror = () => {
      // Browser EventSource automatically handles retry
    }

    return () => {
      eventSource.close()
    }
  }, [activeView, selectedNovelId, fetchPlaylist])

  // Play a specific chapter
  const handlePlayChapter = (chNo: number) => {
    if (currentChapterNo === chNo) {
      if (audioRef.current) {
        if (isPlaying) {
          audioRef.current.pause()
          setIsPlaying(false)
        } else {
          audioRef.current.play()
          setIsPlaying(true)
        }
      }
      return
    }

    setCurrentChapterNo(chNo)
    setIsPlaying(true)
    if (audioRef.current) {
      audioRef.current.src = `/api/novels/${selectedNovelId}/audio/stream_chapter/${chNo}`
      audioRef.current.playbackRate = playbackRate
      audioRef.current.play().catch(e => console.warn('Audio play error:', e))
    }
  }

  const handleSpeedChange = (rate: number) => {
    setPlaybackRate(rate)
    localStorage.setItem('audio_playback_rate', String(rate))
    if (audioRef.current) {
      audioRef.current.playbackRate = rate
    }
  }

  const handleSkipBackward = (seconds: number = 10) => {
    if (audioRef.current) {
      const target = Math.max(0, audioRef.current.currentTime - seconds)
      audioRef.current.currentTime = target
      setCurrentTime(target)
    }
  }

  const handleSkipForward = (seconds: number = 10) => {
    if (audioRef.current) {
      const target = Math.min(duration || 999999, audioRef.current.currentTime + seconds)
      audioRef.current.currentTime = target
      setCurrentTime(target)
    }
  }

  // Play next chapter
  const handleNextChapter = () => {
    if (!currentChapterNo) return
    const readyChapters = playlist.filter(p => p.has_audio)
    const curIdx = readyChapters.findIndex(p => p.chapter_no === currentChapterNo)
    if (curIdx >= 0 && curIdx < readyChapters.length - 1) {
      handlePlayChapter(readyChapters[curIdx + 1].chapter_no)
    }
  }

  // Play previous chapter
  const handlePrevChapter = () => {
    if (!currentChapterNo) return
    const readyChapters = playlist.filter(p => p.has_audio)
    const curIdx = readyChapters.findIndex(p => p.chapter_no === currentChapterNo)
    if (curIdx > 0) {
      handlePlayChapter(readyChapters[curIdx - 1].chapter_no)
    }
  }

  // Audio element events
  const onTimeUpdate = () => {
    if (audioRef.current) {
      const cur = audioRef.current.currentTime
      const dur = audioRef.current.duration || 0
      setCurrentTime(cur)
      setDuration(dur)

      // Lưu tiến độ nghe vào localStorage
      if (selectedNovelId && currentChapterNo) {
        try {
          const chapObj = playlist.find(p => p.chapter_no === currentChapterNo)
          const chapTitle = chapObj?.title || `Chương ${currentChapterNo}`
          const historyEntry = {
            novelId: selectedNovelId,
            chapterNo: currentChapterNo,
            chapterTitle: chapTitle,
            time: cur,
            duration: dur,
            percent: dur > 0 ? Math.round((cur / dur) * 100) : 0,
            updatedAt: Date.now()
          }

          localStorage.setItem(`airead_audio_pos_${selectedNovelId}`, JSON.stringify(historyEntry))
          setSavedHistory(historyEntry)
        } catch (e) {}
      }
    }
  }

  // Tiếp tục nghe đoạn dở từ lịch sử
  const handleResumeHistory = (item: any) => {
    if (!item || !item.chapterNo) return
    handlePlayChapter(item.chapterNo)
    setTimeout(() => {
      if (audioRef.current && item.time) {
        audioRef.current.currentTime = item.time
        setCurrentTime(item.time)
      }
    }, 150)
  }

  const onEnded = () => {
    setIsPlaying(false)
    if (autoNext) {
      handleNextChapter()
    }
  }

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const time = Number(e.target.value)
    setCurrentTime(time)
    if (audioRef.current) {
      audioRef.current.currentTime = time
    }
  }

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = Number(e.target.value)
    setVolume(val)
    if (audioRef.current) {
      audioRef.current.volume = val
      setIsMuted(val === 0)
    }
  }

  const toggleMute = () => {
    if (audioRef.current) {
      if (isMuted) {
        audioRef.current.volume = volume || 1.0
        setIsMuted(false)
      } else {
        audioRef.current.volume = 0
        setIsMuted(true)
      }
    }
  }

  const formatSeconds = (sec: number) => {
    if (isNaN(sec) || sec < 0) return '00:00'
    const m = Math.floor(sec / 60)
    const s = Math.floor(sec % 60)
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
  }

  // Filtered playlist with ultra-safe guards
  const filteredPlaylist = useMemo(() => {
    if (!Array.isArray(playlist)) return []
    const q = searchQuery.trim().toLowerCase()
    return playlist.filter(item => {
      if (!item) return false
      const chStr = String(item.chapter_no || '')
      const titleStr = String(item.title || `Chương ${item.chapter_no}`).toLowerCase()
      const matchSearch = q === '' || chStr.includes(q) || titleStr.includes(q)
      
      if (!matchSearch) return false
      if (filter === 'AUDIO_READY') return Boolean(item.has_audio)
      if (filter === 'AUDIO_PENDING') return !item.has_audio
      return true
    })
  }, [playlist, searchQuery, filter])

  // Virtualizer for playlist
  const playlistParentRef = useRef<HTMLDivElement>(null)
  const rowVirtualizer = useVirtualizer({
    count: filteredPlaylist.length,
    getScrollElement: () => playlistParentRef.current,
    estimateSize: () => 48,
    overscan: 12,
  })

  // Start Batch Generation
  const handleStartBatchTTS = async (sChapter?: number, eChapter?: number) => {
    if (!selectedNovelId) return
    const start = sChapter ?? ttsRangeStart
    const end = eChapter ?? ttsRangeEnd
    setIsGenerating(true)
    try {
      const res = await fetch(
        `/api/novels/${selectedNovelId}/audio/generate_custom_range?start_chapter=${start}&end_chapter=${end}&voice_profile=${voiceProfile}&workers=${parallelWorkers}`,
        { method: 'POST' }
      )
      if (!res.ok) {
        const err = await res.json()
        alert(err.detail || 'Lỗi khi khởi chạy tạo audio.')
        setIsGenerating(false)
      }
    } catch (e: any) {
      alert(`Lỗi kết nối: ${e.message}`)
      setIsGenerating(false)
    }
  }

  // Cancel Batch TTS
  const handleCancelTTS = async () => {
    if (!selectedNovelId) return
    try {
      await fetch(`/api/novels/${selectedNovelId}/audio/cancel`, { method: 'POST' })
      setIsGenerating(false)
      setJobStatus(null)
    } catch (e) {
      console.error(e)
    }
  }

  // Tải 1 file bất kỳ qua DOM link
  const downloadSingleFile = (url: string, filename?: string) => {
    if (!url) return
    const a = document.createElement('a')
    a.href = url
    if (filename) a.download = filename
    else a.setAttribute('download', '')
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  // Tải ĐỒNG THỜI cả file MP3 và JSON Timeline (cách nhau 350ms để trình duyệt không chặn tải nhiều file)
  const handleDownloadBoth = (mp3Url?: string, mp3Filename?: string, jsonUrl?: string, jsonFilename?: string) => {
    if (mp3Url) {
      downloadSingleFile(mp3Url, mp3Filename)
    }
    if (jsonUrl) {
      setTimeout(() => {
        downloadSingleFile(jsonUrl, jsonFilename)
      }, 350)
    }
  }

  // Fast Merge with FFmpeg (kèm hỗ trợ tùy chọn tốc độ speed)
  const handleFastMerge = async () => {
    if (!selectedNovelId) return
    setIsMerging(true)
    setMergeResult(null)
    try {
      const res = await fetch(
        `/api/novels/${selectedNovelId}/audio/merge_range?start_chapter=${exportRangeStart}&end_chapter=${exportRangeEnd}&speed=${exportSpeed}`,
        { method: 'POST' }
      )
      const data = await res.json()
      if (res.ok) {
        setMergeResult(data)
        fetchAutoBundles(selectedNovelId, exportSpeed)
        // Tự động tải cả 2 file (MP3 + JSON) ngay khi ghép xong
        if (data.download_url) {
          const jsonUrl = data.json_download_url || `/api/novels/${selectedNovelId}/audio/export_timeline_json?start_chapter=${exportRangeStart}&end_chapter=${exportRangeEnd}&speed=${exportSpeed}`
          const jsonFilename = data.json_filename || `${data.filename?.replace(/\.mp3$/i, '') || 'bundle'}_timeline.json`
          handleDownloadBoth(data.download_url, data.filename, jsonUrl, jsonFilename)
        }
      } else {
        alert(data.detail || 'Lỗi khi ghép audio.')
      }
    } catch (e: any) {
      alert(`Lỗi kết nối: ${e.message}`)
    } finally {
      setIsMerging(false)
    }
  }

  // Fast Merge an Auto-Partitioned Bundle
  const handleMergeBundle = async (bundle: any) => {
    if (!selectedNovelId || !bundle) return
    setExportRangeStart(bundle.start_chapter)
    setExportRangeEnd(bundle.end_chapter)
    setIsMerging(true)
    setMergeResult(null)
    try {
      const res = await fetch(
        `/api/novels/${selectedNovelId}/audio/merge_range?start_chapter=${bundle.start_chapter}&end_chapter=${bundle.end_chapter}&speed=${exportSpeed}`,
        { method: 'POST' }
      )
      const data = await res.json()
      if (res.ok) {
        setMergeResult(data)
        fetchAutoBundles(selectedNovelId, exportSpeed)
        // Tự động tải cả 2 file (MP3 + JSON) ngay khi ghép xong
        if (data.download_url) {
          const jsonUrl = data.json_download_url || bundle.json_download_url || `/api/novels/${selectedNovelId}/audio/export_timeline_json?start_chapter=${bundle.start_chapter}&end_chapter=${bundle.end_chapter}&speed=${exportSpeed}`
          const jsonFilename = data.json_filename || bundle.json_filename || `${data.filename?.replace(/\.mp3$/i, '') || 'bundle'}_timeline.json`
          handleDownloadBoth(data.download_url, data.filename, jsonUrl, jsonFilename)
        }
      } else {
        alert(data.detail || 'Lỗi khi ghép audio.')
      }
    } catch (e: any) {
      alert(`Lỗi kết nối: ${e.message}`)
    } finally {
      setIsMerging(false)
    }
  }

  // Delete Audio of a single chapter to regenerate
  const handleDeleteSingleChapterAudio = async (chNo: number) => {
    if (!selectedNovelId) return
    const ok = window.confirm(`Bạn có chắc chắn muốn xóa Audio Chương ${chNo} để tạo lại từ bản dịch mới nhất?`)
    if (!ok) return
    try {
      const res = await fetch(`/api/novels/${selectedNovelId}/audio/delete_chapter/${chNo}`, { method: 'POST' })
      if (res.ok) {
        if (currentChapterNo === chNo && audioRef.current) {
          audioRef.current.pause()
          setIsPlaying(false)
          setCurrentChapterNo(null)
        }
        fetchPlaylist(selectedNovelId)
      } else {
        const err = await res.json()
        alert(err.detail || 'Lỗi khi xóa audio chương.')
      }
    } catch (e: any) {
      alert(`Lỗi kết nối: ${e.message}`)
    }
  }

  // Delete All Audio files of current novel
  const handleDeleteAllAudio = async () => {
    if (!selectedNovelId) return
    const ok = window.confirm('⚠️ CẢNH BÁO: Bạn có chắc chắn muốn XÓA TOÀN BỘ Audio và văn bản TTS của truyện này để tạo lại từ đầu?')
    if (!ok) return
    try {
      const res = await fetch(`/api/novels/${selectedNovelId}/audio/delete_all`, { method: 'POST' })
      if (res.ok) {
        if (audioRef.current) {
          audioRef.current.pause()
          setIsPlaying(false)
          setCurrentChapterNo(null)
        }
        fetchPlaylist(selectedNovelId)
      } else {
        const err = await res.json()
        alert(err.detail || 'Lỗi khi xóa toàn bộ audio.')
      }
    } catch (e: any) {
      alert(`Lỗi kết nối: ${e.message}`)
    }
  }

  const readyItems = useMemo(() => playlist.filter(p => p.has_audio), [playlist])
  const readyCount = readyItems.length
  const minReadyCh = readyItems.length > 0 ? readyItems[0].chapter_no : null
  const maxReadyCh = readyItems.length > 0 ? readyItems[readyItems.length - 1].chapter_no : null

  const selectedRangeReadyCount = useMemo(() => {
    return playlist.filter(p => p.has_audio && p.chapter_no >= exportRangeStart && p.chapter_no <= exportRangeEnd).length
  }, [playlist, exportRangeStart, exportRangeEnd])

  const currentChapterInfo = playlist.find(p => p.chapter_no === currentChapterNo)

  // =========================================================================
  // VIEW 1: NOVELS SELECTION GRID (BOOKSHELF)
  // =========================================================================
  if (activeView === 'list') {
    return (
      <div className="flex flex-col h-full overflow-hidden p-4 sm:p-6 gap-4 sm:gap-6">
        <div className="glass-panel p-4 sm:p-5 rounded-2xl flex items-center justify-between flex-shrink-0">
          <div>
            <h2 className="text-sm sm:text-base font-bold text-slate-100 flex items-center gap-2">
              <Headphones className="w-5 h-5 text-cyber-accent" /> Audio Studio — Sách Nói AI Cao Cấp
            </h2>
            <p className="text-xs text-cyber-muted mt-0.5">
              Chọn bộ truyện đã dịch để nghe audio từng chương, xuất file gộp hoặc tạo âm thanh tự động.
            </p>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {storeNovels.length === 0 ? (
            <div className="glass-panel p-12 text-center rounded-2xl flex flex-col items-center justify-center">
              <BookOpen className="w-12 h-12 text-slate-600 mb-3 opacity-40" />
              <p className="text-sm font-semibold text-slate-300">Chưa có bộ truyện nào trong thư viện</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {storeNovels.map((novel) => (
                <div
                  key={novel.id}
                  onClick={() => {
                    setSelectedNovelId(novel.id)
                    setActiveView('detail')
                  }}
                  className="glass-panel p-4 rounded-2xl border border-cyber-border/40 hover:border-cyber-accent/60 hover:shadow-xl hover:shadow-cyber-accent/10 transition-all cursor-pointer group flex flex-col justify-between"
                >
                  <div className="flex gap-3">
                    {novel.cover_url ? (
                      <img
                        src={novel.cover_url}
                        alt={novel.title}
                        className="w-16 h-22 object-cover rounded-xl border border-cyber-border/60 shadow-md flex-shrink-0"
                      />
                    ) : (
                      <div className="w-16 h-22 rounded-xl bg-slate-900 border border-cyber-border/60 flex items-center justify-center text-xl flex-shrink-0">
                        🎧
                      </div>
                    )}
                    <div className="flex-1 min-w-0">
                      <h3 className="font-bold text-sm text-slate-100 truncate group-hover:text-cyber-accent transition-colors">
                        {novel.title_rough || novel.title_raw || novel.title}
                      </h3>
                      <p className="text-[11px] text-cyber-muted truncate mt-0.5">Tác giả: {novel.author || 'N/A'}</p>
                      <span className="inline-block mt-2 text-[9px] font-bold px-2 py-0.5 rounded-full bg-slate-900 text-cyber-accent border border-cyber-accent/30">
                        {novel.completed_chapters || novel.total_chapters || 0} chương đã dịch
                      </span>
                    </div>
                  </div>

                  <button className="mt-4 w-full bg-cyber-accent/15 group-hover:bg-cyber-accent text-cyber-accent group-hover:text-cyber-bg font-bold py-2 rounded-xl text-xs border border-cyber-accent/30 transition-all flex items-center justify-center gap-1.5 shadow-sm">
                    <Headphones className="w-3.5 h-3.5" /> Mở Audio Studio
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    )
  }

  // =========================================================================
  // VIEW 2: COMPACT & POWERFUL AUDIO STUDIO (RESPONSIVE DESKTOP & MOBILE)
  // =========================================================================
  return (
    <div className="flex flex-col h-full overflow-hidden p-2.5 sm:p-4 gap-2.5 sm:gap-3">
      {/* Hidden HTML Audio Tag */}
      <audio
        ref={audioRef}
        onTimeUpdate={onTimeUpdate}
        onEnded={onEnded}
        onPause={() => setIsPlaying(false)}
        onPlay={() => setIsPlaying(true)}
      />

      {/* Top Header Bar */}
      <div className="glass-panel px-3 sm:px-4 py-2.5 rounded-xl flex items-center justify-between flex-shrink-0 flex-wrap gap-2 border border-cyber-border/40 shadow-sm">
        <div className="flex items-center gap-2.5 min-w-0 flex-1">
          <button
            onClick={() => setActiveView('list')}
            className="p-1.5 sm:px-2.5 sm:py-1.5 rounded-lg border border-cyber-border/60 hover:bg-slate-800 text-slate-300 hover:text-white transition-all flex items-center gap-1 text-xs font-bold flex-shrink-0"
            title="Quay lại Tủ Sách"
          >
            <ArrowLeft className="w-4 h-4 text-cyber-accent" />
            <span className="hidden sm:inline">Tủ Sách</span>
          </button>

          {/* Quick Novel Dropdown Selector */}
          <div className="relative min-w-0 flex-1 max-w-sm">
            <select
              value={selectedNovelId}
              onChange={(e) => setSelectedNovelId(Number(e.target.value))}
              className="w-full glass-input rounded-lg pl-3 pr-8 py-1.5 text-xs font-bold text-slate-100 appearance-none truncate cursor-pointer bg-slate-900 border-cyber-accent/40"
            >
              {storeNovels.map((n: any) => (
                <option key={n.id} value={n.id} className="bg-slate-900 text-slate-100">
                  📚 {n.title_rough || n.title_raw || n.title}
                </option>
              ))}
            </select>
            <ChevronDown className="w-3.5 h-3.5 text-cyber-accent absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>

          <div className="flex items-center gap-1.5 flex-shrink-0">
            <span className="text-[10px] sm:text-[11px] px-2 sm:px-2.5 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-semibold flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3 text-emerald-400" />
              <span>{readyCount}/{playlist.length} Audio</span>
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {readyCount > 0 && (
            <button
              onClick={handleDeleteAllAudio}
              className="px-2.5 py-1.5 rounded-lg border border-rose-500/40 bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 hover:text-rose-100 transition-all text-xs flex items-center gap-1.5 shadow-sm"
              title="Xóa toàn bộ audio và văn bản TTS của truyện này để tạo lại từ đầu"
            >
              <Trash2 className="w-3.5 h-3.5 text-rose-400" />
              <span className="hidden sm:inline">Xóa Tất Cả Audio</span>
            </button>
          )}

          <button
            onClick={() => fetchPlaylist(selectedNovelId)}
            disabled={loading}
            className="px-2.5 py-1.5 rounded-lg border border-cyber-border/60 hover:bg-slate-800 text-slate-300 hover:text-white transition-all text-xs flex items-center gap-1.5"
            title="Làm mới trạng thái playlist"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-cyber-accent ${loading ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">Làm mới</span>
          </button>
        </div>
      </div>

      {/* Quick Resume History Banner (If saved position exists) */}
      {savedHistory && savedHistory.chapterNo && (!currentChapterNo || currentChapterNo !== savedHistory.chapterNo || !isPlaying) && (
        <div className="glass-panel px-3 sm:px-4 py-2 rounded-xl flex items-center justify-between bg-gradient-to-r from-cyan-950/40 via-slate-900/60 to-slate-950/60 border border-cyber-accent/40 shadow-sm animate-fade-in flex-wrap gap-2">
          <div className="flex items-center gap-2.5 min-w-0">
            <span className="w-7 h-7 rounded-lg bg-cyber-accent/15 border border-cyber-accent/30 text-cyber-accent flex items-center justify-center text-xs flex-shrink-0">
              🎧
            </span>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-[10px] font-bold uppercase tracking-wider text-cyber-accent">Đang nghe dở</span>
                <span className="text-xs font-bold text-slate-100 truncate">Chương {savedHistory.chapterNo}: {savedHistory.chapterTitle}</span>
              </div>
              <p className="text-[10px] text-slate-400 font-mono mt-0.5">
                Vị trí: {formatSeconds(savedHistory.time)} / {formatSeconds(savedHistory.duration || 0)} 
                {savedHistory.totalParas ? ` • Đoạn ${(savedHistory.paraIdx || 0) + 1}/${savedHistory.totalParas}` : ''}
                {savedHistory.percent ? ` (${savedHistory.percent}%)` : ''}
              </p>
            </div>
          </div>
          <button
            onClick={() => handleResumeHistory(savedHistory)}
            className="px-3 py-1.5 bg-cyber-accent hover:bg-cyber-accent/80 text-cyber-bg font-bold rounded-lg text-xs flex items-center gap-1.5 shadow-md shadow-cyber-accent/20 transition-all flex-shrink-0 active:scale-95"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            <span>Tiếp tục nghe</span>
          </button>
        </div>
      )}

      {/* Mobile Tab Switcher (Visible only on mobile screens < 1024px) */}
      <div className="flex lg:hidden items-center justify-around bg-slate-950/60 p-1 rounded-xl border border-cyber-border/40 text-xs">
        <button
          onClick={() => setMobileTab('playlist')}
          className={`flex-1 py-1.5 rounded-lg font-bold transition-all flex items-center justify-center gap-1.5 ${
            mobileTab === 'playlist'
              ? 'bg-cyber-accent text-cyber-bg shadow-sm'
              : 'text-slate-400 hover:text-white'
          }`}
        >
          <Music className="w-3.5 h-3.5" /> Chương ({playlist.length})
        </button>
        <button
          onClick={() => setMobileTab('player')}
          className={`flex-1 py-1.5 rounded-lg font-bold transition-all flex items-center justify-center gap-1.5 ${
            mobileTab === 'player'
              ? 'bg-cyber-accent text-cyber-bg shadow-sm'
              : 'text-slate-400 hover:text-white'
          }`}
        >
          <Radio className="w-3.5 h-3.5" /> Trình Phát
        </button>
        <button
          onClick={() => setMobileTab('tools')}
          className={`flex-1 py-1.5 rounded-lg font-bold transition-all flex items-center justify-center gap-1.5 ${
            mobileTab === 'tools'
              ? 'bg-cyber-accent text-cyber-bg shadow-sm'
              : 'text-slate-400 hover:text-white'
          }`}
        >
          <Sliders className="w-3.5 h-3.5" /> Tạo & Ghép
        </button>
      </div>

      {/* Main Studio Area (2 Columns Desktop / Tabbed Mobile) */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-3 min-h-0">
        
        {/* ========================================================================= */}
        {/* LEFT COLUMN: CHAPTER PLAYLIST (7 COLS)                                    */}
        {/* ========================================================================= */}
        <div className={`lg:col-span-7 glass-panel rounded-2xl flex flex-col min-h-0 overflow-hidden border border-cyber-border/40 shadow-sm ${
          mobileTab !== 'playlist' ? 'hidden lg:flex' : 'flex'
        }`}>
          {/* Search & Filter Bar */}
          <div className="p-3 border-b border-cyber-border/30 flex items-center gap-2 flex-wrap bg-slate-950/40">
            <div className="relative flex-1 min-w-[140px]">
              <span className="absolute inset-y-0 left-0 pl-2.5 flex items-center pointer-events-none text-slate-500 text-xs">🔍</span>
              <input
                type="text"
                placeholder="Tìm số chương hoặc tiêu đề..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full glass-input rounded-lg pl-8 pr-2.5 py-1.5 text-xs"
              />
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setFilter('ALL')}
                className={`px-2.5 py-1 rounded-lg text-[11px] font-medium transition-all ${
                  filter === 'ALL'
                    ? 'bg-cyber-accent text-cyber-bg font-bold shadow-sm'
                    : 'text-slate-400 hover:bg-slate-800'
                }`}
              >
                Tất cả ({playlist.length})
              </button>
              <button
                onClick={() => setFilter('AUDIO_READY')}
                className={`px-2.5 py-1 rounded-lg text-[11px] font-medium transition-all ${
                  filter === 'AUDIO_READY'
                    ? 'bg-emerald-500 text-slate-950 font-bold shadow-sm'
                    : 'text-slate-400 hover:bg-slate-800'
                }`}
              >
                Đã có ({readyCount})
              </button>
              <button
                onClick={() => setFilter('AUDIO_PENDING')}
                className={`px-2.5 py-1 rounded-lg text-[11px] font-medium transition-all ${
                  filter === 'AUDIO_PENDING'
                    ? 'bg-amber-500 text-slate-950 font-bold shadow-sm'
                    : 'text-slate-400 hover:bg-slate-800'
                }`}
              >
                Chưa có ({Math.max(0, playlist.length - readyCount)})
              </button>
            </div>
          </div>

          {/* Virtualized Playlist */}
          <div ref={playlistParentRef} className="flex-1 overflow-y-auto p-2 min-h-0">
            {filteredPlaylist.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-500 flex flex-col items-center justify-center">
                {loading ? (
                  <div className="flex items-center gap-2 text-cyber-accent">
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Đang tải danh sách chương đã dịch...</span>
                  </div>
                ) : (
                  <span>Không tìm thấy chương nào phù hợp.</span>
                )}
              </div>
            ) : (
              <div
                style={{
                  height: `${rowVirtualizer.getTotalSize()}px`,
                  width: '100%',
                  position: 'relative',
                }}
              >
                {rowVirtualizer.getVirtualItems().map((virtualRow) => {
                  const item = filteredPlaylist[virtualRow.index]
                  if (!item) return null
                  const isCurrent = currentChapterNo === item.chapter_no

                  return (
                    <div
                      key={item.chapter_no}
                      style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        width: '100%',
                        height: `${virtualRow.size}px`,
                        transform: `translateY(${virtualRow.start}px)`,
                      }}
                      className="pb-1"
                    >
                      <div
                        onClick={() => item.has_audio && handlePlayChapter(item.chapter_no)}
                        className={`w-full h-full flex items-center justify-between px-3 py-1.5 rounded-xl text-xs border transition-all ${
                          isCurrent
                            ? 'border-cyber-accent bg-cyber-accent/15 text-cyber-accent shadow-sm ring-1 ring-cyber-accent/30'
                            : item.has_audio
                            ? 'border-cyber-border/30 bg-slate-900/40 hover:bg-slate-800/60 hover:border-emerald-500/40 text-slate-200 cursor-pointer'
                            : 'border-cyber-border/20 bg-slate-950/30 text-slate-400'
                        }`}
                      >
                        <div className="flex items-center gap-2.5 min-w-0 flex-1">
                          <span className={`w-6 h-6 rounded-lg flex items-center justify-center text-[10px] font-bold flex-shrink-0 ${
                            isCurrent
                              ? 'bg-cyber-accent text-cyber-bg'
                              : item.has_audio
                              ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                              : 'bg-slate-800 text-slate-500'
                          }`}>
                            {item.chapter_no}
                          </span>
                          <span className="truncate font-medium text-slate-200">
                            {item.title}
                          </span>
                        </div>

                        <div className="flex items-center gap-1.5 sm:gap-2 flex-shrink-0 ml-2">
                          {item.file_size && (
                            <span className="text-[10px] text-slate-400 font-mono hidden sm:inline">{item.file_size}</span>
                          )}
                          {item.has_audio ? (
                            <div className="flex items-center gap-1 sm:gap-1.5">
                              {/* PLAY BUTTON */}
                              <button
                                onClick={(e) => {
                                  e.stopPropagation()
                                  handlePlayChapter(item.chapter_no)
                                }}
                                className={`p-1.5 rounded-lg transition-all ${
                                  isCurrent && isPlaying
                                    ? 'bg-cyber-accent text-cyber-bg shadow-sm'
                                    : 'hover:bg-cyber-accent/20 text-cyber-accent border border-cyber-accent/30'
                                }`}
                                title={isCurrent && isPlaying ? "Tạm dừng" : "Nghe chương này"}
                              >
                                {isCurrent && isPlaying ? (
                                  <Pause className="w-3.5 h-3.5" />
                                ) : (
                                  <Play className="w-3.5 h-3.5 fill-current" />
                                )}
                              </button>

                              {/* DOWNLOAD SINGLE CHAPTER MP3 BUTTON */}
                              <a
                                href={`/api/novels/${selectedNovelId}/audio/stream_chapter/${item.chapter_no}`}
                                download={`Chuong_${item.chapter_no}.mp3`}
                                onClick={(e) => e.stopPropagation()}
                                className="p-1.5 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-400 hover:text-emerald-200 transition-all flex items-center justify-center shadow-sm"
                                title={`Tải riêng tệp MP3 Chương ${item.chapter_no} về máy`}
                              >
                                <Download className="w-3.5 h-3.5" />
                              </a>

                              {/* DOWNLOAD SINGLE CHAPTER JSON SUBTITLE BUTTON */}
                              <a
                                href={`/api/novels/${selectedNovelId}/audio/json/${item.chapter_no}`}
                                download={`chap_${item.chapter_no}.json`}
                                onClick={(e) => e.stopPropagation()}
                                className="p-1.5 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/30 border border-cyan-500/40 text-cyan-400 hover:text-cyan-200 transition-all flex items-center justify-center shadow-sm"
                                title={`Tải file JSON Subtitle Karaoke Chương ${item.chapter_no}`}
                              >
                                <FileText className="w-3.5 h-3.5" />
                              </a>

                              {/* DELETE SINGLE CHAPTER AUDIO BUTTON (TO REGENERATE) */}
                              <button
                                onClick={(e) => {
                                  e.stopPropagation()
                                  handleDeleteSingleChapterAudio(item.chapter_no)
                                }}
                                className="p-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/30 border border-rose-500/30 text-rose-400 hover:text-rose-200 transition-all flex items-center justify-center shadow-sm"
                                title={`Xóa Audio Chương ${item.chapter_no} để tạo lại từ bản dịch mới`}
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          ) : (
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                handleStartBatchTTS(item.chapter_no, item.chapter_no)
                              }}
                              className="px-2.5 py-1 rounded-lg bg-slate-900 hover:bg-cyber-accent/20 text-slate-400 hover:text-cyber-accent border border-slate-700/60 hover:border-cyber-accent/50 text-[10px] font-medium transition-all"
                              title="Tạo audio riêng cho chương này"
                            >
                              + Tạo audio
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>

        {/* ========================================================================= */}
        {/* RIGHT COLUMN: AUDIO PLAYER & BATCH CONTROL (5 COLS)                       */}
        {/* ========================================================================= */}
        <div className={`lg:col-span-5 flex flex-col gap-3 min-h-0 overflow-y-auto ${
          mobileTab === 'playlist' ? 'hidden lg:flex' : 'flex'
        }`}>
          {/* 1. COMPACT BEAUTIFUL PLAYER CARD */}
          <div className={`glass-panel p-4 rounded-2xl border border-cyber-border/40 flex flex-col gap-3 bg-slate-950/50 shadow-md ${
            mobileTab === 'tools' ? 'hidden lg:flex' : 'flex'
          }`}>
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                <Headphones className="w-4 h-4 text-cyber-accent" /> Trình Phát Sách Nói
              </span>
              <label className="flex items-center gap-1.5 text-[10px] text-slate-400 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={autoNext}
                  onChange={(e) => setAutoNext(e.target.checked)}
                  className="rounded border-slate-700 text-cyber-accent focus:ring-0"
                />
                Tự chuyển chương
              </label>
            </div>

            {currentChapterInfo ? (
              <div className="flex flex-col gap-2.5">
                <div className="min-w-0 bg-slate-900/60 p-2.5 rounded-xl border border-cyber-border/30">
                  <span className="text-[10px] font-bold text-cyber-accent uppercase tracking-wider block">
                    Đang phát • Chương {currentChapterInfo.chapter_no}
                  </span>
                  <h4 className="text-xs font-bold text-slate-100 truncate mt-0.5">
                    {currentChapterInfo.title}
                  </h4>
                  <p className="text-[10px] text-slate-400 mt-0.5">Dung lượng: {currentChapterInfo.file_size || 'N/A'}</p>
                </div>

                {/* Seek Bar */}
                <div className="flex flex-col gap-1">
                  <input
                    type="range"
                    min={0}
                    max={duration || 100}
                    value={currentTime}
                    onChange={handleSeek}
                    className="w-full accent-cyber-accent h-1.5 bg-slate-800 rounded-lg cursor-pointer"
                  />
                  <div className="flex justify-between text-[10px] text-slate-400 font-mono">
                    <span>{formatSeconds(currentTime)}</span>
                    <span>{formatSeconds(duration)}</span>
                  </div>
                </div>

                {/* Control Buttons & Actions */}
                <div className="flex flex-col gap-2.5 pt-1">
                  <div className="flex items-center justify-between gap-2">
                    {/* Volume Slider */}
                    <div className="flex items-center gap-1.5">
                      <button
                        onClick={toggleMute}
                        className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                        title={isMuted ? "Bật âm lượng" : "Tắt âm"}
                      >
                        {isMuted ? <VolumeX className="w-3.5 h-3.5" /> : <Volume2 className="w-3.5 h-3.5" />}
                      </button>
                      <input
                        type="range"
                        min={0}
                        max={1}
                        step={0.05}
                        value={isMuted ? 0 : volume}
                        onChange={handleVolumeChange}
                        className="w-14 sm:w-16 accent-cyber-accent h-1 bg-slate-800 rounded-lg"
                      />
                    </div>

                    {/* Main Playback & Skip Controls */}
                    <div className="flex items-center gap-1 sm:gap-2">
                      {/* Prev Chapter */}
                      <button
                        onClick={handlePrevChapter}
                        className="p-2 rounded-xl hover:bg-slate-800 text-slate-300 hover:text-white transition-colors"
                        title="Chương trước"
                      >
                        <SkipBack className="w-4 h-4" />
                      </button>

                      {/* Tua lùi 10s */}
                      <button
                        onClick={() => handleSkipBackward(10)}
                        className="p-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700/60 text-slate-300 hover:text-cyber-accent transition-all flex items-center gap-0.5 text-[10px] font-bold shadow-sm"
                        title="Tua lùi 10 giây"
                      >
                        <RotateCcw className="w-3.5 h-3.5 text-cyber-accent" />
                        <span>-10s</span>
                      </button>

                      {/* Play/Pause Main Button */}
                      <button
                        onClick={() => handlePlayChapter(currentChapterInfo.chapter_no)}
                        className="w-10 h-10 rounded-full bg-cyber-accent hover:bg-cyber-accent/80 text-cyber-bg flex items-center justify-center shadow-lg shadow-cyber-accent/25 transition-all active:scale-95 flex-shrink-0"
                      >
                        {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 fill-current ml-0.5" />}
                      </button>

                      {/* Tua tới 10s */}
                      <button
                        onClick={() => handleSkipForward(10)}
                        className="p-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700/60 text-slate-300 hover:text-cyber-accent transition-all flex items-center gap-0.5 text-[10px] font-bold shadow-sm"
                        title="Tua tới 10 giây"
                      >
                        <span>+10s</span>
                        <RotateCw className="w-3.5 h-3.5 text-cyber-accent" />
                      </button>

                      {/* Next Chapter */}
                      <button
                        onClick={handleNextChapter}
                        className="p-2 rounded-xl hover:bg-slate-800 text-slate-300 hover:text-white transition-colors"
                        title="Chương tiếp theo"
                      >
                        <SkipForward className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                  {/* Playback Speed Bar (x0.75, x1, x1.25, x1.5, x1.75, x2, x2.5, x3, x3.5, x4) */}
                  <div className="flex items-center justify-between gap-1 p-2 rounded-xl bg-slate-900/60 border border-cyber-border/30 overflow-x-auto text-[10px]">
                    <span className="text-slate-400 font-bold flex items-center gap-1 pl-1 flex-shrink-0">
                      <Gauge className="w-3 h-3 text-cyber-accent" /> Tốc độ:
                    </span>
                    <div className="flex items-center gap-1 flex-wrap">
                      {[0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0, 3.5, 4.0].map((rate) => (
                        <button
                          key={rate}
                          onClick={() => handleSpeedChange(rate)}
                          className={`px-2 py-1 rounded-lg font-mono font-bold transition-all ${
                            playbackRate === rate
                              ? 'bg-cyber-accent text-cyber-bg shadow-sm'
                              : 'text-slate-400 hover:text-white hover:bg-slate-800'
                          }`}
                        >
                          {rate}x
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="py-6 text-center text-xs text-slate-500 flex flex-col items-center justify-center gap-2">
                <Headphones className="w-8 h-8 text-slate-700 opacity-40" />
                <span>Chọn một chương có audio bên trái để bắt đầu nghe.</span>
              </div>
            )}
          </div>

          {/* 2. REALTIME JOB PROGRESS BANNER (IF RUNNING) */}
          {(isGenerating || (jobStatus && jobStatus.is_running)) && (
            <div className="glass-panel p-3.5 rounded-2xl border border-cyber-accent/50 bg-cyber-accent/10 flex flex-col gap-2.5 shadow-lg shadow-cyber-accent/10 animate-fade-in">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-cyber-accent flex items-center gap-1.5">
                  <Sparkles className="w-4 h-4 animate-spin text-cyber-accent" /> {jobStatus?.msg || 'Đang tạo Audio...'}
                </span>
                <button
                  onClick={handleCancelTTS}
                  className="px-2.5 py-1 rounded-lg bg-rose-500/20 hover:bg-rose-500 border border-rose-500/40 text-rose-300 hover:text-white text-[10px] font-bold transition-all shadow-sm"
                >
                  Hủy tiến trình
                </button>
              </div>

              {/* Progress Bar with Glowing Animation */}
              <div className="w-full bg-slate-900/80 rounded-full h-2.5 overflow-hidden border border-cyber-border/40 p-0.5">
                <div
                  className="bg-gradient-to-r from-cyber-accent via-emerald-400 to-cyber-accent h-full transition-all duration-300 rounded-full shadow-sm"
                  style={{ width: `${Math.max(2, jobStatus?.progress_pct || 0)}%` }}
                />
              </div>

              {/* Progress Stats */}
              <div className="flex items-center justify-between text-[11px] text-slate-300 font-medium">
                <span className="flex items-center gap-1">
                  <span className="text-cyber-accent font-bold font-mono text-xs">{jobStatus?.progress_pct || 0}%</span>
                  {jobStatus?.total_subchunks ? (
                    <span className="text-slate-400 font-mono text-[10px]">
                      ({jobStatus?.done_subchunks || 0}/{jobStatus?.total_subchunks} đoạn)
                    </span>
                  ) : null}
                </span>
                <span className="text-slate-400 text-[10px]">
                  ETA: <strong className="text-slate-200">{jobStatus?.eta_display || 'Đang tính...'}</strong>
                </span>
              </div>

              {/* Live Chunk Snippet */}
              {jobStatus?.last_chunk_log && (
                <div className="px-2 py-1 rounded-lg bg-slate-950/70 border border-cyber-border/30 text-[10px] text-slate-400 font-mono truncate">
                  ⚡ {jobStatus.last_chunk_log}
                </div>
              )}
            </div>
          )}

          {/* 3. BATCH TTS GENERATION CARD */}
          <div className={`glass-panel p-4 rounded-2xl border border-cyber-border/40 flex flex-col gap-3 bg-slate-950/50 shadow-md ${
            mobileTab === 'player' ? 'hidden lg:flex' : 'flex'
          }`}>
            <span className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
              <Zap className="w-4 h-4 text-cyber-accent" /> Tạo Audio TTS Hàng Loạt
            </span>

            {/* TTS Range Selection */}
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <label className="text-[10px] text-slate-400 block mb-1 font-medium">Từ chương:</label>
                <input
                  type="number"
                  min={1}
                  max={playlist.length || 1}
                  value={ttsRangeStart}
                  onChange={(e) => setTtsRangeStart(Math.max(1, parseInt(e.target.value) || 1))}
                  className="w-full glass-input rounded-xl px-2.5 py-1.5 text-xs"
                />
              </div>
              <div>
                <label className="text-[10px] text-slate-400 block mb-1 font-medium">Đến chương:</label>
                <input
                  type="number"
                  min={1}
                  max={playlist.length || 1}
                  value={ttsRangeEnd}
                  onChange={(e) => setTtsRangeEnd(Math.max(1, parseInt(e.target.value) || 1))}
                  className="w-full glass-input rounded-xl px-2.5 py-1.5 text-xs"
                />
              </div>
            </div>

            {/* Voice & Workers Config */}
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <label className="text-[10px] text-slate-400 block mb-1 font-medium">Giọng đọc:</label>
                <select
                  value={voiceProfile}
                  onChange={(e) => setVoiceProfile(e.target.value)}
                  className="w-full glass-input rounded-xl px-2 py-1.5 text-xs"
                >
                  <option value="default">Hoài My (Nữ)</option>
                  <option value="nam">Nam Minh (Nam)</option>
                </select>
              </div>
              <div>
                <label className="text-[10px] text-slate-400 block mb-1 font-medium">Workers:</label>
                <select
                  value={parallelWorkers}
                  onChange={(e) => {
                    const v = Number(e.target.value)
                    setParallelWorkers(v)
                    localStorage.setItem('tts_parallel_workers', String(v))
                  }}
                  className="w-full glass-input rounded-xl px-2 py-1.5 text-xs"
                >
                  <option value={4}>4 luồng</option>
                  <option value={8}>8 luồng</option>
                  <option value={12}>12 luồng</option>
                  <option value={16}>16 luồng</option>
                  <option value={24}>24 luồng</option>
                  <option value={32}>32 luồng (Siêu tốc)</option>
                  <option value={48}>48 luồng (Cực đại)</option>
                </select>
              </div>
            </div>

            {/* Start Batch TTS Action */}
            <button
              onClick={() => handleStartBatchTTS()}
              disabled={isGenerating}
              className="w-full py-2.5 rounded-xl bg-cyber-accent/15 hover:bg-cyber-accent text-cyber-accent hover:text-cyber-bg font-bold text-xs border border-cyber-accent/30 transition-all flex items-center justify-center gap-1.5 disabled:opacity-50 shadow-sm mt-1"
            >
              <Zap className="w-3.5 h-3.5" /> Tạo Audio Lô ({ttsRangeStart} → {ttsRangeEnd})
            </button>
          </div>

          {/* 4. EXPORT & DOWNLOAD (MP3 & TIMELINE JSON) CARD - TÁCH BIỆT HOÀN TOÀN */}
          <div className={`glass-panel p-4 rounded-2xl border border-cyber-border/40 flex flex-col gap-3 bg-slate-950/50 shadow-md ${
            mobileTab === 'player' ? 'hidden lg:flex' : 'flex'
          }`}>
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                <Layers className="w-4 h-4 text-cyber-purple" /> Xuất & Tải File Gộp (MP3 / JSON)
              </span>
              {minReadyCh !== null && maxReadyCh !== null && (
                <button
                  type="button"
                  onClick={() => {
                    setExportRangeStart(minReadyCh)
                    setExportRangeEnd(maxReadyCh)
                  }}
                  className="text-[10px] px-2 py-0.5 rounded-lg bg-cyber-purple/20 text-cyber-purple hover:bg-cyber-purple/30 font-medium transition-all"
                  title={`Tự động chọn khoảng chương đã có Audio: ${minReadyCh} → ${maxReadyCh}`}
                >
                  🎯 Chọn nhanh {minReadyCh} → {maxReadyCh}
                </button>
              )}
            </div>

            {/* 🎯 TỰ ĐỘNG CHIA TẬP 10h - <12h @ SPEED */}
            <div className="p-3 rounded-xl bg-cyber-purple/10 border border-cyber-purple/30 flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-cyber-purple flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-cyber-purple" />
                  Chia Tập Chuẩn 10h - 12h (Tốc độ {exportSpeed}x)
                </span>
                <button
                  type="button"
                  onClick={() => selectedNovelId && fetchAutoBundles(selectedNovelId, exportSpeed)}
                  disabled={loadingBundles}
                  className="text-[10px] px-2 py-0.5 rounded-lg bg-cyber-purple/20 text-cyber-purple hover:bg-cyber-purple/30 font-medium transition-all flex items-center gap-1"
                >
                  <RefreshCw className={`w-3 h-3 ${loadingBundles ? 'animate-spin' : ''}`} />
                  <span>Tính lại</span>
                </button>
              </div>
              <p className="text-[10px] text-slate-400">
                Hệ thống tự động gom các chương thành từng tập dài 10h đến dưới 12h (chuẩn YouTube/nghe trọn gói).
              </p>

              {autoBundles.length > 0 ? (
                <div className="flex flex-col gap-1.5 max-h-56 overflow-y-auto pr-1">
                  {autoBundles.map((b: any) => (
                    <div
                      key={b.part}
                      className="p-2 rounded-lg bg-slate-900/80 border border-cyber-border/40 hover:border-cyber-purple/50 transition-all flex items-center justify-between gap-2 text-xs"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span className="font-bold text-slate-100">{b.title}</span>
                          <span className="text-[10px] px-1.5 py-0.2 rounded bg-cyber-accent/20 text-cyber-accent font-mono font-bold">
                            ⏱️ {b.duration_formatted}
                          </span>
                        </div>
                        <p className="text-[10px] text-slate-400 mt-0.5">
                          {b.chapter_count} chương ({b.duration_hours} giờ @ {b.speed}x)
                        </p>
                      </div>

                      <div className="flex items-center gap-1.5 flex-shrink-0">
                        {b.is_merged ? (
                          <>
                            <button
                              type="button"
                              onClick={() => handleDownloadBoth(b.download_url, b.filename, b.json_download_url, b.json_filename)}
                              className="px-2.5 py-1 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold rounded-lg text-[11px] transition-all flex items-center gap-1 shadow-sm"
                              title={`Tải CẢ HAI tệp: File MP3 (${b.file_size}) + File JSON timeline phụ đề`}
                            >
                              <Download className="w-3 h-3" />
                              <span>Tải Cả 2 ({b.file_size})</span>
                            </button>
                            <a
                              href={b.download_url}
                              download={b.filename}
                              className="px-1.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium rounded-lg text-[10px] transition-all"
                              title="Chỉ tải riêng file MP3 này"
                            >
                              MP3
                            </a>
                            <a
                              href={b.json_download_url}
                              download={b.json_filename}
                              className="px-1.5 py-1 bg-cyan-950/60 hover:bg-cyan-900/60 text-cyan-300 border border-cyan-500/30 font-medium rounded-lg text-[10px] transition-all"
                              title="Chỉ tải riêng file JSON timeline phụ đề của tập này"
                            >
                              JSON
                            </a>
                          </>
                        ) : (
                          <>
                            <button
                              type="button"
                              onClick={() => handleMergeBundle(b)}
                              disabled={isMerging}
                              className="px-2.5 py-1 bg-cyber-purple hover:bg-cyber-purple/80 text-white font-bold rounded-lg text-[11px] transition-all flex items-center gap-1 shadow-sm disabled:opacity-50"
                              title="Ghép các chương tập này và TỰ ĐỘNG TẢI CẢ HAI: File MP3 + File JSON timeline"
                            >
                              <Layers className="w-3 h-3" />
                              <span>Ghép & Tải Cả 2</span>
                            </button>
                            <a
                              href={b.json_download_url}
                              download={b.json_filename}
                              className="px-1.5 py-1 bg-cyan-950/60 hover:bg-cyan-900/60 text-cyan-300 border border-cyan-500/30 font-medium rounded-lg text-[10px] transition-all"
                              title="Tải trước file JSON timeline phụ đề của tập này"
                            >
                              JSON
                            </a>
                          </>
                        )}
                        <button
                          type="button"
                          onClick={() => {
                            setExportRangeStart(b.start_chapter)
                            setExportRangeEnd(b.end_chapter)
                          }}
                          className="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-[10px] transition-all"
                          title="Điền khoảng chương này vào khung tự chọn bên dưới"
                        >
                          Chọn
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-[10px] text-slate-500 py-1 text-center">
                  {loadingBundles ? 'Đang tính toán các tập...' : 'Chưa có đủ audio để gom tập 10-12 tiếng.'}
                </div>
              )}
            </div>

            {/* Export Range Selection (Tự chọn thủ công) */}
            <div className="text-[11px] font-bold text-slate-300 pt-1 border-t border-cyber-border/30">
              Hoặc chọn khoảng chương thủ công:
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <label className="text-[10px] text-slate-400 block mb-1 font-medium">Từ chương:</label>
                <input
                  type="number"
                  min={1}
                  max={playlist.length || 1}
                  value={exportRangeStart}
                  onChange={(e) => setExportRangeStart(Math.max(1, parseInt(e.target.value) || 1))}
                  className="w-full glass-input rounded-xl px-2.5 py-1.5 text-xs"
                />
              </div>
              <div>
                <label className="text-[10px] text-slate-400 block mb-1 font-medium">Đến chương:</label>
                <input
                  type="number"
                  min={1}
                  max={playlist.length || 1}
                  value={exportRangeEnd}
                  onChange={(e) => setExportRangeEnd(Math.max(1, parseInt(e.target.value) || 1))}
                  className="w-full glass-input rounded-xl px-2.5 py-1.5 text-xs"
                />
              </div>
            </div>

            {/* Range Status Info */}
            <div className="text-[11px] flex items-center justify-between px-1">
              <span className={selectedRangeReadyCount > 0 ? 'text-emerald-400 font-medium' : 'text-amber-400 font-medium'}>
                {selectedRangeReadyCount > 0 
                  ? `✅ Có sẵn ${selectedRangeReadyCount}/${Math.max(1, exportRangeEnd - exportRangeStart + 1)} chương MP3`
                  : `⚠️ Khoảng ${exportRangeStart} → ${exportRangeEnd} chưa có Audio nào`}
              </span>
              <span className="text-[10px] text-slate-400">
                (Tổng có: {readyCount} ch)
              </span>
            </div>

            {/* Export Speed Selector */}
            <div className="flex items-center justify-between gap-2 p-2 rounded-xl bg-slate-900/60 border border-cyber-border/40 text-xs">
              <span className="text-[11px] font-bold text-slate-300 flex items-center gap-1">
                ⚡ Tốc độ xuất:
              </span>
              <div className="flex items-center gap-1 flex-wrap justify-end">
                {[1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0].map((spd) => (
                  <button
                    key={spd}
                    type="button"
                    onClick={() => setExportSpeed(spd)}
                    className={`px-2 py-0.5 rounded-lg text-[10px] font-bold transition-all ${
                      exportSpeed === spd
                        ? 'bg-cyber-accent text-cyber-bg shadow-sm'
                        : 'bg-slate-800/80 text-slate-400 hover:text-slate-200 hover:bg-slate-700'
                    }`}
                  >
                    {spd === 1.0 ? '1.0x (Gốc)' : `${spd}x`}
                  </button>
                ))}
              </div>
            </div>

            {/* Export Action Buttons */}
            <div className="grid grid-cols-2 gap-2 pt-1">
              <button
                onClick={handleFastMerge}
                disabled={isMerging}
                className="py-2.5 px-2 rounded-xl bg-cyber-purple/15 hover:bg-cyber-purple text-cyber-purple hover:text-white font-bold text-xs border border-cyber-purple/30 transition-all flex items-center justify-center gap-1.5 disabled:opacity-50 shadow-sm truncate"
                title={`Ghép các file MP3 từ chương ${exportRangeStart} đến ${exportRangeEnd} và tự động tải CẢ HAI file (MP3 + JSON Timeline)`}
              >
                {isMerging ? (
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Download className="w-3.5 h-3.5" />
                )}
                <span>{isMerging ? 'Đang ghép...' : `⚡ Ghép & Tải Cả 2 (${exportSpeed}x)`}</span>
              </button>

              <a
                href={`/api/novels/${selectedNovelId}/audio/export_timeline_json?start_chapter=${exportRangeStart}&end_chapter=${exportRangeEnd}&speed=${exportSpeed}`}
                download={`Timeline_Ch${exportRangeStart}_to_Ch${exportRangeEnd}${exportSpeed !== 1.0 ? `_${exportSpeed}x` : ''}.json`}
                className="py-2.5 px-2 rounded-xl bg-cyan-500/15 hover:bg-cyan-500 text-cyan-300 hover:text-slate-950 font-bold text-xs border border-cyan-500/30 transition-all flex items-center justify-center gap-1.5 shadow-sm truncate"
                title={`Chỉ xuất riêng file JSON timeline phụ đề karaoke từ chương ${exportRangeStart} đến ${exportRangeEnd} (Tốc độ ${exportSpeed}x)`}
              >
                <FileText className="w-3.5 h-3.5" />
                <span>Xuất JSON Chuỗi ({exportSpeed}x)</span>
              </a>
            </div>

            {/* Merge Result Download Banner */}
            {mergeResult && (
              <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs flex items-center justify-between mt-1 flex-wrap gap-2">
                <div>
                  <p className="font-bold">{mergeResult.message}</p>
                  <p className="text-[10px] text-slate-400">Dung lượng: {mergeResult.file_size} • Độ dài: {mergeResult.duration || 'N/A'}</p>
                </div>
                <div className="flex items-center gap-1.5 flex-wrap">
                  <button
                    type="button"
                    onClick={() => handleDownloadBoth(
                      mergeResult.download_url,
                      mergeResult.filename,
                      mergeResult.json_download_url,
                      mergeResult.json_filename
                    )}
                    className="px-3 py-1.5 bg-emerald-500 text-slate-950 font-bold rounded-lg text-xs hover:bg-emerald-400 transition-all flex items-center gap-1 shadow-sm"
                    title="Tải CẢ HAI tệp: File MP3 gộp + File JSON timeline phụ đề"
                  >
                    <Download className="w-3.5 h-3.5" /> Tải Cả 2 (MP3 + JSON)
                  </button>
                  <a
                    href={mergeResult.download_url}
                    download={mergeResult.filename}
                    className="px-2 py-1.5 bg-slate-800 text-slate-300 hover:text-white font-medium rounded-lg text-[11px] transition-all"
                    title="Chỉ tải file MP3"
                  >
                    MP3
                  </a>
                  <a
                    href={mergeResult.json_download_url}
                    download={mergeResult.json_filename}
                    className="px-2 py-1.5 bg-cyan-950/60 text-cyan-300 hover:text-cyan-200 border border-cyan-500/30 font-medium rounded-lg text-[11px] transition-all"
                    title="Chỉ tải file JSON timeline phụ đề"
                  >
                    JSON
                  </a>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
