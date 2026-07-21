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
  RefreshCw,
  CheckCircle,
  Clock,
  Sparkles,
  Layers,
  Music,
  Zap
} from 'lucide-react'

interface NovelOption {
  id: number
  title: string
  author?: string
  cover_url?: string
}

interface VolumeInfo {
  volume_no: number
  start_chapter: number
  end_chapter: number
  chapter_count: number
  word_count: number
  estimated_hours: number
  is_created: boolean
  filename?: string
  size_mb?: number
  download_url?: string
}

interface AudioStudioProps {
  novels: NovelOption[]
}

export default function AudioStudio({ novels }: AudioStudioProps) {
  const [selectedNovelId, setSelectedNovelId] = useState<number>(novels[0]?.id || 0)
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

  // Audio Player State
  const [currentPlaying, setCurrentPlaying] = useState<VolumeInfo | null>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [volume, setVolume] = useState(1.0)
  const [isMuted, setIsMuted] = useState(false)
  const [playbackRate, setPlaybackRate] = useState(1.75)

  const audioRef = useRef<HTMLAudioElement | null>(null)

  // Auto select first novel if none selected
  useEffect(() => {
    if (!selectedNovelId && novels.length > 0) {
      setSelectedNovelId(novels[0].id)
    }
  }, [novels])

  // Fetch volume list when selected novel changes
  const fetchVolumes = async (novelId: number) => {
    if (!novelId) return
    setLoading(true)
    try {
      const res = await fetch(`/api/novels/${novelId}/audio/volumes`)
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

  useEffect(() => {
    if (selectedNovelId) {
      fetchVolumes(selectedNovelId)
      checkJobStatus(selectedNovelId)
    }
  }, [selectedNovelId])

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
        }
      }
    } catch (e) {
      console.error(e)
    }
  }

  const pollJob = (novelId: number) => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/novels/${novelId}/audio/status`)
        if (res.ok) {
          const status = await res.json()
          setJobStatus(status)
          fetchVolumes(novelId) // Cập nhật ngay danh sách tập đã tạo lên UI theo thời gian thực
          if (!status.is_running) {
            setIsGenerating(false)
            clearInterval(interval)
          }
        }
      } catch (e) {
        setIsGenerating(false)
        clearInterval(interval)
      }
    }, 3000)
  }

  // Trigger Bulk Audio Generation
  const handleGenerateAll = async () => {
    if (!selectedNovelId) return
    setIsGenerating(true)
    try {
      const res = await fetch(`/api/novels/${selectedNovelId}/audio/generate`, { method: 'POST' })
      const data = await res.json()
      alert(data.message)
      pollJob(selectedNovelId)
    } catch (e) {
      console.error(e)
      setIsGenerating(false)
    }
  }

  // Trigger Targeted Volume Generation
  const handleGenerateSingleVolume = async (volNo: number) => {
    if (!selectedNovelId) return
    setIsGenerating(true)
    try {
      const res = await fetch(`/api/novels/${selectedNovelId}/audio/generate_volume/${volNo}`, { method: 'POST' })
      const data = await res.json()
      alert(data.message)
      pollJob(selectedNovelId)
    } catch (e) {
      console.error(e)
      setIsGenerating(false)
    }
  }

  // Audio Controls Handlers
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

  const filteredVolumes = (volumeData?.volumes || []).filter(v => {
    if (filter === 'CREATED') return v.is_created
    if (filter === 'UNCREATED') return !v.is_created
    return true
  })

  return (
    <div className="flex flex-col h-full bg-slate-950 text-slate-100 overflow-hidden">
      {/* Hidden HTML Audio Element */}
      <audio
        ref={audioRef}
        onTimeUpdate={() => setCurrentTime(audioRef.current?.currentTime || 0)}
        onLoadedMetadata={() => setDuration(audioRef.current?.duration || 0)}
        onEnded={() => setIsPlaying(false)}
      />

      {/* HEADER SECTION */}
      <div className="border-b border-cyber-border/40 px-6 py-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-4 bg-slate-900/40">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400">
            <Headphones className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-slate-100 flex items-center gap-2">
              🎧 Audio Studio — Trình Phát Truyện Cao Cấp
            </h1>
            <p className="text-xs text-slate-400">
              Giọng nam trầm ấm Nam Minh (<code className="text-emerald-400">vi-VN-NamMinhNeural</code>) / Hoài My — Siêu tốc 25 luồng song song (gấp 20x thực tế)
            </p>
          </div>
        </div>

        {/* Novel Selector & Bulk Generate Button */}
        <div className="flex items-center gap-3 flex-wrap">
          <select
            value={selectedNovelId}
            onChange={(e) => setSelectedNovelId(Number(e.target.value))}
            className="bg-slate-900 border border-cyber-border rounded-xl px-3 py-2 text-xs font-semibold text-slate-200 focus:outline-none focus:border-emerald-500/60"
          >
            {novels.map(n => (
              <option key={n.id} value={n.id}>📖 {n.title}</option>
            ))}
          </select>

          <button
            onClick={handleGenerateAll}
            disabled={isGenerating}
            className="bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold px-4 py-2 rounded-xl text-xs flex items-center gap-2 transition-all shadow-lg disabled:opacity-40"
          >
            {isGenerating ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
            🚀 Tạo Tất Cả Các Tập Audio
          </button>
        </div>
      </div>

      {/* AUDIO STATUS BANNER IF GENERATING */}
      {jobStatus?.is_running && (
        <div className="mx-6 mt-4 p-3 rounded-xl bg-emerald-950/40 border border-emerald-500/40 text-emerald-300 text-xs flex items-center justify-between animate-pulse">
          <div className="flex items-center gap-2">
            <RefreshCw className="w-4 h-4 animate-spin" />
            <span className="font-semibold">{jobStatus.msg}</span>
          </div>
          <span className="font-bold text-emerald-400">{jobStatus.progress_pct}%</span>
        </div>
      )}

      {/* ADVANCED CUSTOM AUDIO PLAYER PANEL */}
      <div className="mx-6 mt-4 p-5 rounded-2xl border border-emerald-500/30 bg-gradient-to-r from-slate-900/90 to-emerald-950/40 shadow-2xl flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
              <Music className="w-6 h-6 animate-pulse" />
            </div>
            <div>
              <p className="text-[11px] font-bold uppercase tracking-wider text-emerald-400">Đang Phát Tập Audio</p>
              <h3 className="text-sm font-bold text-slate-100 truncate max-w-md">
                {currentPlaying ? currentPlaying.filename : "Chưa chọn Tập Audio nào (Bấm '▶ Nghe Tập Này' bên dưới)"}
              </h3>
            </div>
          </div>

          {/* Speed Selector */}
          <div className="flex items-center gap-1.5 bg-slate-950/80 p-1 rounded-xl border border-cyber-border">
            <span className="text-[10px] text-slate-400 font-bold px-2">Tốc độ:</span>
            {[1.0, 1.25, 1.5, 1.75, 2.0].map(rate => (
              <button
                key={rate}
                onClick={() => handleRateChange(rate)}
                className={`text-[10px] font-bold px-2 py-1 rounded-lg transition-all ${
                  playbackRate === rate
                    ? 'bg-emerald-500 text-slate-950 shadow-md'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {rate}x
              </button>
            ))}
          </div>
        </div>

        {/* SEEKBAR & TIMESTAMPS */}
        <div className="flex items-center gap-3">
          <span className="text-xs font-mono text-slate-400 w-14 text-right">{formatTime(currentTime)}</span>
          <input
            type="range"
            min={0}
            max={duration || 100}
            value={currentTime}
            onChange={handleSeek}
            className="flex-1 accent-emerald-500 cursor-pointer h-2 bg-slate-800 rounded-lg"
          />
          <span className="text-xs font-mono text-slate-400 w-14">{formatTime(duration)}</span>
        </div>

        {/* MAIN CONTROLS: REWIND / PLAY / FORWARD / VOLUME */}
        <div className="flex items-center justify-between pt-1">
          <div className="flex items-center gap-3">
            <button
              onClick={() => skipTime(-10)}
              className="p-2 rounded-xl bg-slate-800/60 border border-cyber-border hover:bg-slate-800 text-slate-300 transition-all"
              title="Tua lùi 10 giây"
            >
              <RotateCcw className="w-4 h-4" />
            </button>

            <button
              onClick={togglePlay}
              disabled={!currentPlaying}
              className="w-11 h-11 rounded-full bg-emerald-500 hover:bg-emerald-400 text-slate-950 flex items-center justify-center font-bold shadow-lg shadow-emerald-500/20 transition-all disabled:opacity-40"
            >
              {isPlaying ? <Pause className="w-5 h-5 fill-slate-950" /> : <Play className="w-5 h-5 fill-slate-950 ml-0.5" />}
            </button>

            <button
              onClick={() => skipTime(10)}
              className="p-2 rounded-xl bg-slate-800/60 border border-cyber-border hover:bg-slate-800 text-slate-300 transition-all"
              title="Tua tới 10 giây"
            >
              <RotateCw className="w-4 h-4" />
            </button>
          </div>

          {/* Volume Control */}
          <div className="flex items-center gap-2">
            <button onClick={toggleMute} className="text-slate-400 hover:text-emerald-400 transition-colors">
              {isMuted || volume === 0 ? <VolumeX className="w-4 h-4 text-rose-400" /> : <Volume2 className="w-4 h-4" />}
            </button>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={isMuted ? 0 : volume}
              onChange={handleVolumeChange}
              className="w-24 accent-emerald-500 cursor-pointer h-1.5 bg-slate-800 rounded-lg"
            />
          </div>
        </div>
      </div>

      {/* VOLUME GRID & FILTER SECTION */}
      <div className="flex-1 p-6 overflow-y-auto min-h-0">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-bold text-slate-200 flex items-center gap-2">
              <Layers className="w-4 h-4 text-emerald-400" />
              Danh Sách Tập Audio 3-4 Tiếng
            </h2>
            {volumeData && (
              <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-bold">
                {volumeData.created_volumes_count} / {volumeData.total_volumes} Tập đã tạo
              </span>
            )}
          </div>

          {/* Filter Tabs */}
          <div className="flex gap-1 bg-slate-900 p-1 rounded-xl border border-cyber-border text-xs font-semibold">
            <button
              onClick={() => setFilter('ALL')}
              className={`px-3 py-1 rounded-lg transition-all ${filter === 'ALL' ? 'bg-emerald-500 text-slate-950 font-bold' : 'text-slate-400 hover:text-slate-200'}`}
            >
              Tất Cả ({volumeData?.total_volumes || 0})
            </button>
            <button
              onClick={() => setFilter('CREATED')}
              className={`px-3 py-1 rounded-lg transition-all ${filter === 'CREATED' ? 'bg-emerald-500 text-slate-950 font-bold' : 'text-slate-400 hover:text-slate-200'}`}
            >
              ✅ Đã Tạo ({volumeData?.created_volumes_count || 0})
            </button>
            <button
              onClick={() => setFilter('UNCREATED')}
              className={`px-3 py-1 rounded-lg transition-all ${filter === 'UNCREATED' ? 'bg-emerald-500 text-slate-950 font-bold' : 'text-slate-400 hover:text-slate-200'}`}
            >
              ⏳ Chưa Tạo ({(volumeData?.total_volumes || 0) - (volumeData?.created_volumes_count || 0)})
            </button>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-20 text-slate-400 gap-2">
            <RefreshCw className="w-5 h-5 animate-spin text-emerald-400" />
            Đang tải danh sách Tập Audio...
          </div>
        ) : filteredVolumes.length === 0 ? (
          <div className="text-center py-20 border border-dashed border-cyber-border rounded-2xl bg-slate-900/20">
            <p className="text-slate-400 text-sm font-medium">Chưa có Tập Audio nào khớp với bộ lọc.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredVolumes.map((vol) => (
              <div
                key={vol.volume_no}
                className={`p-4 rounded-2xl border transition-all duration-200 flex flex-col justify-between gap-3 ${
                  vol.is_created
                    ? 'bg-emerald-950/20 border-emerald-500/30 hover:border-emerald-500/60 shadow-lg'
                    : 'bg-slate-900/40 border-cyber-border/40 hover:border-cyber-border'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-bold px-2.5 py-1 rounded-lg bg-slate-800 border border-cyber-border text-slate-200">
                      Tập {vol.volume_no < 10 ? `0${vol.volume_no}` : vol.volume_no}
                    </span>

                    {vol.is_created ? (
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 flex items-center gap-1">
                        <CheckCircle className="w-3 h-3" /> ✅ Đã Tạo MP3
                      </span>
                    ) : (
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40 flex items-center gap-1">
                        <Clock className="w-3 h-3" /> ⏳ Chưa Tạo
                      </span>
                    )}
                  </div>

                  <h4 className="text-xs font-bold text-slate-100 leading-snug">
                    Chương {vol.start_chapter} ➔ Chương {vol.end_chapter} ({vol.chapter_count} chương)
                  </h4>

                  <div className="mt-3 flex items-center gap-3 text-[11px] text-slate-400 font-medium">
                    <span className="flex items-center gap-1">⏱️ ~{vol.estimated_hours} tiếng</span>
                    <span>•</span>
                    <span>📝 {vol.word_count.toLocaleString()} từ</span>
                    {vol.is_created && (
                      <>
                        <span>•</span>
                        <span className="text-emerald-400 font-bold">{vol.size_mb} MB</span>
                      </>
                    )}
                  </div>
                </div>

                {/* ACTION BUTTONS FOR EACH VOLUME */}
                <div className="pt-3 border-t border-cyber-border/20 flex items-center justify-between gap-2">
                  {vol.is_created ? (
                    <>
                      <button
                        onClick={() => handlePlayVolume(vol)}
                        className={`flex-1 text-xs font-bold py-2 px-3 rounded-xl border flex items-center justify-center gap-1.5 transition-all ${
                          currentPlaying?.volume_no === vol.volume_no && isPlaying
                            ? 'bg-emerald-500 text-slate-950 border-emerald-400 shadow-lg'
                            : 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40 hover:bg-emerald-500/30'
                        }`}
                      >
                        {currentPlaying?.volume_no === vol.volume_no && isPlaying ? (
                          <>
                            <Pause className="w-3.5 h-3.5 fill-slate-950" /> Đang Phát
                          </>
                        ) : (
                          <>
                            <Play className="w-3.5 h-3.5 fill-emerald-300" /> Nghe Tập Này
                          </>
                        )}
                      </button>

                      <a
                        href={vol.download_url}
                        download
                        className="p-2 rounded-xl bg-slate-800 border border-cyber-border hover:bg-slate-700 text-slate-200 transition-all"
                        title="Tải file MP3 Tập này"
                      >
                        <Download className="w-4 h-4" />
                      </a>
                    </>
                  ) : (
                    <button
                      onClick={() => handleGenerateSingleVolume(vol.volume_no)}
                      disabled={isGenerating}
                      className="w-full text-xs font-bold py-2 px-3 rounded-xl bg-amber-500/20 text-amber-300 border border-amber-500/40 hover:bg-amber-500/30 transition-all flex items-center justify-center gap-1.5 disabled:opacity-40"
                    >
                      {isGenerating ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                      ▶ Tạo Tập Này (3-4 tiếng)
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
