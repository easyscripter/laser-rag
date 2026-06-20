import { api } from './client'

export interface HealthResponse {
  status: string
  app: string
  version: string
}

export async function fetchHealth(): Promise<HealthResponse> {
  const { data } = await api.get<HealthResponse>('/health')
  return data
}
