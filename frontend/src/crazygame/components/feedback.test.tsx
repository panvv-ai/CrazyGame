import {
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react'
import { beforeAll, describe, expect, it } from 'vitest'

import i18n from '../i18n'
import { ToastProvider, useToast } from './feedback'

function ToastTrigger() {
  const { notify } = useToast()
  return (
    <button type="button" onClick={() => notify('Preferences saved', 'success')}>
      Notify
    </button>
  )
}

describe('ToastProvider', () => {
  beforeAll(async () => {
    await i18n.changeLanguage('en-US')
  })

  it('announces a notification and allows manual dismissal', async () => {
    render(
      <ToastProvider>
        <ToastTrigger />
      </ToastProvider>
    )

    fireEvent.click(screen.getByRole('button', { name: 'Notify' }))
    expect(screen.getByRole('status')).toHaveTextContent('Preferences saved')

    fireEvent.click(screen.getByRole('button', { name: 'Dismiss notification' }))
    await waitFor(() => {
      expect(screen.queryByRole('status')).not.toBeInTheDocument()
    })
  })
})
