import axios, { type AxiosInstance } from 'axios'

const ACCESS_TOKEN_KEY = 'accessToken'

class ApiClient {
  readonly axios: AxiosInstance

  constructor() {
    this.axios = axios.create({
      baseURL: import.meta.env.VITE_API_BASE_URL ?? '/api/v1',
      headers: { 'Content-Type': 'application/json' },
    })

    this.axios.interceptors.request.use((config) => {
      const token = this.getAccessToken()
      if (token) config.headers.Authorization = `Bearer ${token}`
      return config
    })

    this.axios.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          this.setAccessToken(null)
          // Auth flow (redirect to /login) is wired in Phase 5/8.
        }
        return Promise.reject(error)
      },
    )
  }

  getAccessToken(): string | null {
    return localStorage.getItem(ACCESS_TOKEN_KEY)
  }

  setAccessToken(token: string | null): void {
    if (token) localStorage.setItem(ACCESS_TOKEN_KEY, token)
    else localStorage.removeItem(ACCESS_TOKEN_KEY)
  }
}

export const apiClient = new ApiClient()
export const api = apiClient.axios
