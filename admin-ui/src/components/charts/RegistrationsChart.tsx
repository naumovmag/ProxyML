import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

const PRIMARY_COLOR = 'hsl(221, 83%, 53%)'

export default function RegistrationsChart({ data, hours }: { data: { bucket: string; count: number }[]; hours: number }) {
  if (data.length === 0) {
    return <div className="flex items-center justify-center h-[250px] text-muted-foreground">No data</div>
  }

  const formatX = (bucket: string) => {
    const d = new Date(bucket)
    if (hours <= 168) return d.toLocaleDateString([], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
    return d.toLocaleDateString([], { day: 'numeric', month: 'short' })
  }

  return (
    <ResponsiveContainer width="100%" height={250}>
      <AreaChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis dataKey="bucket" tickFormatter={formatX} stroke="hsl(var(--muted-foreground))" fontSize={12} tickLine={false} />
        <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} tickLine={false} allowDecimals={false} />
        <Tooltip
          contentStyle={{
            backgroundColor: 'hsl(var(--card))',
            border: '1px solid hsl(var(--border))',
            borderRadius: '6px',
            color: 'hsl(var(--card-foreground))',
          }}
          labelFormatter={(v) => new Date(v).toLocaleString()}
          formatter={(value) => [`${value} users`, 'Registrations']}
        />
        <Area type="monotone" dataKey="count" stroke={PRIMARY_COLOR} fill={PRIMARY_COLOR} fillOpacity={0.3} name="Registrations" />
      </AreaChart>
    </ResponsiveContainer>
  )
}
