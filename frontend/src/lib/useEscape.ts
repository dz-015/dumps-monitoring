import { useEffect } from 'react';

/**
 * Calls `onEscape` when the user presses the Escape key.
 * Mount the hook in any modal so users can dismiss it from the keyboard.
 */
export function useEscape(onEscape: () => void) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onEscape();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onEscape]);
}
