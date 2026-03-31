import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import type { ServiceStats } from '@/api/stats'

const SUCCESS_COLOR = 'hsl(142, 71%, 45%)'
const WARNING_COLOR = 'hsl(38, 92%, 50%)'
const ERROR_COLOR = 'hsl(0, 84%, 60%)'

function getBarColor(errorRate: number) {
  if (errorRate < 5) return SUCCESS_COLOR
  if (errorRate < 20) return WARNING_COLOR
  return ERROR_COLOR
}

export default function ServiceBarChart({ data }: { data: ServiceStats[] }) {
  if (data.length === 0) {
    return <div className="flex items-center justify-center h-[200px] text-muted-foreground">No data</div>
  }

  const chartData = data.map((s) => ({
    ...s,
    errorRate: s.request_count > 0 ? (s.error_count / s.request_count) * 100 : 0,
  }))

  return (
    <ResponsiveContainer width="100%" height={Math.max(200, data.length * 40 + 40)}>
      <BarChart data={chartData} layout="vertical" margin={{ left: 10, right: 30 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" horizontal={false} />
        <XAxis type="number" stroke="hsl(var(--muted-foreground))" fontSize={12} tickLine={false} allowDecimals={false} />
        <YAxis
          type="category"
          dataKey="service_slug"
          stroke="hsl(var(--muted-foreground))"
          fontSize={12}
          tickLine={false}
          width={120}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: 'hsl(var(--card))',
            border: '1px solid hsl(var(--border))',
            borderRadius: '6px',
            color: 'hsl(var(--card-foreground))',
          }}
          formatter={(_v, _n, props) => {
            const d = (props as any).payload
            return [`${d.request_count} req, ${d.error_count} err, ${d.avg_duration_ms}ms avg`, d.service_slug]
          }}
        />
        <Bar dataKey="request_count" radius={[0, 4, 4, 0]} name="Requests">
          {chartData.map((entry) => (
            <Cell key={entry.service_slug} fill={getBarColor(entry.errorRate)} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
