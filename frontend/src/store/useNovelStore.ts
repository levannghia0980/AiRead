import { create } from 'zustand'

export interface Novel {
  id: number
  title: string
  author: string
  cover_url: string
  source_url: string
  genres: string
  status: string
  created_at: string
}

export interface Chapter {
  id: number
  novel_id: number
  chapter_no: number
  title: string
  source_url: string
  raw_text: string | null
  translated_text: string | null
  status: string
  error_msg: string | null
  token_count: number
  updated_at: string
}

export interface Glossary {
  id: number
  novel_id: number | null
  chinese_term: string
  vietnamese_term: string
  category: string
  is_active: boolean
}

export interface LogEntry {
  time: string
  message: string
  level: string
}

export interface ProgressData {
  isRunning: boolean
  novelId?: number
  novelTitle?: string
  stage: string
  totalChapters?: number
  completedChapters?: number
  failedChapters?: number
  currentChapterNo?: number
}

export interface PackagedResult {
  success: boolean
  title: string
  txt: string | null
  txt_clean: string | null
  html: string | null
  docx: string | null
  epub: string | null
}

interface NovelStore {
  novels: Novel[]
  selectedNovel: { novel: Novel; chapters: Chapter[] } | null
  glossary: Glossary[]
  logs: LogEntry[]
  progress: ProgressData | null
  packagedResult: PackagedResult | null

  // Settings (Persisted in localStorage)
  provider: string
  model: string
  apiKeys: string
  customPrompt: string
  delay: number
  concurrency: number
  startChapter: number | null
  endChapter: number | null

  setSettings: (settings: { provider?: string; model?: string; apiKeys?: string; customPrompt?: string; delay?: number; concurrency?: number; startChapter?: number | null; endChapter?: number | null }) => void
  testApiKey: () => Promise<{ success: boolean; message: string }>

  fetchNovels: () => Promise<void>
  fetchNovelDetails: (id: number) => Promise<void>
  deleteNovel: (id: number) => Promise<void>

  fetchGlossary: (novelId: number) => Promise<void>
  addGlossaryTerm: (novelId: number, chinese: string, vietnamese: string, category: string) => Promise<void>
  deleteGlossaryTerm: (novelId: number, termId: number) => Promise<void>

  startTranslation: (novelId: number) => Promise<void>
  pauseTranslation: () => Promise<void>
  clearJob: () => Promise<void>
  manualExport: (novelId: number) => Promise<void>
  resetChapters: (novelId: number, chapterNos?: number[]) => Promise<void>
  saveToFolder: (novelId: number) => Promise<{ success: boolean; folder?: string; total_files?: number; folder_path?: string; message?: string }>
  fetchChapterText: (novelId: number, chapterNo: number) => Promise<{ chapter_no: number; title: string; translated_text: string; raw_text: string } | null>

  addLog: (log: LogEntry) => void
  setLogs: (logs: LogEntry[]) => void
  setProgress: (progress: ProgressData) => void
  setPackagedResult: (res: PackagedResult | null) => void
}
// Pre-configure optimized defaults for OpenRouter DeepSeek V3 and API key
if (!localStorage.getItem('airead_provider') || localStorage.getItem('airead_provider')?.trim() === '' || localStorage.getItem('airead_provider') === 'gemini') {
  localStorage.setItem('airead_provider', 'openrouter');
}
if (!localStorage.getItem('airead_api_keys') || localStorage.getItem('airead_api_keys')?.trim() === '' || localStorage.getItem('airead_api_keys')?.startsWith('AQ.')) {
  localStorage.setItem('airead_api_keys', import.meta.env.VITE_OPENROUTER_API_KEY || '');
}
if (!localStorage.getItem('airead_model') || localStorage.getItem('airead_model')?.trim() === '' || localStorage.getItem('airead_model') === 'gemini-2.5-flash' || localStorage.getItem('airead_model') === 'deepseek/deepseek-chat' || localStorage.getItem('airead_model') === 'deepseek/deepseek-chat:free') {
  localStorage.setItem('airead_model', 'openrouter/free');
}
if (!localStorage.getItem('airead_concurrency')) {
  localStorage.setItem('airead_concurrency', '10');
}
if (!localStorage.getItem('airead_delay')) {
  localStorage.setItem('airead_delay', '0.5');
}

