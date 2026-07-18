import { describe, it, expect, vi, beforeEach } from 'vitest'
import { get, post, put, del, upload, ApiError } from '../client'

// Mock global fetch
const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

function mockResponse(data: any, ok = true, status = 200) {
  return {
    ok,
    status,
    json: async () => data,
  } as Response
}

beforeEach(() => {
  mockFetch.mockReset()
})

describe('API client', () => {
  describe('get', () => {
    it('发送 GET 请求并返回 data', async () => {
      mockFetch.mockResolvedValueOnce(
        mockResponse({ success: true, message: 'ok', data: { id: 1 } }),
      )
      const result = await get('/kb')
      expect(result).toEqual({ id: 1 })
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/kb',
        expect.objectContaining({ method: 'GET' }),
      )
    })

    it('不包含 body', async () => {
      mockFetch.mockResolvedValueOnce(
        mockResponse({ success: true, message: 'ok', data: [] }),
      )
      await get('/kb')
      const opts = mockFetch.mock.calls[0][1]
      expect(opts.body).toBeUndefined()
    })
  })

  describe('post', () => {
    it('发送 POST 请求并序列化 JSON body', async () => {
      mockFetch.mockResolvedValueOnce(
        mockResponse({ success: true, message: 'ok', data: { id: 5 } }),
      )
      const result = await post('/kb', { name: '测试库' })
      expect(result).toEqual({ id: 5 })
      const opts = mockFetch.mock.calls[0][1]
      expect(opts.method).toBe('POST')
      expect(opts.headers['Content-Type']).toBe('application/json')
      expect(opts.body).toBe(JSON.stringify({ name: '测试库' }))
    })

    it('无 body 时不设置 Content-Type', async () => {
      mockFetch.mockResolvedValueOnce(
        mockResponse({ success: true, message: 'ok', data: null }),
      )
      await post('/kb')
      const opts = mockFetch.mock.calls[0][1]
      expect(opts.body).toBeUndefined()
    })
  })

  describe('put', () => {
    it('发送 PUT 请求', async () => {
      mockFetch.mockResolvedValueOnce(
        mockResponse({ success: true, message: 'ok', data: null }),
      )
      await put('/kb/1', { name: '更新' })
      const opts = mockFetch.mock.calls[0][1]
      expect(opts.method).toBe('PUT')
      expect(opts.body).toBe(JSON.stringify({ name: '更新' }))
    })
  })

  describe('del', () => {
    it('发送 DELETE 请求', async () => {
      mockFetch.mockResolvedValueOnce(
        mockResponse({ success: true, message: 'ok', data: null }),
      )
      await del('/kb/1')
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/kb/1',
        expect.objectContaining({ method: 'DELETE' }),
      )
    })
  })

  describe('upload', () => {
    it('发送 FormData 不设置 Content-Type（浏览器自动加 boundary）', async () => {
      mockFetch.mockResolvedValueOnce(
        mockResponse({ success: true, message: 'ok', data: { id: 1 } }),
      )
      const formData = new FormData()
      formData.append('file', new Blob(['test']), 'test.txt')
      await upload('/documents/upload', formData)
      const opts = mockFetch.mock.calls[0][1]
      expect(opts.method).toBe('POST')
      expect(opts.body).toBe(formData)
      expect(opts.headers['Content-Type']).toBeUndefined()
    })
  })

  describe('错误处理', () => {
    it('HTTP 错误时抛出 ApiError（带状态码）', async () => {
      mockFetch.mockResolvedValueOnce(
        mockResponse({ message: 'Not Found' }, false, 404),
      )
      try {
        await get('/kb/999')
        expect.fail('应该抛出 ApiError')
      } catch (e) {
        expect(e).toBeInstanceOf(ApiError)
        expect((e as ApiError).status).toBe(404)
      }
    })

    it('success=false 时抛出 ApiError', async () => {
      mockFetch.mockResolvedValueOnce(
        mockResponse({ success: false, message: '参数错误', data: null }),
      )
      await expect(get('/kb')).rejects.toThrow('参数错误')
    })

    it('HTTP 错误且响应非 JSON 时使用默认消息', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => { throw new Error('not json') },
      } as Response)
      await expect(get('/kb')).rejects.toThrow('HTTP 500')
    })
  })
})
