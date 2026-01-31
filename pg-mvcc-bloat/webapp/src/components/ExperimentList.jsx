import React, { useState, useEffect } from 'react'
import axios from 'axios'
import './ExperimentList.css'

function ExperimentList({ selectedRun, onSelectRun }) {
  const [runs, setRuns] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    axios.get('/api/experiments')
      .then(response => {
        setRuns(response.data)
        setLoading(false)
      })
      .catch(err => {
        console.error('Error fetching experiments:', err)
        setLoading(false)
      })
  }, [])

  if (loading) {
    return <div className="experiment-list loading">Loading experiments...</div>
  }

  return (
    <div className="experiment-list">
      <h2>Available Experiments</h2>
      <div className="runs-grid">
        {runs.map(run => (
          <div 
            key={run.id}
            className={`run-card ${selectedRun === run.id ? 'selected' : ''}`}
            onClick={() => onSelectRun(run.id)}
          >
            <div className="run-preset">{run.preset}</div>
            <div className="run-timestamp">{run.timestamp}</div>
            <div className="run-stats">
              <span>Duration: {run.duration}s</span>
              <span>Samples: {run.samples}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default ExperimentList
