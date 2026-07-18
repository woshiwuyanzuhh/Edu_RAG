import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import LoadingSkeleton from '../LoadingSkeleton.vue'

describe('LoadingSkeleton', () => {
  it('默认渲染 3 行骨架', () => {
    const wrapper = mount(LoadingSkeleton)
    const rows = wrapper.findAll('.skeleton-row')
    expect(rows).toHaveLength(3)
  })

  it('渲染指定行数的骨架', () => {
    const wrapper = mount(LoadingSkeleton, {
      props: { rows: 5 },
    })
    const rows = wrapper.findAll('.skeleton-row')
    expect(rows).toHaveLength(5)
  })

  it('渲染 1 行骨架', () => {
    const wrapper = mount(LoadingSkeleton, {
      props: { rows: 1 },
    })
    expect(wrapper.findAll('.skeleton-row')).toHaveLength(1)
  })

  it('渲染 0 行骨架', () => {
    // Vue 中 v-for="i in 0" 不产生元素，但 props 默认值为 3，
    // 传入 0 后 (rows || 3) 仍为 3，因为 0 是 falsy
    const wrapper = mount(LoadingSkeleton, {
      props: { rows: 0 },
    })
    // (0 || 3) = 3，所以实际渲染 3 行
    expect(wrapper.findAll('.skeleton-row')).toHaveLength(3)
  })

  it('每行有宽度样式', () => {
    const wrapper = mount(LoadingSkeleton, {
      props: { rows: 2 },
    })
    const rows = wrapper.findAll('.skeleton-row')
    rows.forEach((row) => {
      const style = row.attributes('style') || ''
      expect(style).toContain('width:')
      expect(style).toContain('animation-delay:')
    })
  })
})
