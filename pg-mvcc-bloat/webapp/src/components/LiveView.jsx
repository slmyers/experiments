import React, { useState, useEffect } from 'react'
import axios from 'axios'
import StorageChart from './StorageChart'
import DeadTupleChart from './DeadTupleChart'
import HOTUpdateChart from './HOTUpdateChart'
import MetricsChart from './MetricsChart'
import './LiveView.css'

function LiveView() {
  const [metrics, setMetrics] = useState([])
  const [status, setStatus] = useState('connecting')
  const [currentStats, setCurrentStats] = useState(null)

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const response = await axios.get('/api/metrics/live')
        setMetrics(prev => {
          const newMetrics = [...prev, response.data]
          return newMetrics.slice(-120) // Keep last 10 minutes at 5s intervals
        })
        setCurrentStats(response.data)
        setStatus('connected')
      } catch (err) {
        console.error('Error fetching live metrics:', err)
        setStatus('error')
      }
    }, 5000)

    return () => clearInterval(interval)
  }, [])

  return (
    <div className="live-view">
      <div className="live-header">
        <h2>Live Metrics</h2>
        <div className={`status-indicator ${status}`}>
          <span className="dot"></span>
          {status === 'connected' ? 'Connected' : status === 'connecting' ? 'Connecting...' : 'Connection Error'}
        </div>
      </div>

      {currentStats && (
        <div className="current-stats">
          <div className="stat-card">
            <div className="stat-label">Dead Tuples</div>
            <div className="stat-value">{currentStats.n_dead_tup.toLocaleString()}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Dead Ratio</div>
            <div className="stat-value">
              {((currentStats.n_dead_tup / (currentStats.n_live_tup + currentStats.n_dead_tup)) * 100).toFixed(1)}%
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-label">TOAST Size</div>
            <div className="stat-value">
              {(currentStats.toast_size_bytes / 1024 / 1024 / 1024).toFixed(2)} GB
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Total Size</div>
            <div className="stat-value">
              {(currentStats.total_size_bytes / 1024 / 1024 / 1024).toFixed(2)} GB
            </div>
          </div>
        </div>
      )}

      {metrics.length > 0 && (
        <div className="charts-container">
          <div className="chart-wrapper">
            <h2>Storage Growth</h2>
            <StorageChart data={metrics} />
          </div>

          <div className="chart-wrapper">
            <h2>Dead Tuples</h2>
            <DeadTupleChart data={metrics} />
          </div>

          <div className="chart-wrapper">
            <h2>HOT Update Ratio</h2>
            <HOTUpdateChart data={metrics} />
          </div>

          <div className="chart-wrapper">
            <h2>Buffer Cache Hit Ratio</h2>
            <MetricsChart data={metrics} />
          </div>
        </div>
      )}
    </div>
  )
}

export default LiveView
