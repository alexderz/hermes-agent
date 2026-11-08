import { expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { ChatImageControls } from "./ChatImageControls";

it("offers a photo/file picker without clipboard support and disables unsafe actions", () => {
  const render = (connected: boolean, busy: boolean, clipboardSupported = false) => renderToStaticMarkup(
    <ChatImageControls connected={connected} busy={busy} clipboardSupported={clipboardSupported} onAttach={() => {}} onPaste={() => {}} />,
  );
  const html = render(true, false);
  expect(html).toContain('type="file"');
  expect(html).toContain('accept="image/*"');
  expect(html).toContain('aria-label="Attach image"');
  expect(html).not.toContain('capture=');
  expect(html).not.toContain('Paste image');
  expect(html).not.toContain('disabled=');
  expect(render(false, false)).toContain('disabled=');
  expect(render(true, true)).toContain('disabled=');
  expect(render(true, false, true)).toContain('Paste image');
});
