import type { APIResponse } from './types'

const BASE = '/api'

class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(method: string, path: string, body?: any): Promise<T> {
  const opts: RequestInit = {
    method,
    headers: {} as Record<string, string>,
  }

  if (body !== undefined && !(body instanceof FormData)) {
    opts.headers!['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(body)
  } else if (body instanceof FormData) {
    opts.body = body
  }

  const resp = await fetch(`${BASE}${path}`, opts)

  if (!resp.ok) {
    let msg = `HTTP ${resp.status}`
    try {
      const err = await resp.json()
      msg = err.message || msg
    } catch {}
    throw new ApiError(msg, resp.status)
  }

  const json: APIResponse<T> = await resp.json()

  if (!json.success) {
    throw new ApiError(json.message || '请求失败', 400)
  }

  return json.data
}

export function get<T>(path: string): Promise<T> {
  return request<T>('GET', path)
}

export function post<T>(path: string, body?: any): Promise<T> {
  return request<T>('POST', path, body)
}

export function put<T>(path: string, body?: any): Promise<T> {
  return request<T>('PUT', path, body)
}

export function del<T>(path: string): Promise<T> {
  return request<T>('DELETE', path)
}

export function upload<T>(path: string, formData: FormData): Promise<T> {
  return request<T>('POST', path, formData)
}

export { ApiError }
