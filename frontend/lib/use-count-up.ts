"use client";
import { useEffect, useState } from "react";

/* Animates a number from 0 to `target` on mount/target-change, easing out.
 * Shared by any final-match card that wants a "count-up" stat instead of a
 * static number appearing instantly. */
export function useCountUp(target: number, duration = 1100): number {
  const [value, setValue] = useState(0);
  useEffect(() => {
    let raf: number;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(target * eased);
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);
  return value;
}
