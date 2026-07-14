import { useCallback, useEffect, useRef } from "react";

interface Props {
  onResize: (delta: number) => void;
}

/**
 * A thin draggable strip placed between two flex siblings.
 * Calls onResize(delta) on each mousemove tick while dragging.
 */
export default function ResizeDivider({ onResize }: Props) {
  const onResizeRef = useRef(onResize);
  onResizeRef.current = onResize;

  const draggingRef = useRef(false);

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    let lastX = e.clientX;
    draggingRef.current = true;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";

    const onMove = (e: MouseEvent) => {
      const delta = e.clientX - lastX;
      lastX = e.clientX;
      onResizeRef.current(delta);
    };

    const onUp = () => {
      draggingRef.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }, []);

  // Clean up in case the component unmounts mid-drag
  useEffect(() => {
    return () => {
      if (draggingRef.current) {
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
      }
    };
  }, []);

  return <div className="resize-divider" onMouseDown={onMouseDown} />;
}
