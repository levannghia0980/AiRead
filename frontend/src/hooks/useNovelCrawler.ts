import { useState, useCallback } from 'react'
import { useNovelStore } from '../store/useNovelStore'

export const useNovelCrawler = () => {
  const { fetchNovels, fetchNovelDetails } = useNovelStore()
  const [inputUrl, setInputUrl] = useState('')
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [analyzedData, setAnalyzedData] = useState<any>(null)
  const [isSaving, setIsSaving] = useState(false)

  const handleAnalyzeUrl = useCallback(async () => {
    if (!inputUrl) return
    setIsAnalyzing(true)
    setAnalyzedData(null)
    try {
      const res = await fetch('/api/novels/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: inputUrl })
      })
      if (!res.ok) throw new Error("Lỗi cào dữ liệu từ trang nguồn.")
      const data = await res.json()
      setAnalyzedData(data)
    } catch (err: any) {
      alert(err.message || "Failed to analyze URL")
    } finally {
      setIsAnalyzing(false)
    }
  }, [inputUrl])

  const handleSaveNovel = useCallback(async () => {
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
        await fetchNovelDetails(data.novel_id)
        setAnalyzedData(null)
        setInputUrl('')
      }
    } catch (e) {
      alert("Failed to save novel")
    } finally {
      setIsSaving(false)
    }
  }, [analyzedData, inputUrl, fetchNovels, fetchNovelDetails])

  return {
    inputUrl,
    setInputUrl,
    isAnalyzing,
    analyzedData,
    isSaving,
    handleAnalyzeUrl,
    handleSaveNovel
  }
}
export default useNovelCrawler
