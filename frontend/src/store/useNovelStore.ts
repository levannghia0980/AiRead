import { create } from 'zustand'

export interface Novel {
  id: number
  title?: string
  title_raw?: string
  title_rough?: string
  author: string
  cover_url: string
  source_url: string
  genres: string
  status: string
  created_at: string
  total_chapters?: number
  completed_chapters?: number
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
  gender?: string | null
  role?: string | null
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

export interface GenreOption {
  code: string
  name: string
  icon: string
  desc: string
}

export const NOVEL_GENRE_OPTIONS: GenreOption[] = [
  { code: 'XIANXIA', name: 'Tiên Hiệp / Cổ Trang / Huyền Huyễn', icon: '☯️', desc: 'Ta/Ngươi, Hắn/Nàng, Trúc Cơ, Đan Điền, Tông Môn' },
  { code: 'WUXIA', name: 'Võ Lâm / Kiếm Hiệp', icon: '⚔️', desc: 'Huynh/Đệ, Tỷ/Muội, Gia Tộc, Chưởng Môn, Binh Khí' },
  { code: 'MODERN_URBAN', name: 'Đô Thị / Hiện Đại / Thương Chiến', icon: '🏙️', desc: 'Anh/Chị/Em, Bố/Mẹ, Sếp/Chủ tịch, Công ty, Xe hơi' }
]

interface NovelStore {
  novels: Novel[]
  selectedNovel: { novel: Novel; chapters: Chapter[] } | null
  glossary: Glossary[]
  corrections: any[]
  logs: LogEntry[]
  progress: ProgressData | null
  packagedResult: PackagedResult | null

  // Settings (Persisted in localStorage + backend .env)
  provider: string
  model: string
  apiKeys: string
  customPrompt: string
  delay: number
  batchSize: number
  startChapter: number | null
  endChapter: number | null
  translationStyle: string
  enableUnblock: boolean
  enableErotic: boolean
  enableLlmExtract: boolean
  enableNamesDict: boolean
  enableGgCorrections: boolean
  forceRetranslate: boolean

  setSettings: (settings: {
    provider?: string;
    model?: string;
    apiKeys?: string;
    customPrompt?: string;
    delay?: number;
    batchSize?: number;
    startChapter?: number | null;
    endChapter?: number | null;
    translationStyle?: string;
    enableUnblock?: boolean;
    enableErotic?: boolean;
    enableLlmExtract?: boolean;
    enableNamesDict?: boolean;
    enableGgCorrections?: boolean;
    forceRetranslate?: boolean;
  }) => void
  saveSettingsToEnv: (settings?: { provider?: string; model?: string; apiKeys?: string; customPrompt?: string; delay?: number; batchSize?: number; translationStyle?: string }) => Promise<void>
  loadSettingsFromEnv: () => Promise<void>
  testApiKey: () => Promise<{ success: boolean; message: string }>

  fetchNovels: () => Promise<void>
  fetchNovelDetails: (id: number) => Promise<void>
  deleteNovel: (id: number) => Promise<void>
  updateNovelGenre: (novelId: number, genreCode: string) => Promise<{ success: boolean; message: string }>


  fetchGlossary: (novelId: number, chapterNo?: number | null) => Promise<void>
  addGlossaryTerm: (novelId: number, chinese: string, vietnamese: string, category: string, chapterNo?: number | null, gender?: string | null, role?: string | null) => Promise<{ success: boolean; message?: string; affected_chapters?: number }>
  updateGlossaryTerm: (novelId: number, termId: number, chinese: string, vietnamese: string, category: string, oldVietnamese?: string, chapterNo?: number | null, gender?: string | null, role?: string | null) => Promise<{ success: boolean; message?: string; affected_chapters?: number }>
  applyGlossaryToAllChapters: (novelId: number) => Promise<{ success: boolean; message?: string; affected_chapters?: number }>
  deleteGlossaryTerm: (novelId: number, termId: number, chapterNo?: number | null) => Promise<void>
  fetchCorrections: (novelId: number, chapterNo: number) => Promise<void>
  addCorrection: (novelId: number, chapterNo: number, wrong: string, correct: string) => Promise<any>
  updateCorrection: (novelId: number, chapterNo: number, corrId: number, wrong: string, correct: string) => Promise<any>
  deleteCorrection: (novelId: number, chapterNo: number, corrId: number) => Promise<void>

