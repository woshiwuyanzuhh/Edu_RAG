import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { h } from 'vue'
import PageHeader from '../PageHeader.vue'

describe('PageHeader', () => {
  it('渲染标题', () => {
    const wrapper = mount(PageHeader, {
      props: { title: '智能问答' },
    })
    expect(wrapper.find('.page-header-title').text()).toBe('智能问答')
  })

  it('渲染描述（当传入 description）', () => {
    const wrapper = mount(PageHeader, {
      props: { title: '智能问答', description: '基于知识库的问答系统' },
    })
    expect(wrapper.find('.page-header-desc').text()).toBe('基于知识库的问答系统')
  })

  it('不渲染描述（当未传 description）', () => {
    const wrapper = mount(PageHeader, {
      props: { title: '智能问答' },
    })
    expect(wrapper.find('.page-header-desc').exists()).toBe(false)
  })

  it('渲染图标（当传入 icon）', () => {
    const wrapper = mount(PageHeader, {
      props: { title: '智能问答', icon: h('span', { class: 'test-icon' }) },
    })
    expect(wrapper.find('.page-header-icon').exists()).toBe(true)
  })

  it('不渲染图标（当未传 icon）', () => {
    const wrapper = mount(PageHeader, {
      props: { title: '智能问答' },
    })
    expect(wrapper.find('.page-header-icon').exists()).toBe(false)
  })

  it('渲染 extra 插槽内容', () => {
    const wrapper = mount(PageHeader, {
      props: { title: '智能问答' },
      slots: {
        extra: '<button class="test-btn">操作</button>',
      },
    })
    expect(wrapper.find('.page-header-extra .test-btn').exists()).toBe(true)
  })
})
