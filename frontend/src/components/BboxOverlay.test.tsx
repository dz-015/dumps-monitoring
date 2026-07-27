import { fireEvent, render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import BboxOverlay from './BboxOverlay';

function loadImage(container: HTMLElement, naturalWidth: number, naturalHeight: number) {
  const img = container.querySelector('img')!;
  Object.defineProperty(img, 'naturalWidth', { value: naturalWidth, configurable: true });
  Object.defineProperty(img, 'naturalHeight', { value: naturalHeight, configurable: true });
  fireEvent.load(img);
}

describe('BboxOverlay', () => {
  it('renders one rect per detection (plus background label rects)', () => {
    const { container } = render(
      <BboxOverlay
        imageUrl="/fake.jpg"
        detections={[
          { class_name: 'metal_ok', confidence: 0.9, x: 0.5, y: 0.5, w: 0.2, h: 0.2 },
          { class_name: 'ground_trash', confidence: 0.7, x: 0.1, y: 0.8, w: 0.3, h: 0.1 },
        ]}
        width={100}
        height={100}
      />
    );
    // Each detection produces 2 rects (bbox + label background) → 4 for 2 detections.
    expect(container.querySelectorAll('rect').length).toBe(4);
  });

  it('converts YOLO center-size to SVG top-left coordinates', () => {
    const { container } = render(
      <BboxOverlay
        imageUrl="/fake.jpg"
        detections={[{ class_name: 'metal_ok', confidence: 1, x: 0.5, y: 0.5, w: 0.2, h: 0.2 }]}
        width={100}
        height={100}
      />
    );
    const bboxRect = container.querySelector('rect[fill="none"]') as SVGRectElement | null;
    expect(bboxRect).not.toBeNull();
    // x=0.5, w=0.2 on width=100 → top-left x = (0.5 - 0.1) * 100 = 40
    expect(bboxRect!.getAttribute('x')).toBe('40');
    expect(bboxRect!.getAttribute('y')).toBe('40');
    expect(bboxRect!.getAttribute('width')).toBe('20');
    expect(bboxRect!.getAttribute('height')).toBe('20');
  });

  it('maps boxes onto the letterboxed image rect, not the whole container (BUG-19)', () => {
    const { container } = render(
      <BboxOverlay
        imageUrl="/fake.jpg"
        detections={[{ class_name: 'metal_ok', confidence: 1, x: 0.5, y: 0.5, w: 0.2, h: 0.2 }]}
        width={100}
        height={100}
      />
    );
    // A 2:1 image inside a 1:1 container renders at 100×50 with 25px bars
    // top and bottom.
    loadImage(container, 200, 100);
    const bboxRect = container.querySelector('rect[fill="none"]') as SVGRectElement;
    expect(bboxRect.getAttribute('x')).toBe('40'); // (0.5-0.1) * 100 + 0
    expect(bboxRect.getAttribute('y')).toBe('45'); // (0.5-0.1) * 50 + 25
    expect(bboxRect.getAttribute('width')).toBe('20'); // 0.2 * 100
    expect(bboxRect.getAttribute('height')).toBe('10'); // 0.2 * 50
  });

  it('a top-edge box hugs the top of the image content, not the container', () => {
    const { container } = render(
      <BboxOverlay
        imageUrl="/fake.jpg"
        detections={[{ class_name: 'metal_ok', confidence: 1, x: 0.5, y: 0.05, w: 0.2, h: 0.1 }]}
        width={100}
        height={100}
      />
    );
    loadImage(container, 200, 100);
    const bboxRect = container.querySelector('rect[fill="none"]') as SVGRectElement;
    // Image content starts at y=25; box top = 25 + (0.05-0.05)*50 = 25, not 0.
    expect(bboxRect.getAttribute('y')).toBe('25');
  });

  it('applies red stroke for *_overflow, green for *_ok, orange for ground_trash', () => {
    const { container } = render(
      <BboxOverlay
        imageUrl="/fake.jpg"
        detections={[
          { class_name: 'metal_overflow', confidence: 1, x: 0.5, y: 0.5, w: 0.1, h: 0.1 },
          { class_name: 'plastic_ok', confidence: 1, x: 0.3, y: 0.3, w: 0.1, h: 0.1 },
          { class_name: 'ground_trash', confidence: 1, x: 0.7, y: 0.7, w: 0.1, h: 0.1 },
        ]}
        width={100}
        height={100}
      />
    );
    const strokes = Array.from(container.querySelectorAll('rect[fill="none"]')).map((r) =>
      r.getAttribute('stroke')
    );
    expect(strokes).toEqual(['#ef4444', '#22c55e', '#f97316']);
  });

  it('uses fallback colour for unknown class_name', () => {
    const { container } = render(
      <BboxOverlay
        imageUrl="/fake.jpg"
        detections={[{ class_name: 'mystery_bin', confidence: 1, x: 0.5, y: 0.5, w: 0.1, h: 0.1 }]}
        width={100}
        height={100}
      />
    );
    const stroke = container.querySelector('rect[fill="none"]')?.getAttribute('stroke');
    expect(stroke).toBe('#94a3b8');
  });

  it('renders confidence label as integer percent', () => {
    const { getByText } = render(
      <BboxOverlay
        imageUrl="/fake.jpg"
        detections={[{ class_name: 'metal_ok', confidence: 0.872, x: 0.5, y: 0.5, w: 0.1, h: 0.1 }]}
        width={100}
        height={100}
      />
    );
    expect(getByText(/87%/)).toBeInTheDocument();
  });

  it('renders nothing except background image when detections is empty', () => {
    const { container } = render(
      <BboxOverlay imageUrl="/fake.jpg" detections={[]} width={100} height={100} />
    );
    expect(container.querySelectorAll('rect').length).toBe(0);
  });
});
