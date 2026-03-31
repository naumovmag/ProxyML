import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import type { TimeseriesPoint } from '@/api/stats'

const PRIMARY_COLOR = 'hsl(221, 83%, 53%)'

function formatXAxis(bucket: string, hours: number) {
  const d = new Date(bucket)
  if (hours <= 6) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  if (hours <= 168) return d.toLocaleDateString([], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
  return d.toLocaleDateString([], { day: 'numeric', month: 'short' })
}

export default function LatencyOverTimeChart({ data, hours }: { data: TimeseriesPoint[]; hours: number }) {
  if (data.length === 0) {
    return <div className="flex items-center justify-center h-[300px] text-muted-foreground">No data</div>
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis
          dataKey="bucket"
          tickFormatter={(v) => formatXAxis(v, hours)}
          stroke="hsl(var(--muted-foreground))"
          fontSize={12}
          tickLine={false}
        />
        <YAxis
          stroke="hsl(var(--muted-foreground))"
          fontSize={12}
          tickLine={false}
          tickFormatter={(v) => `${v}ms`}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: 'hsl(var(--card))',
            border: '1px solid hsl(var(--border))',
            borderRadius: '6px',
            color: 'hsl(var(--card-foreground))',
          }}
          labelFormatter={(v) => new Date(v).toLocaleString()}
          formatter={(value) => [`${value} ms`, 'Avg Latency']}
        />
        <Area type="monotone" dataKey="avg_duration_ms" stroke={PRIMARY_COLOR} fill={PRIMARY_COLOR} fillOpacity={0.3} name="Avg Latency" />
      </AreaChart>
    </ResponsiveContainer>
  )
}
