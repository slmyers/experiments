import { useState, useEffect } from 'react'
import axios from 'axios'

export function useMetrics(runId, viewMode) {
  const [metrics, setMetrics] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!runId && viewMode === 'historical') {
      setMetrics([])
      return
    }

    if (viewMode === 'live') {
      // Live polling
      const interval = setInterval(async () => {
        try {
          const response = await axios.get('/api/metrics/live')
          setMetrics(prev => [...prev, response.data].slice(-100)) // Keep last 100 points
        } catch (err) {
          console.error('Error fetching live metrics:', err)
        }
      }, 5000)

      return () => clearInterval(interval)
    } else {
      // Historical data
      setLoading(true)
      setError(null)

      axios.get(`/api/metrics/${runId}`)
        .then(response => {
          setMetrics(response.data)
          setLoading(false)
        })
        .catch(err => {
          setError(err.message)
          setLoading(false)
        })
    }
  }, [runId, viewMode])

  return { metrics, loading, error }
}
