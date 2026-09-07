import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import SnapshotLightbox from './SnapshotLightbox';

function renderBox(onClose = () => {}) {
  return render(<SnapshotLightbox imageUrl="/x.jpg" detections={[]} onClose={onClose} />);
}

describe('SnapshotLightbox', () => {
  it('wheel up zooms the image, wheel down zooms back to 1 and recenters', () => {
    renderBox();
    const stage = screen.getByTestId('lightbox-stage');
    const zoomed = screen.getByTestId('lightbox-zoom');
    fireEvent.wheel(stage, { deltaY: -100, clientX: 10, clientY: 10 });
    // Шаг зума = exp(0.002 * 100) ≈ 1.22 на один щелчок колеса.
    expect(zoomed.style.transform).toContain('scale(1.22');
    fireEvent.wheel(stage, { deltaY: 100, clientX: 10, clientY: 10 });
    expect(zoomed.style.transform).toBe('translate(0px, 0px) scale(1)');
  });

  it('double click toggles between zoomed-in and reset', () => {
    renderBox();
    const stage = screen.getByTestId('lightbox-stage');
    const zoomed = screen.getByTestId('lightbox-zoom');
    fireEvent.doubleClick(stage, { clientX: 0, clientY: 0 });
    expect(zoomed.style.transform).toContain('scale(2.5)');
    fireEvent.doubleClick(stage, { clientX: 0, clientY: 0 });
    expect(zoomed.style.transform).toBe('translate(0px, 0px) scale(1)');
  });

  it('wheel down at minimum zoom closes the lightbox', () => {
    const onClose = vi.fn();
    renderBox(onClose);
    const stage = screen.getByTestId('lightbox-stage');
    // Приближено — колесо вниз лишь отдаляет, не закрывает.
    fireEvent.wheel(stage, { deltaY: -100, clientX: 10, clientY: 10 });
    fireEvent.wheel(stage, { deltaY: 100, clientX: 10, clientY: 10 });
    expect(onClose).not.toHaveBeenCalled();
    // А на масштабе 1 колесо вниз сворачивает просмотр.
    fireEvent.wheel(stage, { deltaY: 100, clientX: 10, clientY: 10 });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('locks page scroll while open and unlocks on unmount', () => {
    const { unmount } = renderBox();
    expect(document.body.style.overflow).toBe('hidden');
    unmount();
    expect(document.body.style.overflow).toBe('');
  });

  it('closes on Escape and on backdrop click, but not on a click inside the stage', () => {
    const onClose = vi.fn();
    renderBox(onClose);
    fireEvent.click(screen.getByTestId('lightbox-stage'));
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('dialog'));
    expect(onClose).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
