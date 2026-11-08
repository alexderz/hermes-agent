import { authedFetch } from "@/lib/api";

// Clipboard image MIME → file extension. Mirrors the set the TUI's /image
// attach path and the gateway's image sniffer accept.
const IMAGE_MIME_EXT: Record<string, string> = {
  "image/png": "png",
  "image/jpeg": "jpg",
  "image/gif": "gif",
  "image/webp": "webp",
  "image/bmp": "bmp",
};

// Anthropic caps a single vision image at ~25 MB; reject earlier client-side
// with a clear message rather than round-tripping a doomed upload.
const MAX_IMAGE_BYTES = 25 * 1024 * 1024;

export interface ChatImageUploadResult {
  /** Absolute path under HERMES_HOME/images the gateway wrote. */
  path: string;
  /** Byte size of the uploaded image. */
  bytes: number;
  /** Basename written on the server. */
  name: string;
  mime_type: string;
}

function imageFileKey(file: File): string {
  return `${file.name}\0${file.type}\0${file.size}\0${file.lastModified}`;
}

function addImageFile(files: File[], seen: Set<string>, file: File | null) {
  if (!file || !file.type.startsWith("image/")) return;
  const key = imageFileKey(file);
  if (seen.has(key)) return;
  seen.add(key);
  files.push(file);
}

/** Pull every image file out of a DataTransfer (clipboard or drop). */
export function imageFilesFromTransfer(
  data: DataTransfer | null,
): File[] {
  if (!data) return [];
  const files: File[] = [];
  const seen = new Set<string>();

  if (data.items?.length) {
    for (let i = 0; i < data.items.length; i++) {
      const item = data.items[i];
      if (item.kind === "file" && item.type.startsWith("image/")) {
        addImageFile(files, seen, item.getAsFile());
      }
    }
  }

  if (data.files?.length) {
    for (let i = 0; i < data.files.length; i++) {
      addImageFile(files, seen, data.files[i]);
    }
  }

  return files;
}

/** Pull the first image blob out of a DataTransfer, or null if none present. */
export function firstImageFromClipboard(
  data: DataTransfer | null,
): File | null {
  return imageFilesFromTransfer(data)[0] ?? null;
}

/** True when a drag payload may contain an image (for dragover preventDefault). */
export function transferMayContainImage(data: DataTransfer | null): boolean {
  if (!data) return false;
  if (data.items?.length) {
    for (let i = 0; i < data.items.length; i++) {
      const item = data.items[i];
      if (
        item.kind === "file" &&
        (!item.type || item.type.startsWith("image/"))
      ) {
        return true;
      }
    }
    return false;
  }
  if (data.files?.length) {
    for (let i = 0; i < data.files.length; i++) {
      if (data.files[i].type.startsWith("image/")) return true;
    }
  }
  return false;
}

export async function readClipboardImages(clipboard: Clipboard | undefined): Promise<File[]> {
  if (typeof clipboard?.read !== "function") {
    throw new Error("Clipboard images need HTTPS and a supported browser. Use Attach image instead.");
  }
  const files: File[] = [];
  try {
    const items = await clipboard.read();
    for (const item of items) {
      const type = item.types.find(type => type.startsWith("image/"));
      if (!type) continue;
      const blob = await item.getType(type);
      files.push(new File([blob], `clipboard.${IMAGE_MIME_EXT[type] || "png"}`, { type }));
    }
  } catch {
    throw new Error("Clipboard permission denied or unavailable. Allow clipboard access, or use Attach image.");
  }
  if (!files.length) throw new Error("No image found in clipboard. Copy an image, or use Attach image.");
  return files;
}

interface ImageAttachmentSocket {
  readyState: number;
  send(data: string): void;
}

interface ChatImageAttachmentOptions {
  socket(): ImageAttachmentSocket | null;
  active(): boolean;
  upload(file: File): Promise<{ path: string }>;
  busy(value: boolean): void;
}

/** Use the TUI's dropped-path paste handler (the same image.attach RPC as
 * /image). Sending /image + Return would append to and submit a user's draft;
 * bracketed paste inserts an image token at the TUI's own cursor instead. */
export function createChatImageAttachment(options: ChatImageAttachmentOptions) {
  let busy = false;
  let disposed = false;
  return {
    dispose() { disposed = true; },
    async attach(files: File[]) {
      if (!files.length) return;
      if (files.some(file => !file.type.startsWith("image/"))) {
        throw new Error("Choose an image file from your photos or files.");
      }
      if (busy) throw new Error("An image attachment is already in progress.");
      const socket = options.socket();
      if (disposed || !options.active() || !socket || socket.readyState !== 1) {
        throw new Error("Chat is not connected — reconnect before attaching an image.");
      }
      busy = true;
      options.busy(true);
      try {
        for (const file of files) {
          const { path } = await options.upload(file);
          if (disposed || !options.active() || options.socket() !== socket || socket.readyState !== 1) {
            throw new Error("Chat connection changed during upload — select the image again.");
          }
          socket.send(`\x1b[200~${path}\x1b[201~`);
        }
      } finally {
        busy = false;
        options.busy(false);
      }
    },
  };
}

function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () =>
      reject(reader.error ?? new Error("image read failed"));
    reader.onload = () => {
      const result = reader.result;
      if (typeof result === "string") {
        resolve(result);
      } else {
        reject(new Error("image read failed"));
      }
    };
    reader.readAsDataURL(file);
  });
}

/**
 * Upload a browser clipboard/drop image to ``HERMES_HOME/images`` via the
 * dedicated chat upload endpoint and return the absolute gateway path.
 *
 * The dashboard Chat tab is an xterm mirror of a TUI running INSIDE the
 * gateway. The container has no access to the browser's clipboard, so the
 * server-side ``clipboard.paste`` path can never see a pasted image.
 * Upload the bytes the browser already holds, then hand the path to the
 * TUI's ``/image`` command.
 */
export async function uploadChatImage(
  blob: Blob,
  profile = "",
): Promise<ChatImageUploadResult> {
  if (blob.size === 0) throw new Error("clipboard image is empty");
  if (blob.size > MAX_IMAGE_BYTES) {
    const mb = Math.round(MAX_IMAGE_BYTES / (1024 * 1024));
    throw new Error(`image too large (max ${mb} MB)`);
  }

  const mime = blob.type || "image/png";
  const ext = IMAGE_MIME_EXT[mime] || "png";
  const filename =
    blob instanceof File && blob.name
      ? blob.name
      : `clipboard.${ext}`;
  const file =
    blob instanceof File
      ? blob
      : new File([blob], filename, { type: mime });

  const dataUrl = await fileToDataUrl(file);
  const qs = profile ? `?profile=${encodeURIComponent(profile)}` : "";
  const res = await authedFetch(`/api/chat/image-upload${qs}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      data_url: dataUrl,
      filename,
    }),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(text || `HTTP ${res.status}`);
  }

  const uploaded = (await res.json()) as ChatImageUploadResult;
  if (!uploaded?.path) {
    throw new Error("image upload did not return a path");
  }
  return uploaded;
}
