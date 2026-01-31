import React from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

function MetricsChart({ data }) {
  const chartData = data.map(d => {
    const totalBlks = d.heap_blks_read + d.heap_blks_hit
    const hitRatio = totalBlks > 0 ? ((d.heap_blks_hit / totalBlks) * 100).toFixed(2) : 0
    return {
      time: d.elapsed_seconds,
      hitRatio: parseFloat(hitRatio)
    }
  })

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" stroke="#30363d" />
        <XAxis 
          dataKey="time" 
          stroke="#8b949e"
          label={{ value: 'Time (seconds)', position: 'insideBottom', offset: -5, fill: '#8b949e' }}
        />
        <YAxis 
          stroke="#8b949e"
          label={{ value: 'Hit Ratio (%)', angle: -90, position: 'insideLeft', fill: '#8b949e' }}
          domain={[0, 100]}
        />
        <Tooltip 
          contentStyle={{ 
            backgroundColor: '#161b22', 
            border: '1px solid #30363d',
            borderRadius: '6px',
            color: '#e6edf3'
          }}
        />
        <Legend />
        <Line type="monotone" dataKey="hitRatio" stroke="#a371f7" name="Buffer Cache Hit %" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  )
}

export default MetricsChart
