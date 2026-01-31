import React, { useState, useEffect } from 'react'
import ExperimentList from './components/ExperimentList'
import MetricsChart from './components/MetricsChart'
import StorageChart from './components/StorageChart'
import DeadTupleChart from './components/DeadTupleChart'
import HOTUpdateChart from './components/HOTUpdateChart'
import LiveView from './components/LiveView'
import { useMetrics } from './hooks/useMetrics'
import './App.css'

function App() {
  const [selectedRun, setSelectedRun] = useState(null)
  const [viewMode, setViewMode] = useState('historical') // 'historical' or 'live'
  const { metrics, loading, error } = useMetrics(selectedRun, viewMode)

  return (
    <div className="app">
      <header className="header">
        <h1>PostgreSQL MVCC Bloat Visualizer</h1>
        <p className="subtitle">Real-time observation of dead tuple accumulation and storage growth</p>
      </header>

      <div className="controls">
        <div className="view-mode-toggle">
          <button 
            className={viewMode === 'historical' ? 'active' : ''}
            onClick={() => setViewMode('historical')}
          >
            Historical Data
          </button>
          <button 
            className={viewMode === 'live' ? 'active' : ''}
            onClick={() => setViewMode('live')}
          >
            Live View
          </button>
        </div>
      </div>

      {viewMode === 'historical' ? (
        <>
          <ExperimentList 
            selectedRun={selectedRun}
            onSelectRun={setSelectedRun}
          />

          {loading && <div className="loading">Loading metrics...</div>}
          {error && <div className="error">Error: {error}</div>}

          {metrics && metrics.length > 0 && (
            <div className="charts-container">
              <div className="chart-wrapper">
                <h2>Storage Growth Over Time</h2>
                <StorageChart data={metrics} />
              </div>

              <div className="chart-wrapper">
                <h2>Dead Tuples Accumulation</h2>
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
        </>
      ) : (
        <LiveView />
      )}

      <footer className="footer">
        <p>Inspired by <a href="https://www.cs.cmu.edu/~pavlo/blog/2023/04/the-part-of-postgresql-we-hate-the-most.html" target="_blank" rel="noopener noreferrer">Andy Pavlo's blog post</a></p>
      </footer>
    </div>
  )
}

export default App
