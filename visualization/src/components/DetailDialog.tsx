import { useEffect, useRef } from "react";
import type { ReactNode } from "react";

/** Native modal semantics provide focus trapping, Escape and focus restoration. */
export function DetailDialog({
  label,
  onClose,
  children,
}: {
  label: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const closeRef = useRef(onClose);
  useEffect(() => {
    closeRef.current = onClose;
  }, [onClose]);
  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    const returnFocus = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    element.showModal();
    return () => {
      element.close();
      document.body.style.overflow = overflow;
      queueMicrotask(() => {
        if (!document.querySelector("dialog[open]") && returnFocus?.isConnected)
          returnFocus.focus();
      });
    };
  }, []);
  return (
    <dialog
      ref={dialog}
      className="detail-dialog"
      aria-label={label}
      onCancel={(event) => {
        event.preventDefault();
        closeRef.current();
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) closeRef.current();
      }}
    >
      {children}
    </dialog>
  );
}
