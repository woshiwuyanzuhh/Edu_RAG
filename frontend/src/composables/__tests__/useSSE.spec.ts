import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useSSE } from '../useSSE'

// 创建一个可控制的 ReadableStream mock
function createMockStream(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder()
  let index = 0
  return new ReadableStream({
    pull(controller) {
      if (index < chunks.length) {
        controller.enqueue(encoder.encode(chunks[index]))
        index++
      } else {
        controller.close()
      }
    },
  })
}

function mockFetchResponse(chunks: string[], ok = true, status = 200) {
  return {
    ok,
    status,
    body: createMockStream(chunks),
  } as Response
}

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

beforeEach(() => {
  mockFetch.mockReset()
})

describe('useSSE', () => {
  it('初始状态正确', () => {
    const { state } = useSSE()
    expect(state.value).toEqual({
      fullAnswer: '',
      sources: [],
      done: false,
      error: null,
    })
  })

  it('解析普通 token 并拼接到 fullAnswer', async () => {
    mockFetch.mockResolvedValueOnce(
      mockFetchResponse(['data: 你好\ndata: 世界\n']),
    )
    const { state, stream } = useSSE()

    const tokens: string[] = []
    for await (const token of stream('/api/qa/stream', { question: '测试' })) {
      tokens.push(token)
    }

    expect(tokens).toEqual(['你好', '世界'])
    expect(state.value.fullAnswer).toBe('你好世界')
  })

  it('遇到 [DONE] 时设置 done=true', async () => {
    mockFetch.mockResolvedValueOnce(
      mockFetchResponse(['data: 回答\ndata: [DONE]\n']),
    )
    const { state, stream } = useSSE()

    for await (const _ of stream('/api/qa/stream', {})) {
      // consume
    }

    expect(state.value.done).toBe(true)
    expect(state.value.fullAnswer).toBe('回答')
  })

  it('解析 sources JSON 事件', async () => {
    const sourcesEvent = JSON.stringify({
      type: 'sources',
      data: [{ doc_id: 1, chunk_index: 0, score: 0.9, text_preview: '...' }],
    })
    mockFetch.mockResolvedValueOnce(
      mockFetchResponse([`data: 回答\ndata: ${sourcesEvent}\ndata: [DONE]\n`]),
    )
    const { state, stream } = useSSE()

    for await (const _ of stream('/api/qa/stream', {})) {
      // consume
    }

    expect(state.value.sources).toHaveLength(1)
    expect(state.value.sources[0].doc_id).toBe(1)
  })

  it('忽略非 data: 开头的行', async () => {
    mockFetch.mockResolvedValueOnce(
      mockFetchResponse([': comment\ndata: 有效\n\n']),
    )
    const { state, stream } = useSSE()

    for await (const _ of stream('/api/qa/stream', {})) {
      // consume
    }

    expect(state.value.fullAnswer).toBe('有效')
  })

  it('忽略无效 JSON 的 sources 事件', async () => {
    mockFetch.mockResolvedValueOnce(
      mockFetchResponse(['data: 回答\ndata: {invalid json\ndata: [DONE]\n']),
    )
    const { state, stream } = useSSE()

    for await (const _ of stream('/api/qa/stream', {})) {
      // consume
    }

    expect(state.value.sources).toEqual([])
    expect(state.value.fullAnswer).toBe('回答')
  })

  it('HTTP 错误时设置 error 并抛出异常', async () => {
    mockFetch.mockResolvedValueOnce(mockFetchResponse([], false, 500))
    const { state, stream } = useSSE()

    await expect(
      (async () => {
        for await (const _ of stream('/api/qa/stream', {})) {
          // consume
        }
      })(),
    ).rejects.toThrow('SSE error: 500')

    expect(state.value.error).toBe('SSE error: 500')
  })

  it('每次调用 stream 重置状态', async () => {
    // 第一次调用
    mockFetch.mockResolvedValueOnce(
      mockFetchResponse(['data: 第一轮\ndata: [DONE]\n']),
    )
    const { state, stream } = useSSE()

    for await (const _ of stream('/api/qa/stream', {})) {
      // consume
    }
    expect(state.value.fullAnswer).toBe('第一轮')
    expect(state.value.done).toBe(true)

    // 第二次调用应重置
    mockFetch.mockResolvedValueOnce(
      mockFetchResponse(['data: 第二轮\ndata: [DONE]\n']),
    )
    for await (const _ of stream('/api/qa/stream', {})) {
      // consume
    }
    expect(state.value.fullAnswer).toBe('第二轮')
    expect(state.value.done).toBe(true)
  })

  it('跨 chunk 的 SSE 行正确拼接', async () => {
    // 一个完整的 SSE 行被拆分到两个 chunk
    mockFetch.mockResolvedValueOnce(
      mockFetchResponse(['data: 你好', '世界\ndata: [DONE]\n']),
    )
    const { state, stream } = useSSE()

    const tokens: string[] = []
    for await (const token of stream('/api/qa/stream', {})) {
      tokens.push(token)
    }

    expect(tokens).toEqual(['你好世界'])
    expect(state.value.fullAnswer).toBe('你好世界')
  })
})
