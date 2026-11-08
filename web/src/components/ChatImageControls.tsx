import { useRef } from "react";
import { ImagePlus, ClipboardPaste } from "lucide-react";

interface ChatImageControlsProps {
  connected: boolean;
  busy: boolean;
  clipboardSupported: boolean;
  onAttach(files: File[]): void;
  onPaste(): void;
}

/** Attachment tools only; the PTY-backed TUI remains the sole composer. */
export function ChatImageControls({ connected, busy, clipboardSupported, onAttach, onPaste }: ChatImageControlsProps) {
  const picker = useRef<HTMLInputElement>(null);
  const disabled = !connected || busy;
  const buttonClass = "min-h-11 min-w-11 rounded border border-current/30 px-3 text-xs inline-flex items-center justify-center gap-2 disabled:opacity-40 hover:bg-white/10";
  return (
    <div className="flex shrink-0 flex-wrap items-center gap-2 pt-2" role="group" aria-label="Image attachments" aria-busy={busy}>
      <input ref={picker} type="file" accept="image/*" className="hidden" tabIndex={-1} disabled={disabled} aria-label="Choose image from photos or files" onChange={event => {
        const files = Array.from(event.currentTarget.files ?? []);
        event.currentTarget.value = "";
        if (files.length) onAttach(files);
      }} />
      <button type="button" className={buttonClass} disabled={disabled} aria-label="Attach image" title="Choose an image from your photo library or files" onClick={() => picker.current?.click()}>
        <ImagePlus className="h-4 w-4" aria-hidden="true" /> Attach image
      </button>
      {clipboardSupported && <button type="button" className={buttonClass} disabled={disabled} aria-label="Paste image" title="Paste an image from your clipboard (requires permission)" onClick={onPaste}>
        <ClipboardPaste className="h-4 w-4" aria-hidden="true" /> Paste image
      </button>}
      {busy && <span role="status" aria-live="polite" className="text-xs">Attaching image…</span>}
    </div>
  );
}
