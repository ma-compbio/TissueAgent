/**
 * Resizable splitter handle.
 *
 * Renders a thin, hover-friendly divider that the user can drag to
 * resize one or both adjacent panels. The component is purely
 * presentational and stateless — the parent owns the dimension and
 * updates it via ``onResize`` as the user drags.
 *
 * Usage:
 *
 *   <Splitter
 *     orientation="vertical"   // a vertical handle resizes width
 *     onResize={(delta) => setWidth(w => clamp(w + delta, MIN, MAX))}
 *     ariaLabel="Resize sidebar"
 *   />
 *
 * Implementation note: the mousemove and mouseup handlers are stable
 * across renders, and the latest ``onResize`` is read through a ref
 * inside them. This is important — if we re-created the handlers on
 * every render (e.g. because the parent passes an inline arrow), the
 * ``useEffect`` cleanup that tracks them would tear down the active
 * drag listeners mid-drag, leaving the user stuck after the first
 * state change.
 */

import { useCallback, useEffect, useRef } from "react";

interface Props {
  /** "vertical" = handle is a vertical line; drag horizontally to resize
   *  the width of the left/right panels. "horizontal" = handle is a
   *  horizontal line; drag vertically to resize heights. */
  orientation: "vertical" | "horizontal";
  /** Called repeatedly during a drag with the delta in pixels since the
   *  last frame. Positive delta means right (vertical) or down
   *  (horizontal). */
  onResize: (delta: number) => void;
  /** Accessible label, e.g. "Resize sidebar". */
  ariaLabel: string;
  /** Optional. Called when the drag begins. */
  onDragStart?: () => void;
  /** Optional. Called when the drag ends (mouseup). */
  onDragEnd?: () => void;
}

export default function Splitter({
  orientation,
  onResize,
  ariaLabel,
  onDragStart,
  onDragEnd,
}: Props) {
  const draggingRef = useRef(false);
  const lastPosRef = useRef(0);
  const orientationRef = useRef(orientation);

  // Hold the latest callback identities in refs so the global mouse
  // listeners can call them without being re-bound on every render.
  // Inline arrow props from the parent (the common case) change
  // identity every render; re-binding listeners every render
  // tore down the active drag mid-stride.
  const onResizeRef = useRef(onResize);
  const onDragStartRef = useRef(onDragStart);
  const onDragEndRef = useRef(onDragEnd);

  useEffect(() => {
    orientationRef.current = orientation;
  }, [orientation]);
  useEffect(() => {
    onResizeRef.current = onResize;
  }, [onResize]);
  useEffect(() => {
    onDragStartRef.current = onDragStart;
  }, [onDragStart]);
  useEffect(() => {
    onDragEndRef.current = onDragEnd;
  }, [onDragEnd]);

  // Stable handlers — same function identity for the lifetime of the
  // component. They read the latest props through the refs above.
  const handleMouseMoveRef = useRef<(e: MouseEvent) => void>(undefined);
  const handleMouseUpRef = useRef<() => void>(undefined);

  if (!handleMouseMoveRef.current) {
    handleMouseMoveRef.current = (e: MouseEvent) => {
      if (!draggingRef.current) return;
      const current =
        orientationRef.current === "vertical" ? e.clientX : e.clientY;
      const delta = current - lastPosRef.current;
      lastPosRef.current = current;
      if (delta !== 0) onResizeRef.current(delta);
    };
  }
  if (!handleMouseUpRef.current) {
    handleMouseUpRef.current = () => {
      if (!draggingRef.current) return;
      draggingRef.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      window.removeEventListener("mousemove", handleMouseMoveRef.current!);
      window.removeEventListener("mouseup", handleMouseUpRef.current!);
      onDragEndRef.current?.();
    };
  }

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      draggingRef.current = true;
      lastPosRef.current =
        orientation === "vertical" ? e.clientX : e.clientY;
      // Lock the cursor globally for the duration of the drag so the
      // user can move past the handle's hit area without losing it.
      document.body.style.cursor =
        orientation === "vertical" ? "col-resize" : "row-resize";
      document.body.style.userSelect = "none";
      window.addEventListener("mousemove", handleMouseMoveRef.current!);
      window.addEventListener("mouseup", handleMouseUpRef.current!);
      onDragStartRef.current?.();
    },
    [orientation],
  );

  // If the splitter unmounts mid-drag (rare; e.g. a layout swap),
  // make sure we clean up the global listeners and body styles.
  useEffect(() => {
    return () => {
      if (draggingRef.current) {
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
        if (handleMouseMoveRef.current) {
          window.removeEventListener("mousemove", handleMouseMoveRef.current);
        }
        if (handleMouseUpRef.current) {
          window.removeEventListener("mouseup", handleMouseUpRef.current);
        }
      }
    };
  }, []);

  // Keyboard support — arrows move the handle by 8px, shift+arrows by 32px.
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      const step = e.shiftKey ? 32 : 8;
      let delta = 0;
      if (orientation === "vertical") {
        if (e.key === "ArrowLeft") delta = -step;
        else if (e.key === "ArrowRight") delta = step;
      } else {
        if (e.key === "ArrowUp") delta = -step;
        else if (e.key === "ArrowDown") delta = step;
      }
      if (delta !== 0) {
        e.preventDefault();
        onResizeRef.current(delta);
      }
    },
    [orientation],
  );

  return (
    <div
      className={`splitter splitter-${orientation}`}
      role="separator"
      aria-orientation={orientation}
      aria-label={ariaLabel}
      tabIndex={0}
      onMouseDown={handleMouseDown}
      onKeyDown={handleKeyDown}
    >
      <div className="splitter-line" aria-hidden="true" />
    </div>
  );
}