export const useNovelStore = create<NovelStore>((set, get) => ({
  novels: [],
  selectedNovel: null,
  glossary: [],
  logs: [],
  progress: null,
  packagedResult: null,

  // Load settings from localStorage or defaults
  provider: localStorage.getItem('airead_provider') || 'openrouter',
  model: localStorage.getItem('airead_model') || 'openrouter/free',
  apiKeys: localStorage.getItem('airead_api_keys') || import.meta.env.VITE_OPENROUTER_API_KEY || '',
  customPrompt: localStorage.getItem('airead_custom_prompt') || '',
  delay: Math.min(parseFloat(localStorage.getItem('airead_delay') || '0.5'), 1.5),
  concurrency: Math.max(parseInt(localStorage.getItem('airead_concurrency') || '10'), 10),
  startChapter: null,
  endChapter: null,

  setSettings: (settings) => {
    set((state) => {
      const newState = { ...state, ...settings }
      if (settings.provider !== undefined) localStorage.setItem('airead_provider', settings.provider)
      if (settings.model !== undefined) localStorage.setItem('airead_model', settings.model)
      if (settings.apiKeys !== undefined) localStorage.setItem('airead_api_keys', settings.apiKeys)
      if (settings.customPrompt !== undefined) localStorage.setItem('airead_custom_prompt', settings.customPrompt)
      if (settings.delay !== undefined) localStorage.setItem('airead_delay', settings.delay.toString())
      if (settings.concurrency !== undefined) localStorage.setItem('airead_concurrency', settings.concurrency.toString())
      return newState
    })
  },

  testApiKey: async () => {
    const { provider, model, apiKeys } = get()
    if (!apiKeys.trim()) {
      return { success: false, message: 'Vui lòng nhập API Key trước.' }
    }
    try {
      const res = await fetch('/api/translation/test-key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, model, api_key: apiKeys })
      })
      const data = await res.json()
      return data
    } catch (e: any) {
      return { success: false, message: `Lỗi kết nối: ${e.message}` }
    }
  },

  fetchNovels: async () => {
    try {
      const res = await fetch('/api/novels')
      const data = await res.json()
      set({ novels: data })
    } catch (e) {
      console.error("Failed to fetch novels", e)
    }
  },

  fetchNovelDetails: async (id) => {
    try {
      const res = await fetch(`/api/novels/${id}`)
      if (res.ok) {
        const data = await res.json()
        set({ selectedNovel: data })
      }
    } catch (e) {
      console.error("Failed to fetch novel details", e)
    }
  },

  deleteNovel: async (id) => {
    try {
      const res = await fetch(`/api/novels/${id}`, { method: 'DELETE' })
      if (res.ok) {
        set((state) => ({
          novels: state.novels.filter((n) => n.id !== id),
          selectedNovel: state.selectedNovel?.novel.id === id ? null : state.selectedNovel
        }))
      }
    } catch (e) {
      console.error("Failed to delete novel", e)
    }
  },

  fetchGlossary: async (novelId) => {
    try {
      const res = await fetch(`/api/novels/${novelId}/glossary`)
      const data = await res.json()
      set({ glossary: data })
    } catch (e) {
      console.error("Failed to fetch glossary", e)
    }
  },

  addGlossaryTerm: async (novelId, chinese, vietnamese, category) => {
    try {
      const res = await fetch(`/api/novels/${novelId}/glossary`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chinese_term: chinese, vietnamese_term: vietnamese, category })
      })
      if (res.ok) {
        get().fetchGlossary(novelId)
      }
    } catch (e) {
      console.error("Failed to add glossary term", e)
    }
  },

  deleteGlossaryTerm: async (novelId, termId) => {
    try {
      const res = await fetch(`/api/novels/${novelId}/glossary/${termId}`, {
        method: 'DELETE'
      })
      if (res.ok) {
        set((state) => ({
          glossary: state.glossary.filter((g) => g.id !== termId)
        }))
      }
    } catch (e) {
      console.error("Failed to delete glossary term", e)
    }
  },

  startTranslation: async (novelId) => {
    const { provider, model, apiKeys, customPrompt, delay, concurrency, startChapter, endChapter } = get()
    set({ packagedResult: null }) // Reset download links
    const res = await fetch('/api/translation/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        novel_id: novelId,
        provider,
        model,
        api_key: apiKeys,
        prompt: customPrompt,
        delay,
        concurrency,
        start_chapter: startChapter,
        end_chapter: endChapter
      })
    })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || "Lỗi khởi chạy dịch")
    }
  },

  pauseTranslation: async () => {
    await fetch('/api/translation/pause', { method: 'POST' })
  },

  clearJob: async () => {
    await fetch('/api/translation/clear', { method: 'POST' })
    set({ progress: null, logs: [], packagedResult: null })
  },

  manualExport: async (novelId) => {
    try {
      const res = await fetch('/api/translation/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ novel_id: novelId })
      })
      if (res.ok) {
        const data = await res.json()
        set({ packagedResult: data })
      }
    } catch (e) {
      console.error("Manual export failed", e)
    }
  },

  resetChapters: async (novelId, chapterNos) => {
    try {
      const res = await fetch(`/api/novels/${novelId}/chapters/reset`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chapter_nos: chapterNos || null })
      })
      if (res.ok) {
        const store = get()
        await store.fetchNovelDetails(novelId)
      } else {
        const err = await res.json()
        throw new Error(err.detail || "Lỗi reset chương")
      }
    } catch (e) {
      console.error("Failed to reset chapters", e)
      throw e
    }
  },

  saveToFolder: async (novelId) => {
    try {
      const res = await fetch(`/api/novels/${novelId}/save-to-folder`, {
        method: 'POST'
      })
      const data = await res.json()
      if (!res.ok) {
        return { success: false, message: data.detail || 'Lỗi lưu file' }
      }
      return data
    } catch (e: any) {
      return { success: false, message: `Lỗi kết nối: ${e.message}` }
    }
  },

  fetchChapterText: async (novelId, chapterNo) => {
    try {
      const res = await fetch(`/api/novels/${novelId}/chapters/${chapterNo}/text`)
      if (res.ok) {
        return await res.json()
      }
      return null
    } catch {
      return null
    }
  },

  addLog: (log) => set((state) => ({ logs: [...state.logs, log].slice(-500) })),
  setLogs: (logs) => set({ logs }),
  setProgress: (progress) => set({ progress }),
  setPackagedResult: (packagedResult) => set({ packagedResult })
}))
