import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import CanvasPersistenceFeedback from '../CanvasPersistenceFeedback.vue'
import type { CanvasPersistenceIssue } from '@/composables/useCanvasPersistence'

function issue(
  overrides: Partial<CanvasPersistenceIssue> = {},
): CanvasPersistenceIssue {
  return {
    id: 'workflow:a:persistence:1',
    version: 1,
    kind: 'error',
    source: 'draft',
    summary: 'Changes could not be saved',
    detail: 'Your latest changes are still queued on this canvas.',
    dismissed: false,
    ...overrides,
  }
}

describe('CanvasPersistenceFeedback', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('delays quiet saving feedback so fast autosaves remain silent', async () => {
    vi.useFakeTimers()
    const wrapper = mount(CanvasPersistenceFeedback, {
      props: { state: 'saving', issue: null },
    })

    expect(wrapper.find('[data-testid="canvas-persistence-saving"]').exists()).toBe(false)
    await vi.advanceTimersByTimeAsync(199)
    expect(wrapper.find('[data-testid="canvas-persistence-saving"]').exists()).toBe(false)
    await vi.advanceTimersByTimeAsync(1)

    const saving = wrapper.get('[data-testid="canvas-persistence-saving"]')
    expect(saving.text()).toBe('Saving…')
    expect(saving.attributes('role')).toBe('status')
    expect(saving.attributes('aria-live')).toBe('polite')
    expect(saving.attributes('aria-atomic')).toBe('true')
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  })

  it('returns to silence after saving without a success state or message', async () => {
    vi.useFakeTimers()
    const wrapper = mount(CanvasPersistenceFeedback, {
      props: { state: 'saving', issue: null },
    })

    await vi.advanceTimersByTimeAsync(200)
    await wrapper.setProps({ state: 'idle' })

    expect(wrapper.text()).toBe('')
    expect(wrapper.find('[role="status"]').exists()).toBe(false)
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  })

  it.each(['idle', 'error', 'conflict'] as const)(
    'cancels delayed saving feedback when state changes to %s',
    async (state) => {
      vi.useFakeTimers()
      const wrapper = mount(CanvasPersistenceFeedback, {
        props: { state: 'saving', issue: null },
      })

      await vi.advanceTimersByTimeAsync(100)
      await wrapper.setProps({ state })
      await vi.advanceTimersByTimeAsync(1_000)

      expect(wrapper.find('[data-testid="canvas-persistence-saving"]').exists()).toBe(false)
    },
  )

  it('cancels delayed saving feedback when the component is disposed', () => {
    vi.useFakeTimers()
    const wrapper = mount(CanvasPersistenceFeedback, {
      props: { state: 'saving', issue: null },
    })
    expect(vi.getTimerCount()).toBe(1)

    wrapper.unmount()

    expect(vi.getTimerCount()).toBe(0)
  })

  it('does not auto-dismiss an error, so hover and reading time are unbounded', async () => {
    vi.useFakeTimers()
    const wrapper = mount(CanvasPersistenceFeedback, {
      props: { state: 'error', issue: issue() },
    })

    await vi.advanceTimersByTimeAsync(60_000)

    const alert = wrapper.get('[data-testid="canvas-persistence-issue"]')
    expect(alert.text()).toContain('Changes could not be saved')
    expect(alert.text()).toContain('still queued on this canvas')
    expect(alert.attributes('role')).toBe('alert')
    expect(alert.attributes('aria-live')).toBe('assertive')
    expect(alert.attributes('aria-atomic')).toBe('true')
    expect(alert.attributes('tabindex')).toBe('0')
  })

  it('emits the exact sticky issue id for Retry and Dismiss', async () => {
    const currentIssue = issue()
    const wrapper = mount(CanvasPersistenceFeedback, {
      props: { state: 'error', issue: currentIssue },
    })

    await wrapper.get('[data-testid="canvas-persistence-retry"]').trigger('click')
    await wrapper.get('[data-testid="canvas-persistence-dismiss"]').trigger('click')

    expect(wrapper.emitted('retry')).toEqual([[currentIssue.id]])
    expect(wrapper.emitted('dismiss')).toEqual([[currentIssue.id]])
    expect(
      wrapper.get('[data-testid="canvas-persistence-dismiss"]').attributes('aria-label'),
    ).toBe('Dismiss persistence message')
  })

  it('hides a dismissed issue without pretending persistence succeeded', () => {
    const wrapper = mount(CanvasPersistenceFeedback, {
      props: {
        state: 'error',
        issue: issue({ dismissed: true }),
      },
    })

    expect(wrapper.text()).toBe('')
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(wrapper.find('[role="status"]').exists()).toBe(false)
  })

  it('offers a keyboard-actionable conflict review without a retry loop', async () => {
    const conflict = issue({
      kind: 'conflict',
      summary: 'Workflow changes need attention',
      detail: 'Choose which version to keep before continuing.',
    })
    const wrapper = mount(CanvasPersistenceFeedback, {
      props: {
        state: 'conflict',
        issue: conflict,
        conflictActionLabel: 'Keep my changes',
        conflictSecondaryActionLabel: 'Use latest snapshot',
      },
    })

    const review = wrapper.get('[data-testid="canvas-persistence-resolve-conflict"]')
    const useLatest = wrapper.get('[data-testid="canvas-persistence-use-latest"]')
    expect(review.element.tagName).toBe('BUTTON')
    expect(review.text()).toBe('Keep my changes')
    expect(useLatest.element.tagName).toBe('BUTTON')
    expect(useLatest.text()).toBe('Use latest snapshot')
    expect(wrapper.find('[data-testid="canvas-persistence-retry"]').exists()).toBe(false)
    await useLatest.trigger('click')
    await review.trigger('click')
    expect(wrapper.emitted('use-latest')).toEqual([[conflict.id]])
    expect(wrapper.emitted('resolve-conflict')).toEqual([[conflict.id]])
  })

  it('keeps an opt-in dismissed conflict keyboard-accessible and preserves focus', async () => {
    const conflict = issue({
      kind: 'conflict',
      summary: 'nested-workflow changes need attention',
      detail: 'Choose which nested snapshot to keep.',
    })
    const wrapper = mount(CanvasPersistenceFeedback, {
      attachTo: document.body,
      props: {
        state: 'conflict',
        issue: conflict,
        conflictActionLabel: 'Keep my changes',
        conflictSecondaryActionLabel: 'Use latest snapshot',
        conflictReopenLabel: 'Resolve nested save conflict',
      },
    })

    await wrapper.get('[data-testid="canvas-persistence-dismiss"]').trigger('click')
    expect(wrapper.emitted('dismiss')).toEqual([[conflict.id]])
    await wrapper.setProps({ issue: { ...conflict, dismissed: true } })

    const reopen = wrapper.get('[data-testid="canvas-persistence-reopen-conflict"]')
    expect(reopen.element.tagName).toBe('BUTTON')
    expect(reopen.text()).toContain('Resolve nested save conflict')
    expect(document.activeElement).toBe(reopen.element)
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)

    await reopen.trigger('click')
    expect(wrapper.emitted('reopen-conflict')).toEqual([[conflict.id]])
    await wrapper.setProps({ issue: conflict })

    const alert = wrapper.get('[data-testid="canvas-persistence-issue"]')
    expect(document.activeElement).toBe(alert.element)
    expect(wrapper.find('[data-testid="canvas-persistence-use-latest"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="canvas-persistence-resolve-conflict"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('does not offer a collapsed reminder unless conflict reopening is enabled', () => {
    const wrapper = mount(CanvasPersistenceFeedback, {
      props: {
        state: 'conflict',
        issue: issue({ kind: 'conflict', dismissed: true }),
      },
    })

    expect(wrapper.text()).toBe('')
    expect(
      wrapper.find('[data-testid="canvas-persistence-reopen-conflict"]').exists(),
    ).toBe(false)
  })

  it('disables the collapsed conflict reminder while resolution is pending', () => {
    const wrapper = mount(CanvasPersistenceFeedback, {
      props: {
        state: 'conflict',
        issue: issue({ kind: 'conflict', dismissed: true }),
        conflictReopenLabel: 'Resolve nested save conflict',
        conflictActionsDisabled: true,
      },
    })

    expect(
      wrapper.get('[data-testid="canvas-persistence-reopen-conflict"]').attributes('disabled'),
    ).toBeDefined()
  })
})
