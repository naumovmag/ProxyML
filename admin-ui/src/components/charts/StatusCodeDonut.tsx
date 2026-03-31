import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts'
import type { StatusBreakdown } from '@/api/stats'

const COLORS: Record<string, string> = {
  '1xx': 'hsl(0, 0%, 55%)',
  '2xx': 'hsl(142, 71%, 45%)',
  '3xx': 'hsl(221, 83%, 53%)',
  '4xx': 'hsl(38, 92%, 50%)',
  '5xx': 'hsl(0, 84%, 60%)',
}

export default function StatusCodeDonut({ data }: { data: StatusBreakdown[] }) {
  if (data.length === 0) {
    return <div className="flex items-center justify-center h-[300px] text-muted-foreground">No data</div>
  }

  const total = data.reduce((sum, d) => sum + d.count, 0)

  return (
    <ResponsiveContainer width="100%" height={300}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          innerRadius={70}
          outerRadius={110}
          dataKey="count"
          nameKey="group"
          paddingAngle={2}
        >
          {data.map((entry) => (
            <Cell key={entry.group} fill={COLORS[entry.group] || COLORS['1xx']} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{
            backgroundColor: 'hsl(var(--card))',
            border: '1px solid hsl(var(--border))',
            borderRadius: '6px',
            color: 'hsl(var(--card-foreground))',
          }}
          formatter={(value, name) => [`${value} (${((Number(value) / total) * 100).toFixed(1)}%)`, name]}
        />
        <Legend />
        <text x="50%" y="50%" textAnchor="middle" dominantBaseline="middle" fill="hsl(var(--foreground))" fontSize={24} fontWeight="bold">
          {total}
        </text>
      </PieChart>
    </ResponsiveContainer>
  )
}
