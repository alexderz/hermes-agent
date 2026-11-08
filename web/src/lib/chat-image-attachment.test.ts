import { expect, it, vi } from "vitest";
import * as attachments from "./chatImagePaste";

it("reads only clipboard images and explains missing images or denied permission", async () => {
  expect(attachments.readClipboardImages).toBeTypeOf("function");
  const blob = new Blob(["png"], { type: "image/png" });
  const read = async () => [{ types: ["text/plain", "image/png"], getType: async () => blob }];
  const files = await attachments.readClipboardImages({ read } as unknown as Clipboard);
  expect(files[0].type).toBe("image/png");
  expect(await files[0].text()).toBe("png");
  await expect(attachments.readClipboardImages(undefined)).rejects.toThrow("HTTPS");
  await expect(attachments.readClipboardImages({ read: async () => [] } as unknown as Clipboard)).rejects.toThrow("No image");
  await expect(attachments.readClipboardImages({ read: async () => { throw new Error("denied"); } } as unknown as Clipboard)).rejects.toThrow("permission");
});

it("attaches an uploaded path as a paste without submitting or replacing a drafted prompt", async () => {
  const frames: string[] = [];
  const socket = { readyState: 1, send: (data: string) => frames.push(data) };
  const file = new File(["image"], "photo.png", { type: "image/png" });
  const controller = attachments.createChatImageAttachment({
    socket: () => socket,
    active: () => true,
    upload: async () => ({ path: "/images/photo.png" }),
    busy: () => {},
  });
  await controller.attach([file]);
  expect(frames).toEqual(["\x1b[200~/images/photo.png\x1b[201~"]);
  expect(frames.join("")).not.toContain("\r");
});

it("fails closed during disconnects, concurrent uploads and disposal without touching the prompt", async () => {
  const frames: string[] = [];
  let socket = { readyState: 3, send: (data: string) => frames.push(data) };
  let resolveUpload!: (value: { path: string }) => void;
  const upload = vi.fn(() => socket.readyState !== 1
    ? Promise.resolve({ path: "/images/photo.png" })
    : new Promise<{ path: string }>(resolve => { resolveUpload = resolve; }));
  const busy = vi.fn();
  const controller = attachments.createChatImageAttachment({ socket: () => socket, active: () => true, upload, busy });
  const file = new File(["image"], "photo.png", { type: "image/png" });
  await expect(controller.attach([file])).rejects.toThrow("connected");
  expect(upload).not.toHaveBeenCalled();
  socket.readyState = 1;
  const pending = controller.attach([file]);
  await expect(controller.attach([file])).rejects.toThrow("progress");
  socket = { readyState: 1, send: (data: string) => frames.push(data) };
  resolveUpload({ path: "/images/photo.png" });
  await expect(pending).rejects.toThrow("changed");
  expect(frames).toEqual([]);
  expect(busy.mock.calls).toEqual([[true], [false]]);
  const disposed = controller.attach([file]);
  controller.dispose();
  resolveUpload({ path: "/images/photo.png" });
  await expect(disposed).rejects.toThrow("changed");
  expect(frames).toEqual([]);
});
