import { useEffect } from 'react'
import { useNovelStore } from '../store/useNovelStore'

export const useSSE = () => {
  const { setLogs, addLog, setProgress, setPackagedResult } = useNovelStore()

  useEffect(() => {
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
  }, [setLogs, addLog, setProgress, setPackagedResult])
}
export default useSSE
