import { useEffect, useRef, useState } from "react";

const LOGO_SIZE = 720;
const SPEED = 1.2; // px per frame

export function BouncingLogo() {
  const ref = useRef<HTMLImageElement>(null);
  const state = useRef({
    x: 0,
    y: 0,
    dx: SPEED,
    dy: SPEED,
    initialized: false,
  });
  const raf = useRef<number>(0);
  const [pos, setPos] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const parent = el.parentElement;
    if (!parent) return;

    function tick() {
      const s = state.current;
      const bounds = parent!.getBoundingClientRect();
      const maxX = bounds.width - LOGO_SIZE;
      const maxY = bounds.height - LOGO_SIZE;

      if (!s.initialized) {
        s.x = Math.random() * Math.max(0, maxX);
        s.y = Math.random() * Math.max(0, maxY);
        s.dx = (Math.random() > 0.5 ? 1 : -1) * SPEED;
        s.dy = (Math.random() > 0.5 ? 1 : -1) * SPEED;
        s.initialized = true;
      }

      s.x += s.dx;
      s.y += s.dy;

      if (s.x <= 0 || s.x >= maxX) {
        s.dx *= -1;
        s.x = Math.max(0, Math.min(s.x, maxX));
      }
      if (s.y <= 0 || s.y >= maxY) {
        s.dy *= -1;
        s.y = Math.max(0, Math.min(s.y, maxY));
      }

      setPos({ x: s.x, y: s.y });
      raf.current = requestAnimationFrame(tick);
    }

    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, []);

  return (
    <img
      ref={ref}
      src="/ralph-logo.png"
      alt=""
      aria-hidden="true"
      width={LOGO_SIZE}
      height={LOGO_SIZE}
      style={{
        position: "absolute",
        left: pos.x,
        top: pos.y,
        width: LOGO_SIZE,
        height: LOGO_SIZE,
        objectFit: "contain",
        opacity: 0.85,
        pointerEvents: "none",
        zIndex: 5,
      }}
    />
  );
}
