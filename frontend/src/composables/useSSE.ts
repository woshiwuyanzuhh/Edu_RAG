import { ref } from 'vue'

export interface SSEState {
  fullAnswer: string
  sources: any[]
  done: boolean
  error: string | null
}

export function useSSE() {
  const state = ref<SSEState>({
    fullAnswer: '',
    sources: [],
    done: false,
    error: null,
  })

  async function* stream(endpoint: string, body: object): AsyncGenerator<string, SSEState, unknown> {
    state.value = { fullAnswer: '', sources: [], done: false, error: null }

    const resp = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })

    if (!resp.ok) {
      state.value.error = `SSE error: ${resp.status}`
      throw new Error(state.value.error)
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
        if (!line.startsWith('data: ')) continue
        const token = line.slice(6)

        if (token === '[DONE]') {
          state.value.done = true
          continue
        }

        // Parse source JSON
        if (token.startsWith('{')) {
          try {
            const parsed = JSON.parse(token)
            if (parsed.type === 'sources' && parsed.data) {
              state.value.sources = parsed.data
            }
          } catch { /* skip */ }
          continue
        }

        state.value.fullAnswer += token
        yield token
      }
    }

    return state.value
  }

  return {
    state,
    stream,
  }
}
