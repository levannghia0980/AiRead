import { useEffect } from 'react'
import { useNovelStore } from '../store/useNovelStore'

export const useSSE = () => {
  useEffect(() => {
    const eventSource = new EventSource('/api/translation/logs')

    eventSource.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data)
        const { event: eventType, data } = payload
        const store = useNovelStore.getState()

        if (eventType === 'init_logs') {
          store.setLogs(data)
        } else if (eventType === 'log') {
          store.addLog(data)
        } else if (eventType === 'progress') {
          store.setProgress(data)
        } else if (eventType === 'packaged') {
          store.setPackagedResult(data)
          store.fetchNovels()
          const currentSelected = store.selectedNovel
          if (currentSelected?.novel?.id) {
            store.fetchNovelDetails(currentSelected.novel.id)
          }
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
}

export default useSSE
