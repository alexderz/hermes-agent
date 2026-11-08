interface TouchScrollTerminal {
  rows: number;
  buffer: { active: { baseY: number; viewportY: number } };
  scrollLines(lines: number): void;
}

export function attachTerminalTouchScroll(
  screen: HTMLElement,
  terminal: TouchScrollTerminal,
): () => void {
  const view = screen.ownerDocument.defaultView!;
  let frame: number | null = null;
  let remainder = 0;
  let gesture: {
    id: number;
    startX: number;
    startY: number;
    lastY: number;
    lastTime: number;
    velocity: number;
    scrolling: boolean;
  } | null = null;

  const stopMomentum = () => {
    if (frame !== null) view.cancelAnimationFrame(frame);
    frame = null;
  };
  const reset = () => { gesture = null; };
  const cancel = () => { stopMomentum(); reset(); };
  const scrollPixels = (pixels: number): boolean => {
    const cellHeight = screen.getBoundingClientRect().height / terminal.rows;
    if (cellHeight <= 0) return false;
    remainder += pixels / cellHeight;
    const lines = Math.trunc(remainder);
    if (!lines) return true;
    const before = terminal.buffer.active.viewportY;
    terminal.scrollLines(lines);
    remainder -= lines;
    return terminal.buffer.active.viewportY !== before;
  };
  const start = (event: TouchEvent) => {
    stopMomentum();
    if (event.touches.length !== 1) return reset();
    const touch = event.touches[0];
    remainder = 0;
    gesture = {
      id: touch.identifier,
      startX: touch.clientX,
      startY: touch.clientY,
      lastY: touch.clientY,
      lastTime: view.performance.now(),
      velocity: 0,
      scrolling: false,
    };
  };
  const move = (event: TouchEvent) => {
    if (!gesture) return;
    const touch = event.touches[0];
    if (event.touches.length !== 1 || touch.identifier !== gesture.id) return cancel();
    if (!gesture.scrolling) {
      const dx = Math.abs(touch.clientX - gesture.startX);
      const dy = Math.abs(touch.clientY - gesture.startY);
      if (Math.max(dx, dy) < 6) return;
      if (dx >= dy) return reset();
      gesture.scrolling = true;
    }
    const now = view.performance.now();
    const pixels = gesture.lastY - touch.clientY;
    // At the top or bottom of the scrollback, leave the swipe to the page so
    // the dashboard can still move above the software keyboard.
    const { baseY, viewportY } = terminal.buffer.active;
    if ((pixels < 0 && viewportY <= 0) || (pixels > 0 && viewportY >= baseY)) {
      gesture.lastY = touch.clientY;
      gesture.lastTime = now;
      gesture.velocity = 0;
      remainder = 0;
      return;
    }
    // xterm 6 uses a virtual viewport, not a native overflowing element.
    // Consume only vertical swipes; a tap must still focus the composer.
    event.preventDefault();
    event.stopPropagation();
    const elapsed = now - gesture.lastTime;
    if (elapsed > 0) {
      const speed = Math.max(-3, Math.min(3, pixels / elapsed));
      gesture.velocity = elapsed > 100 ? 0 : speed * 0.8 + gesture.velocity * 0.2;
    }
    gesture.lastY = touch.clientY;
    gesture.lastTime = now;
    if (!scrollPixels(pixels)) gesture.velocity = 0;
  };
  const end = (event: TouchEvent) => {
    const released = gesture;
    reset();
    let lastTime = view.performance.now();
    // Whole-row scrolling looks jerky below one row per 80ms. Drop that
    // sparse tail rather than waiting for fractional movement to add up.
    const minimumVelocity = screen.getBoundingClientRect().height / terminal.rows / 80;
    if (!released?.scrolling || event.touches.length ||
        lastTime - released.lastTime > 80 || Math.abs(released.velocity) < minimumVelocity) return;
    let velocity = released.velocity;
    const coast = (now: number) => {
      frame = null;
      // Integrate exponential friction so speed is independent of frame rate.
      const elapsed = Math.min(64, now - lastTime);
      lastTime = now;
      const decay = Math.exp(-elapsed / 325);
      if (Math.abs(velocity * decay) < minimumVelocity) return;
      const moved = scrollPixels(velocity * 325 * (1 - decay));
      velocity *= decay;
      if (moved) frame = view.requestAnimationFrame(coast);
    };
    frame = view.requestAnimationFrame(coast);
  };

  screen.addEventListener("touchstart", start, { passive: true });
  screen.addEventListener("touchmove", move, { passive: false });
  screen.addEventListener("touchend", end);
  screen.addEventListener("touchcancel", cancel);
  screen.addEventListener("wheel", stopMomentum, { passive: true });
  screen.addEventListener("keydown", stopMomentum);
  return () => {
    cancel();
    screen.removeEventListener("touchstart", start);
    screen.removeEventListener("touchmove", move);
    screen.removeEventListener("touchend", end);
    screen.removeEventListener("touchcancel", cancel);
    screen.removeEventListener("wheel", stopMomentum);
    screen.removeEventListener("keydown", stopMomentum);
  };
}
