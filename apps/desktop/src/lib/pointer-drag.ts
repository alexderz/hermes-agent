/** Track a drag on window so it continues outside its starting element.
 *  Cancellation tears down without committing the release action. */
export function startPointerDrag(
  onMove: (event: PointerEvent) => void,
  onEnd?: (event: PointerEvent) => void,
  onCancel?: (event: PointerEvent) => void
): () => void {
  const move = (event: PointerEvent) => onMove(event)

  const dispose = () => {
    window.removeEventListener('pointermove', move, true)
    window.removeEventListener('pointerup', up, true)
    window.removeEventListener('pointercancel', cancel, true)
  }

  const up = (event: PointerEvent) => {
    dispose()
    onEnd?.(event)
  }

  const cancel = (event: PointerEvent) => {
    dispose()
    onCancel?.(event)
  }

  window.addEventListener('pointermove', move, true)
  window.addEventListener('pointerup', up, true)
  window.addEventListener('pointercancel', cancel, true)

  return dispose
}
