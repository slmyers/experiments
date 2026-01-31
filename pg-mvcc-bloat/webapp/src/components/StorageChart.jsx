import React from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

function StorageChart({ data }) {
  const chartData = data.map(d => ({
    time: d.elapsed_seconds,
    table: (d.table_size_bytes / 1024 / 1024).toFixed(2),
    toast: (d.toast_size_bytes / 1024 / 1024).toFixed(2),
    indexes: (d.indexes_size_bytes / 1024 / 1024).toFixed(2),
    total: (d.total_size_bytes / 1024 / 1024).toFixed(2)
  }))

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
          label={{ value: 'Size (MB)', angle: -90, position: 'insideLeft', fill: '#8b949e' }}
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
        <Line type="monotone" dataKey="table" stroke="#58a6ff" name="Table" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="toast" stroke="#f85149" name="TOAST" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="indexes" stroke="#ffa657" name="Indexes" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="total" stroke="#a371f7" name="Total" strokeWidth={3} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  )
}

export default StorageChart
