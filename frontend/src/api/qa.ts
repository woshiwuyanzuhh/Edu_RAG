import { post } from './client'
import type { QARequest, QAResponse } from './types'

export function askQuestion(data: QARequest) {
  return post<QAResponse>('/qa', data)
}

export async function* askQuestionStream(data: QARequest): AsyncGenerator<string, void, unknown> {
  const resp = await fetch('/api/qa/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })

  if (!resp.ok) {
    throw new Error(`SSE error: ${resp.status}`)
  }

  const reader = resp.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const token = line.slice(6)
        if (token === '[DONE]') return
        // Skip source JSON events — handled separately
        if (token.startsWith('{')) continue
        yield token
      }
    }
  }
}
