import { useQuery } from '@tanstack/react-query'
import { fetchHealth } from '@/api/health'

function App() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
  })

  const status = isLoading
    ? { label: 'проверка…', color: 'bg-amber-400' }
    : isError
      ? { label: 'нет связи с API', color: 'bg-red-500' }
      : { label: `онлайн · v${data?.version}`, color: 'bg-emerald-500' }

  return (
    <div className="flex min-h-full items-center justify-center bg-neutral-50 text-neutral-900">
      <div className="rounded-2xl border border-neutral-200 bg-white p-10 text-center shadow-sm">
        <h1 className="text-3xl font-semibold tracking-tight">LaserRAG</h1>
        <p className="mt-2 text-sm text-neutral-500">
          RAG-ассистент по научной литературе о лазерной наплавке
        </p>
        <div className="mt-6 inline-flex items-center gap-2 rounded-full bg-neutral-100 px-4 py-2 text-sm">
          <span className={`h-2.5 w-2.5 rounded-full ${status.color}`} />
          <span>Backend: {status.label}</span>
        </div>
      </div>
    </div>
  )
}

export default App
