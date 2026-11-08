import { describe, expect, it } from "vitest";
import { attachTerminalTouchScroll } from "./terminal-touch-scroll";

function fixture() {
  let now = 0;
  let frameId = 0;
  const frames = new Map<number, FrameRequestCallback>();
  const view = {
    performance: { now: () => now },
    requestAnimationFrame(callback: FrameRequestCallback) {
      frames.set(++frameId, callback);
      return frameId;
    },
    cancelAnimationFrame(id: number) { frames.delete(id); },
  };
  const advance = (ms: number) => {
    now += ms;
    const pending = [...frames.values()];
    frames.clear();
    pending.forEach(callback => callback(now));
  };
  const screen = Object.assign(new EventTarget(), {
    ownerDocument: { defaultView: view },
    getBoundingClientRect: () => ({ height: 200 }),
  });
  const terminal = {
    rows: 10,
    viewportY: 50,
    baseY: 200,
    get buffer() { return { active: { baseY: this.baseY, viewportY: this.viewportY } }; },
    scrollLines(lines: number) { this.viewportY = Math.max(0, Math.min(200, this.viewportY + lines)); },
  };
  const cleanup = attachTerminalTouchScroll(screen as unknown as HTMLElement, terminal);
  const touch = (type: string, points: Array<[number, number]>) => {
    const event = Object.assign(new Event(type, { cancelable: true }), {
      touches: points.map(([clientX, clientY], identifier) => ({ identifier, clientX, clientY })),
    });
    screen.dispatchEvent(event);
    return event;
  };
  return { terminal, touch, cleanup, advance, frames, screen };
}

describe("terminal touch scroll", () => {
  it("stops a slow drag on release instead of adding delayed row jumps", () => {
    const { terminal, touch, advance, frames } = fixture();
    touch("touchstart", [[100, 100]]);
    advance(50);
    touch("touchmove", [[100, 110]]);
    advance(50);
    touch("touchmove", [[100, 120]]);
    const released = terminal.viewportY;
    touch("touchend", []);
    expect(frames.size).toBe(0);
    for (let i = 0; i < 100; i++) advance(16);
    expect(terminal.viewportY).toBe(released);
  });
  it("keeps fast flick momentum but cuts off the sparse low-speed tail", () => {
    const { terminal, touch, advance, frames } = fixture();
    terminal.viewportY = 150;
    touch("touchstart", [[100, 100]]);
    advance(20);
    touch("touchmove", [[100, 140]]);
    touch("touchend", []);
    const released = terminal.viewportY;
    advance(16);
    expect(terminal.viewportY).toBeLessThan(released);
    for (let i = 0; i < 50; i++) advance(16);
    expect(terminal.viewportY).toBeGreaterThan(0);
    expect(frames.size).toBe(0);
    const stopped = terminal.viewportY;
    advance(1000);
    expect(terminal.viewportY).toBe(stopped);
  });
  it("cancels coasting on user input or disposal and does not fling after holding still", () => {
    for (const interruption of ["touchstart", "touchcancel", "wheel", "keydown", "cleanup", "pause"]) {
      const { terminal, touch, advance, frames, screen, cleanup } = fixture();
      touch("touchstart", [[100, 140]]);
      advance(20);
      touch("touchmove", [[100, 100]]);
      if (interruption === "pause") advance(150);
      touch("touchend", []);
      if (interruption !== "pause") {
        expect(frames.size).toBe(1);
        if (interruption === "cleanup") cleanup();
        else if (interruption.startsWith("touch")) touch(interruption, interruption === "touchstart" ? [[100, 100]] : []);
        else screen.dispatchEvent(new Event(interruption));
      }
      expect(frames.size).toBe(0);
      const stopped = terminal.viewportY;
      advance(1000);
      expect(terminal.viewportY).toBe(stopped);
      cleanup();
    }
  });
  it("coasts after a flick, decays to rest, and stops at a scrollback boundary", () => {
    const { terminal, touch, advance, frames } = fixture();
    touch("touchstart", [[100, 100]]);
    advance(20);
    touch("touchmove", [[100, 140]]);
    touch("touchend", []);
    const released = terminal.viewportY;
    advance(16);
    expect(terminal.viewportY).toBeLessThan(released);
    for (let i = 0; i < 200; i++) advance(16);
    expect(frames.size).toBe(0);
    const resting = terminal.viewportY;
    advance(1000);
    expect(terminal.viewportY).toBe(resting);

    terminal.viewportY = 2;
    touch("touchstart", [[100, 100]]);
    advance(20);
    touch("touchmove", [[100, 120]]);
    touch("touchend", []);
    for (let i = 0; i < 10; i++) advance(16);
    expect(terminal.viewportY).toBe(0);
    expect(frames.size).toBe(0);
  });
  it("moves history in both directions and accumulates sub-row movement", () => {
    const { terminal, touch } = fixture();
    touch("touchstart", [[100, 100]]);
    expect(touch("touchmove", [[100, 110]]).defaultPrevented).toBe(true);
    expect(terminal.viewportY).toBe(50);
    touch("touchmove", [[100, 121]]);
    expect(terminal.viewportY).toBe(49);
    touch("touchmove", [[100, 161]]);
    expect(terminal.viewportY).toBe(47);
    touch("touchend", []);
    touch("touchstart", [[100, 160]]);
    touch("touchmove", [[100, 100]]);
    expect(terminal.viewportY).toBe(50);
  });

  it("leaves taps, horizontal gestures and pinch alone, and removes listeners on cleanup", () => {
    const { terminal, touch, cleanup } = fixture();
    expect(touch("touchstart", [[100, 100]]).defaultPrevented).toBe(false);
    expect(touch("touchmove", [[101, 101]]).defaultPrevented).toBe(false);
    expect(touch("touchmove", [[140, 102]]).defaultPrevented).toBe(false);
    touch("touchend", []);
    touch("touchstart", [[100, 100]]);
    expect(touch("touchmove", [[100, 150], [150, 150]]).defaultPrevented).toBe(false);
    expect(touch("touchmove", [[100, 180]]).defaultPrevented).toBe(false);
    touch("touchcancel", []);
    cleanup();
    touch("touchstart", [[100, 100]]);
    expect(touch("touchmove", [[100, 180]]).defaultPrevented).toBe(false);
    expect(terminal.viewportY).toBe(50);
  });
  it("leaves the swipe to the page at the top or bottom of the scrollback", () => {
    for (const [start, from, to] of [[0, 100, 140], [200, 140, 100]] as const) {
      const { terminal, touch } = fixture();
      terminal.viewportY = start;
      touch("touchstart", [[100, from]]);
      const move = touch("touchmove", [[100, to]]);
      expect(move.defaultPrevented).toBe(false);
      expect(terminal.viewportY).toBe(start);
    }
  });
});