  startTranslation: (novelId: number) => Promise<void>
  pauseTranslation: () => Promise<void>
  clearJob: () => Promise<void>
  manualExport: (novelId: number) => Promise<void>
  resetChapters: (novelId: number, chapterNos?: number[]) => Promise<void>
  restartNovel: (novelId: number) => Promise<{ success: boolean; message: string }>
  saveToFolder: (novelId: number) => Promise<{ success: boolean; folder?: string; total_files?: number; folder_path?: string; message?: string }>
  fetchChapterText: (novelId: number, chapterNo: number) => Promise<{ chapter_no: number; title: string; translated_text: string; raw_text: string } | null>
  updateChapterText: (novelId: number, chapterNo: number, text: string) => Promise<boolean>
  downloadNovel: (novelId: number, fmt: 'txt' | 'docx') => Promise<void>

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
if (!localStorage.getItem('airead_batch_size')) {
  localStorage.setItem('airead_batch_size', '3');
}
if (!localStorage.getItem('airead_delay')) {
  localStorage.setItem('airead_delay', '0.5');
}

export const useNovelStore = create<NovelStore>((set, get) => ({
  novels: [],
  selectedNovel: null,
  glossary: [],
  corrections: [],
  logs: [],
  progress: null,
  packagedResult: null,

  // Load settings from localStorage or defaults
  provider: localStorage.getItem('airead_provider') || 'openrouter',
  model: localStorage.getItem('airead_model') || 'openrouter/free',
  apiKeys: localStorage.getItem('airead_api_keys') || import.meta.env.VITE_OPENROUTER_API_KEY || '',
  customPrompt: localStorage.getItem('airead_custom_prompt') || '',
  delay: Math.max(0, parseFloat(localStorage.getItem('airead_delay') || '0.5')),
  batchSize: Math.max(parseInt(localStorage.getItem('airead_batch_size') || '3'), 1),
  startChapter: null,
  endChapter: null,
  translationStyle: localStorage.getItem('airead_translation_style') || 'draft_only',
  enableUnblock: localStorage.getItem('airead_enable_unblock') !== 'false',
  enableErotic: localStorage.getItem('airead_enable_erotic') !== 'false',
  enableLlmExtract: true,
  enableNamesDict: true,
  enableGgCorrections: true,
  forceRetranslate: false,

  setSettings: (settings) => {
    set((state) => {
      const newState = { ...state, ...settings }
      if (settings.provider !== undefined) localStorage.setItem('airead_provider', settings.provider)
      if (settings.model !== undefined) localStorage.setItem('airead_model', settings.model)
      if (settings.apiKeys !== undefined) localStorage.setItem('airead_api_keys', settings.apiKeys)
      if (settings.customPrompt !== undefined) localStorage.setItem('airead_custom_prompt', settings.customPrompt)
      if (settings.delay !== undefined) localStorage.setItem('airead_delay', settings.delay.toString())
      if (settings.batchSize !== undefined) localStorage.setItem('airead_batch_size', settings.batchSize.toString())
      if (settings.translationStyle !== undefined) localStorage.setItem('airead_translation_style', settings.translationStyle)
      if (settings.enableUnblock !== undefined) localStorage.setItem('airead_enable_unblock', settings.enableUnblock ? 'true' : 'false')
      if (settings.enableErotic !== undefined) localStorage.setItem('airead_enable_erotic', settings.enableErotic ? 'true' : 'false')
      if (settings.enableLlmExtract !== undefined) localStorage.setItem('airead_enable_llm_extract', settings.enableLlmExtract ? 'true' : 'false')
      if (settings.enableNamesDict !== undefined) localStorage.setItem('airead_enable_names_dict', settings.enableNamesDict ? 'true' : 'false')
      if (settings.enableGgCorrections !== undefined) localStorage.setItem('airead_enable_gg_corrections', settings.enableGgCorrections ? 'true' : 'false')
      return newState
    })
    // Tự động lưu vào backend .env (debounced 800ms)
    clearTimeout((window as any)._saveSettingsTimer)
      ; (window as any)._saveSettingsTimer = setTimeout(() => {
        get().saveSettingsToEnv(settings as any)
      }, 800)
  },

  saveSettingsToEnv: async (settings) => {
    try {
      const state = get()
      const payload: Record<string, any> = {}
      const src = settings ?? state
      if ('apiKeys' in src && src.apiKeys !== undefined) payload.api_keys = src.apiKeys
      if ('provider' in src && src.provider !== undefined) payload.provider = src.provider
      if ('model' in src && src.model !== undefined) payload.model = src.model
      if ('batchSize' in src && src.batchSize !== undefined) payload.batch_size = src.batchSize
      if ('delay' in src && src.delay !== undefined) payload.delay = src.delay
      if ('customPrompt' in src && src.customPrompt !== undefined) payload.custom_prompt = src.customPrompt
      if ('translationStyle' in src && src.translationStyle !== undefined) payload.translation_style = src.translationStyle
      if (Object.keys(payload).length === 0) return
      await fetch('/api/settings/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
    } catch (e) {
      console.warn('Không thể lưu settings vào .env backend:', e)
    }
  },

  loadSettingsFromEnv: async () => {
    try {
      const res = await fetch('/api/settings')
      if (!res.ok) return
      const data = await res.json()
      // Backend .env có key hợp lệ → ưu tiên hơn localStorage
      if (data.api_keys && data.api_keys.trim()) {
        set((state) => {
          const updates: Partial<NovelStore> = {}
          if (data.api_keys) {
            updates.apiKeys = data.api_keys
            localStorage.setItem('airead_api_keys', data.api_keys)
          }
          if (data.provider) {
            updates.provider = data.provider
            localStorage.setItem('airead_provider', data.provider)
          }
          if (data.model) {
            updates.model = data.model
            localStorage.setItem('airead_model', data.model)
          }
          if (data.batch_size) {
            updates.batchSize = data.batch_size
            localStorage.setItem('airead_batch_size', String(data.batch_size))
          }
          if (data.delay) {
            updates.delay = data.delay
            localStorage.setItem('airead_delay', String(data.delay))
          }
          if (data.custom_prompt) {
            updates.customPrompt = data.custom_prompt
            localStorage.setItem('airead_custom_prompt', data.custom_prompt)
          }
          if (data.translation_style) {
            updates.translationStyle = data.translation_style
            localStorage.setItem('airead_translation_style', data.translation_style)
          }
          return { ...state, ...updates }
        })
      }
    } catch (e) {
      console.warn('Không thể tải settings từ backend .env:', e)
    }
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
      const list = Array.isArray(data) ? data : (data.data || [])
      set({ novels: list })
    } catch (e) {
      console.error("Failed to fetch novels", e)
    }
  },

  fetchNovelDetails: async (id) => {
    const current = get().selectedNovel
    if (current && current.novel && current.novel.id !== id) {
      set({ selectedNovel: null })
    }
    try {
      const res = await fetch(`/api/novels/${id}`)
      if (res.ok) {
        const data = await res.json()
        if (data.novel && data.chapters) {
          set({ selectedNovel: { novel: data.novel, chapters: data.chapters } })
        } else if (data.data) {
          set({ selectedNovel: { novel: data.data, chapters: data.chapters || [] } })
        } else {
          set({ selectedNovel: data })
        }
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

  fetchGlossary: async (novelId, chapterNo) => {
    try {
      const url = chapterNo
        ? `/api/novels/${novelId}/chapters/${chapterNo}/entities`
        : `/api/novels/${novelId}/glossary`
      const res = await fetch(url)
      const data = await res.json()
      set({ glossary: Array.isArray(data) ? data : [] })
    } catch (e) {
      console.error("Failed to fetch glossary", e)
      set({ glossary: [] })
    }
  },

  addGlossaryTerm: async (novelId, chinese, vietnamese, category, chapterNo, gender, role) => {
    try {
      const res = await fetch(`/api/novels/${novelId}/glossary`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          chinese_term: chinese, 
          vietnamese_term: vietnamese, 
          category,
          chapter_no: chapterNo || undefined,
          gender: gender || null,
          role: role || null
        })
      })
      const data = await res.json()
      if (res.ok) {
        get().fetchGlossary(novelId, chapterNo)
      }
      return data
    } catch (e: any) {
      console.error("Failed to add glossary term", e)
      return { success: false, message: e.message }
    }
  },

  updateGlossaryTerm: async (novelId, termId, chinese, vietnamese, category, oldVietnamese, chapterNo, gender, role) => {
    try {
      const res = await fetch(`/api/novels/${novelId}/glossary/${termId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          chinese_term: chinese,
          vietnamese_term: vietnamese,
          category,
          old_vietnamese_term: oldVietnamese || null,
          apply_to_all_chapters: true,
          gender: gender || null,
          role: role || null
        })
      })
      const data = await res.json()
      if (res.ok) {
        get().fetchGlossary(novelId, chapterNo)
      }
      return { ...data, affected_chapters: data.affected_chapters || 0 }
    } catch (e: any) {
      console.error("Failed to update glossary term", e)
      return { success: false, message: e.message }
    }
  },

  applyGlossaryToAllChapters: async (novelId) => {
    try {
      const res = await fetch(`/api/novels/${novelId}/glossary/apply-all`, {
        method: 'POST'
      })
      const data = await res.json()
      return data
    } catch (e: any) {
      console.error("Failed to apply glossary to all chapters", e)
      return { success: false, message: e.message }
    }
  },

  deleteGlossaryTerm: async (novelId, termId, chapterNo) => {
    try {
      const url = chapterNo
        ? `/api/novels/${novelId}/glossary/${termId}?chapter_no=${chapterNo}`
        : `/api/novels/${novelId}/glossary/${termId}`
      const res = await fetch(url, {
        method: 'DELETE'
      })
      if (res.ok) {
        get().fetchGlossary(novelId, chapterNo)
      }
    } catch (e) {
      console.error("Failed to delete glossary term", e)
    }
  },

  fetchCorrections: async (novelId, chapterNo) => {
    if (!chapterNo) {
      set({ corrections: [] })
      return
    }
    try {
      const res = await fetch(`/api/novels/${novelId}/chapters/${chapterNo}/corrections`)
      if (res.ok) {
        const data = await res.json()
        set({ corrections: Array.isArray(data) ? data : [] })
      } else {
        set({ corrections: [] })
      }
    } catch (e) {
      console.error("Failed to fetch corrections", e)
      set({ corrections: [] })
    }
  },

  addCorrection: async (novelId, chapterNo, wrong, correct) => {
    try {
      const res = await fetch(`/api/novels/${novelId}/chapters/${chapterNo}/corrections`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ wrong_text: wrong, correct_text: correct })
      })
      const data = await res.json()
      if (res.ok) {
        get().fetchCorrections(novelId, chapterNo)
      }
      return data
    } catch (e: any) {
      return { success: false, message: e.message }
    }
  },

  updateCorrection: async (novelId, chapterNo, corrId, wrong, correct) => {
    try {
      const res = await fetch(`/api/novels/${novelId}/chapters/${chapterNo}/corrections/${corrId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ wrong_text: wrong, correct_text: correct })
      })
      const data = await res.json()
      if (res.ok) {
        get().fetchCorrections(novelId, chapterNo)
      }
      return data
    } catch (e: any) {
      return { success: false, message: e.message }
    }
  },

  deleteCorrection: async (novelId, chapterNo, corrId) => {
    try {
      const res = await fetch(`/api/novels/${novelId}/chapters/${chapterNo}/corrections/${corrId}`, {
        method: 'DELETE'
      })
      if (res.ok) {
        get().fetchCorrections(novelId, chapterNo)
      }
    } catch (e) {
      console.error("Failed to delete correction", e)
    }
  },

  updateNovelGenre: async (novelId, genreCode) => {

    try {
      const res = await fetch(`/api/novels/${novelId}/genre`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ genre: genreCode })
      })
      if (res.ok) {
        const data = await res.json()
        set((state) => ({
          novels: state.novels.map((n) => (n.id === novelId ? { ...n, genres: genreCode } : n)),
          selectedNovel: state.selectedNovel && state.selectedNovel.novel.id === novelId
            ? { ...state.selectedNovel, novel: { ...state.selectedNovel.novel, genres: genreCode } }
            : state.selectedNovel
        }))
        return { success: true, message: data.message }
      } else {
        const err = await res.json()
        return { success: false, message: err.detail || 'Lỗi lưu thể loại truyện' }
      }
    } catch (e: any) {
      return { success: false, message: e.message }
    }
  },

  startTranslation: async (novelId) => {

    let { provider, model, apiKeys, customPrompt, delay, batchSize, startChapter, endChapter, translationStyle, enableUnblock } = get()

    // Fix race condition: nếu apiKeys rỗng (loadSettingsFromEnv chưa hoàn thành),
    // thử load thẳng từ backend .env trước khi gửi request
    if (!apiKeys || !apiKeys.trim()) {
      try {
        const settingsRes = await fetch('/api/settings')
        if (settingsRes.ok) {
          const data = await settingsRes.json()
          if (data.api_keys && data.api_keys.trim()) {
            apiKeys = data.api_keys
            // Cập nhật store và localStorage luôn
            get().setSettings({ apiKeys: data.api_keys })
          }
        }
      } catch (_) { /* bỏ qua lỗi mạng, để backend trả 400 với message rõ ràng */ }
    }

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
        batch_size: batchSize,
        start_chapter: startChapter,
        end_chapter: endChapter,
        translation_style: translationStyle,
        enable_unblock: enableUnblock,
        enable_erotic: get().enableErotic !== false,
        enable_llm_extract: get().enableLlmExtract !== false,
        enable_names_dict: get().enableNamesDict !== false,
        enable_gg_corrections: get().enableGgCorrections !== false,
        force_retranslate: get().forceRetranslate || false
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

  restartNovel: async (novelId) => {
    try {
      const res = await fetch(`/api/novels/${novelId}/chapters/reset`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ full_restart: true })
      })
      const data = await res.json()
      if (res.ok) {
        await get().fetchNovelDetails(novelId)
        await get().fetchNovels()
        return { success: true, message: data.message || 'Restart thành công' }
      } else {
        return { success: false, message: data.detail || 'Lỗi restart' }
      }
    } catch (e: any) {
      console.error("Failed to restart novel", e)
      return { success: false, message: e.message }
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

  updateChapterText: async (novelId, chapterNo, text) => {
    try {
      const res = await fetch(`/api/novels/${novelId}/chapters/${chapterNo}/text`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ translated_text: text })
      })
      if (res.ok) {
        set((state) => {
          if (!state.selectedNovel) return state
          const updatedChapters = state.selectedNovel.chapters.map((ch) =>
            ch.chapter_no === chapterNo
              ? { ...ch, translated_text: text, status: 'COMPLETED' }
              : ch
          )
          return {
            selectedNovel: {
              ...state.selectedNovel,
              chapters: updatedChapters
            }
          }
        })
      }
      return res.ok
    } catch {
      return false
    }
  },

  downloadNovel: async (novelId, fmt) => {
    const url = `/api/novels/${novelId}/download?fmt=${fmt}`
    const res = await fetch(url)
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Lỗi tải file' }))
      throw new Error(err.detail || 'Lỗi tải file')
    }
    const blob = await res.blob()
    const disposition = res.headers.get('Content-Disposition') || ''
    const match = disposition.match(/filename="?([^"]+)"?/)
    const filename = match ? match[1] : `novel.${fmt}`
    const objUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = objUrl
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(objUrl)
  },

  addLog: (log) => set((state) => ({ logs: [...state.logs, log].slice(-500) })),
  setLogs: (logs) => set({ logs }),
  setProgress: (progress) => {
    set((state) => {
      let updatedSelectedNovel = state.selectedNovel
      if (progress && progress.currentChapterNo && state.selectedNovel && (!progress.novelId || state.selectedNovel.novel.id === progress.novelId)) {
        const chapters = state.selectedNovel.chapters.map((ch: any) => {
          if (ch.chapter_no === progress.currentChapterNo) {
            return { ...ch, status: 'COMPLETED' }
          }
          return ch
        })
        updatedSelectedNovel = { ...state.selectedNovel, chapters }
      }
      return { progress, selectedNovel: updatedSelectedNovel }
    })
  },
  setPackagedResult: (packagedResult) => set({ packagedResult })
}))
