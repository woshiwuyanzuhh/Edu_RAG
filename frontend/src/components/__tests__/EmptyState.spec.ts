import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { Button } from 'ant-design-vue'
import EmptyState from '../EmptyState.vue'

const globalStubs = {
  components: { 'a-button': Button },
}

describe('EmptyState', () => {
  // 所有测试都注册 a-button，避免 Vue warn
  const mountOpts = (props = {}) => ({ props, global: globalStubs })

  it('渲染标题', () => {
    const wrapper = mount(EmptyState, mountOpts({ title: '暂无数据' }))
    expect(wrapper.find('.empty-state-title').text()).toBe('暂无数据')
  })

  it('渲染描述（当传入 description）', () => {
    const wrapper = mount(EmptyState, mountOpts({ title: '暂无数据', description: '请上传文档' }))
    expect(wrapper.find('.empty-state-desc').text()).toBe('请上传文档')
  })

  it('不渲染描述（当未传 description）', () => {
    const wrapper = mount(EmptyState, mountOpts({ title: '暂无数据' }))
    expect(wrapper.find('.empty-state-desc').exists()).toBe(false)
  })

  it('渲染按钮并触发 action 事件（当传入 actionText）', async () => {
    const wrapper = mount(EmptyState, mountOpts({ title: '暂无数据', actionText: '上传文档' }))
    const button = wrapper.find('button')
    expect(button.text()).toContain('上传文档')
    await button.trigger('click')
    expect(wrapper.emitted('action')).toHaveLength(1)
  })

  it('不渲染按钮（当未传 actionText）', () => {
    const wrapper = mount(EmptyState, mountOpts({ title: '暂无数据' }))
    expect(wrapper.find('button').exists()).toBe(false)
  })

  it('默认使用 robot 图标', () => {
    const wrapper = mount(EmptyState, mountOpts({ title: '暂无数据' }))
    expect(wrapper.find('.empty-state-icon').exists()).toBe(true)
  })

  it('支持不同图标类型', () => {
    const wrapper = mount(EmptyState, mountOpts({ title: '暂无数据', type: 'search' }))
    expect(wrapper.find('.empty-state-icon').exists()).toBe(true)
  })
})
