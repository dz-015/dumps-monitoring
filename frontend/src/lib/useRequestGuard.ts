import { useCallback, useRef } from 'react';

/**
 * Guard against out-of-order async responses (stale-response clobbering).
 *
 * Each `begin()` call invalidates every earlier one; response handlers check
 * `fresh()` before applying setState, so a slow response for the previous
 * filter/route can never overwrite data from a newer request.
 *
 *   const begin = useRequestGuard();
 *   const load = () => {
 *     const fresh = begin();
 *     getData().then((d) => { if (fresh()) setData(d); });
 *   };
 */
export function useRequestGuard() {
  const seq = useRef(0);
  return useCallback(() => {
    const id = ++seq.current;
    return () => id === seq.current;
  }, []);
}
