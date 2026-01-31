import React from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Area, AreaChart } from 'recharts'

function DeadTupleChart({ data }) {
  const chartData = data.map(d => ({
    time: d.elapsed_seconds,
    live: d.n_live_tup,
    dead: d.n_dead_tup,
    deadRatio: ((d.n_dead_tup / (d.n_live_tup + d.n_dead_tup)) * 100).toFixed(1)
  }))

  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" stroke="#30363d" />
        <XAxis 
          dataKey="time" 
          stroke="#8b949e"
          label={{ value: 'Time (seconds)', position: 'insideBottom', offset: -5, fill: '#8b949e' }}
        />
        <YAxis 
          stroke="#8b949e"
          label={{ value: 'Tuple Count', angle: -90, position: 'insideLeft', fill: '#8b949e' }}
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
        <Area type="monotone" dataKey="live" stackId="1" stroke="#3fb950" fill="#3fb950" name="Live Tuples" fillOpacity={0.6} />
        <Area type="monotone" dataKey="dead" stackId="1" stroke="#f85149" fill="#f85149" name="Dead Tuples" fillOpacity={0.6} />
      </AreaChart>
    </ResponsiveContainer>
  )
}

export default DeadTupleChart
