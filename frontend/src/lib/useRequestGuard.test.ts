import { renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { useRequestGuard } from './useRequestGuard';

describe('useRequestGuard', () => {
  it('invalidates earlier requests when a newer one begins (BUG-10/21)', () => {
    const { result } = renderHook(() => useRequestGuard());
    const first = result.current();
    const second = result.current();

    // The slow "first" response must be dropped; the latest stays fresh.
    expect(first()).toBe(false);
    expect(second()).toBe(true);
  });

  it('a single in-flight request stays fresh', () => {
    const { result } = renderHook(() => useRequestGuard());
    const only = result.current();
    expect(only()).toBe(true);
  });

  it('returns a stable begin function across re-renders', () => {
    const { result, rerender } = renderHook(() => useRequestGuard());
    const before = result.current;
    rerender();
    expect(result.current).toBe(before);
  });
});
