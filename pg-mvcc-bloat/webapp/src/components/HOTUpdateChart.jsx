import React from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

function HOTUpdateChart({ data }) {
  const chartData = data.map(d => {
    const hotRatio = d.n_tup_upd > 0 
      ? ((d.n_tup_hot_upd / d.n_tup_upd) * 100).toFixed(2)
      : 0
    return {
      time: d.elapsed_seconds,
      hotRatio: parseFloat(hotRatio),
      updates: d.n_tup_upd,
      hotUpdates: d.n_tup_hot_upd
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
          label={{ value: 'HOT Update Ratio (%)', angle: -90, position: 'insideLeft', fill: '#8b949e' }}
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
        <Line type="monotone" dataKey="hotRatio" stroke="#3fb950" name="HOT Update %" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  )
}

export default HOTUpdateChart
