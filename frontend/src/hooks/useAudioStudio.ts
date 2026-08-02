import { useState, useCallback } from 'react'

export const useAudioStudio = () => {
  const [isGeneratingAudio, setIsGeneratingAudio] = useState(false)
  const [audioStatus, setAudioStatus] = useState<any>(null)
  const [audioFiles, setAudioFiles] = useState<any[]>([])

  const fetchAudioFiles = useCallback(async (novelId: number) => {
    try {
      const res = await fetch(`/api/novels/${novelId}/audio/files`)
      if (res.ok) {
        const data = await res.json()
        setAudioFiles(data.files || [])
      }
    } catch (e) {
      console.error("Failed to fetch audio files", e)
    }
  }, [])

  const pollAudioStatus = useCallback((novelId: number) => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/novels/${novelId}/audio/status`)
        if (res.ok) {
          const status = await res.json()
          setAudioStatus(status)
          if (!status.is_running) {
            setIsGeneratingAudio(false)
            clearInterval(interval)
            fetchAudioFiles(novelId)
          }
        }
      } catch (e) {
        clearInterval(interval)
        setIsGeneratingAudio(false)
      }
    }, 3000)
  }, [fetchAudioFiles])

  const handleGenerateAudio = useCallback(async (novelId: number) => {
    setIsGeneratingAudio(true)
    try {
      const res = await fetch(`/api/novels/${novelId}/audio/generate`, { method: 'POST' })
      const data = await res.json()
      alert(data.message)
      pollAudioStatus(novelId)
    } catch (e) {
      console.error("Failed to start audio generation", e)
      setIsGeneratingAudio(false)
    }
  }, [pollAudioStatus])

  const handleDeleteAudioFile = useCallback(async (novelId: number, filename: string) => {
    if (!confirm(`Bạn có chắc chắn muốn xóa file audio: ${filename}?`)) return
    try {
      const res = await fetch(`/api/novels/${novelId}/audio/files/${encodeURIComponent(filename)}`, { method: 'DELETE' })
      if (res.ok) {
        fetchAudioFiles(novelId)
      } else {
        alert("Xóa file thất bại!")
      }
    } catch (e) {
      console.error("Failed to delete audio file", e)
    }
  }, [fetchAudioFiles])

  const handleDeleteAllAudioFiles = useCallback(async (novelId: number) => {
    if (!confirm("Bạn có chắc chắn muốn xóa TOÀN BỘ file audio của truyện này?")) return
    try {
      const res = await fetch(`/api/novels/${novelId}/audio/files`, { method: 'DELETE' })
      if (res.ok) {
        setAudioFiles([])
      } else {
        alert("Xóa toàn bộ file thất bại!")
      }
    } catch (e) {
      console.error("Failed to delete all audio files", e)
    }
  }, [])

  return {
    isGeneratingAudio,
    audioStatus,
    audioFiles,
    fetchAudioFiles,
    handleGenerateAudio,
    handleDeleteAudioFile,
    handleDeleteAllAudioFiles
  }
}
export default useAudioStudio
