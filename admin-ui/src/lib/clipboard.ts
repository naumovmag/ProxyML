import copy from 'copy-to-clipboard'

export async function copyToClipboard(text: string): Promise<boolean> {
  if (window.isSecureContext && navigator?.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch {
      // fall through to legacy path
    }
  }

  try {
    return copy(text, { format: 'text/plain' })
  } catch {
    return false
  }
}
