"""Build an HTML gallery for manual review of cam_2 frames with GT bboxes.

Output: one HTML page per camera, each frame shown with ground truth boxes
overlaid. User opens, scrolls, decides keep/drop/relabel and records in
a CSV.

Workflow:
1. Run this script → produces frames_overlay/ with annotated images + decisions.csv (preset action=keep for all)
2. Open the HTML in browser, scroll through cam_2
3. Edit decisions.csv: action column to drop / relabel for problematic frames
4. Run filter_apply_decisions.py to materialise drops (separate script)

Usage:
    python build_review_gallery.py \\
        --camera 2 \\
        --images-dir data/processed/to_label \\
        --labels-dir data/processed/labeled \\
        --out-dir runs/manual_review/cam_2
"""

from __future__ import annotations

import csv
from pathlib import Path

import click


CLASS_COLORS = {
    0: (50, 200, 50),    # bin_ok — green
    1: (50, 50, 200),    # bin_overflow — red-blue
    2: (200, 150, 50),   # ground_trash — orange
}
CLASS_NAMES = {0: "bin_ok", 1: "bin_overflow", 2: "ground_trash"}


def render_annotated(img_path: Path, label_path: Path, out_path: Path,
                     full_out_path: Path) -> dict:
    """Render thumbnail (960px) + full-size (original) copies.

    Thumbnail uses thin (1px) rectangles for visibility of underlying content.
    Full-size is saved unmodified for click-to-open viewing.
    """
    import cv2

    img = cv2.imread(str(img_path))
    H, W = img.shape[:2]
    counts = {0: 0, 1: 0, 2: 0}

    # Full-size copy: no annotations, just the raw image (link target)
    cv2.imwrite(str(full_out_path), img, [cv2.IMWRITE_JPEG_QUALITY, 85])

    if label_path.exists() and label_path.stat().st_size > 0:
        for line in label_path.read_text().strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split()
            cls = int(parts[0])
            cx, cy, w_n, h_n = map(float, parts[1:5])
            x1 = int((cx - w_n / 2) * W)
            y1 = int((cy - h_n / 2) * H)
            x2 = int((cx + w_n / 2) * W)
            y2 = int((cy + h_n / 2) * H)
            color = CLASS_COLORS[cls]
            cv2.rectangle(img, (x1, y1), (x2, y2), color, 1)
            counts[cls] += 1
    scale = 960 / W
    new_h = int(H * scale)
    img = cv2.resize(img, (960, new_h))
    cv2.imwrite(str(out_path), img, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return {"total_bboxes": sum(counts.values()), **counts}


@click.command()
@click.option("--camera", type=int, required=True)
@click.option("--images-dir", type=click.Path(path_type=Path, exists=True),
              default=Path("data/processed/to_label"))
@click.option("--labels-dir", type=click.Path(path_type=Path, exists=True),
              default=Path("data/processed/labeled"))
@click.option("--exclude-list",
              type=click.Path(path_type=Path),
              default=None,
              help="Optional: skip filenames listed here (one per line)")
@click.option("--include-only-list",
              type=click.Path(path_type=Path),
              default=None,
              help="Optional: render ONLY filenames listed here (for reviewing dropped frames)")
@click.option("--out-dir", type=click.Path(path_type=Path), required=True)
def main(camera, images_dir, labels_dir, exclude_list, include_only_list, out_dir):
    excluded = set()
    if exclude_list and Path(exclude_list).exists():
        excluded = {l.strip() for l in Path(exclude_list).read_text().splitlines() if l.strip()}
        click.echo(f"Loaded {len(excluded)} excluded filenames from {exclude_list}")
    include_only = None
    if include_only_list and Path(include_only_list).exists():
        include_only = {l.strip() for l in Path(include_only_list).read_text().splitlines() if l.strip()}
        click.echo(f"Loaded {len(include_only)} include-only filenames from {include_only_list}")
    out_dir = Path(out_dir)
    overlay_dir = out_dir / "frames"
    full_dir = out_dir / "full"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    full_dir.mkdir(parents=True, exist_ok=True)

    all_images = sorted((images_dir / str(camera)).glob("*.jpg"))
    if include_only is not None:
        images = [img for img in all_images if img.name in include_only]
        click.echo(f"Camera {camera}: {len(images)} frames to render (include-only mode)")
    else:
        images = [img for img in all_images if img.name not in excluded]
        click.echo(f"Camera {camera}: {len(images)} frames to render "
                   f"({len(all_images) - len(images)} pre-excluded)")

    decisions_csv = out_dir / "decisions.csv"
    with open(decisions_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["filename", "n_bboxes", "n_bin_ok", "n_bin_overflow",
                         "n_ground_trash", "action", "note"])
        for idx, img_path in enumerate(images):
            label_path = labels_dir / str(camera) / (img_path.stem + ".txt")
            out_img = overlay_dir / img_path.name
            full_img = full_dir / img_path.name
            info = render_annotated(img_path, label_path, out_img, full_img)
            writer.writerow([
                img_path.name, info["total_bboxes"], info[0], info[1], info[2],
                "keep", "",  # default action; user edits in spreadsheet
            ])
            if (idx + 1) % 50 == 0:
                click.echo(f"  {idx+1}/{len(images)}")

    # Build interactive HTML gallery with KEEP/DROP/RELABEL buttons,
    # localStorage persistence, CSV export.
    html_path = out_dir / "review.html"
    with open(html_path, "w") as f:
        f.write(f"""<!doctype html>
<html><head><meta charset="utf-8">
<title>Review cam_{camera}</title>
<style>
* {{ box-sizing: border-box; }}
body {{ font-family: sans-serif; background: #1a1a1a; color: #ddd; margin: 0; padding: 12px; }}
.toolbar {{ position: sticky; top: 0; background: #0a0a0a; padding: 10px; z-index: 10;
            display: flex; gap: 12px; align-items: center; border-bottom: 2px solid #333; }}
.toolbar button {{ padding: 8px 14px; font-size: 14px; cursor: pointer; border: 0;
                    border-radius: 4px; background: #4a8a4a; color: #fff; font-weight: 600; }}
.toolbar button.danger {{ background: #8a4a4a; }}
.toolbar .status {{ font-size: 13px; color: #aaa; }}
.toolbar input {{ padding: 6px; background: #222; color: #ddd; border: 1px solid #444; border-radius: 4px; }}

.gallery {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(440px, 1fr)); gap: 10px; padding: 8px; }}

.frame {{ background: #2a2a2a; border-radius: 6px; padding: 8px; border: 3px solid transparent; transition: border-color 0.15s; }}
.frame.action-keep    {{ border-color: #4a8a4a; }}
.frame.action-drop    {{ border-color: #8a4a4a; }}
.frame.action-relabel {{ border-color: #cca84a; }}

.frame img {{ display: block; width: 100%; height: auto; border-radius: 4px; cursor: zoom-in; }}
.frame .info {{ font-size: 11px; color: #aaa; margin: 6px 0; font-family: monospace; }}
.frame .info .name {{ color: #fff; }}
.frame .info .count {{ color: #cccc66; font-weight: 600; }}

.actions {{ display: flex; gap: 6px; margin-top: 6px; }}
.actions button {{ flex: 1; padding: 8px; font-size: 13px; cursor: pointer; border: 0;
                   border-radius: 4px; background: #333; color: #888; }}
.actions button.keep    {{ background: #2a4a2a; color: #aaffaa; }}
.actions button.drop    {{ background: #4a2a2a; color: #ffaaaa; }}
.actions button.relabel {{ background: #4a4a2a; color: #ffeebb; }}
.actions button.active  {{ outline: 3px solid #fff; font-weight: 700; }}

.note {{ width: 100%; margin-top: 6px; padding: 4px; font-size: 12px; background: #1a1a1a;
         color: #ddd; border: 1px solid #444; border-radius: 4px; }}

h1 {{ color: #fff; padding: 0 8px; font-size: 18px; }}
.legend {{ font-size: 12px; color: #aaa; padding: 4px 12px; }}
</style></head><body>

<div class="toolbar">
  <button onclick="exportCSV()">💾 Скачать decisions.csv</button>
  <button class="danger" onclick="resetAll()">🔄 Сбросить</button>
  <span class="status">
    <span id="cnt_total">0</span> всего |
    <span style="color:#aaffaa" id="cnt_keep">0</span> keep |
    <span style="color:#ffaaaa" id="cnt_drop">0</span> drop |
    <span style="color:#ffeebb" id="cnt_relabel">0</span> relabel
  </span>
  <span class="status">Hotkeys: <b>K</b>=keep <b>D</b>=drop <b>R</b>=relabel</span>
</div>

<h1>Review cam_{camera} — {len(images)} кадров</h1>
<div class="legend">
  Bbox цвета:
  <span style="color: rgb(50,200,50)">■ bin_ok</span> ·
  <span style="color: rgb(50,50,200)">■ bin_overflow</span> ·
  <span style="color: rgb(200,150,50)">■ ground_trash</span>
  · Клик на фото — открыть оригинал в новой вкладке
</div>

<div class="gallery" id="gallery">
""")
        for img_path in images:
            f.write(f'''<div class="frame" data-name="{img_path.name}">
<a href="full/{img_path.name}" target="_blank"><img src="frames/{img_path.name}" loading="lazy"></a>
<div class="info"><span class="name">{img_path.stem}</span></div>
<div class="actions">
<button class="keep"    onclick="setAction(this, 'keep')">✓ KEEP</button>
<button class="drop"    onclick="setAction(this, 'drop')">✗ DROP</button>
<button class="relabel" onclick="setAction(this, 'relabel')">↻ RELABEL</button>
</div>
<input class="note" placeholder="note (optional)" oninput="saveNote(this)">
</div>
''')
        f.write(f"""</div>

<script>
const KEY = "cam_{camera}_decisions_v1";
const FILENAMES = [{",".join(f'"{img.name}"' for img in images)}];

function loadState() {{
  try {{ return JSON.parse(localStorage.getItem(KEY) || "{{}}"); }} catch (e) {{ return {{}}; }}
}}
function saveState(state) {{ localStorage.setItem(KEY, JSON.stringify(state)); }}

function applyState() {{
  const state = loadState();
  document.querySelectorAll('.frame').forEach(div => {{
    const name = div.dataset.name;
    const entry = state[name] || {{action:'keep', note:''}};
    div.classList.remove('action-keep','action-drop','action-relabel');
    div.classList.add('action-' + entry.action);
    div.querySelectorAll('.actions button').forEach(b => b.classList.remove('active'));
    div.querySelector('.actions button.' + entry.action).classList.add('active');
    div.querySelector('.note').value = entry.note || '';
  }});
  updateCounters();
}}
function updateCounters() {{
  const state = loadState();
  let k=0, d=0, r=0;
  FILENAMES.forEach(n => {{
    const a = (state[n] && state[n].action) || 'keep';
    if (a==='keep') k++; else if (a==='drop') d++; else if (a==='relabel') r++;
  }});
  document.getElementById('cnt_total').textContent = FILENAMES.length;
  document.getElementById('cnt_keep').textContent = k;
  document.getElementById('cnt_drop').textContent = d;
  document.getElementById('cnt_relabel').textContent = r;
}}

function setAction(btn, action) {{
  const div = btn.closest('.frame');
  const name = div.dataset.name;
  const state = loadState();
  state[name] = {{action, note: div.querySelector('.note').value || ''}};
  saveState(state);
  applyState();
}}

function saveNote(input) {{
  const div = input.closest('.frame');
  const name = div.dataset.name;
  const state = loadState();
  const action = (state[name] && state[name].action) || 'keep';
  state[name] = {{action, note: input.value}};
  saveState(state);
}}

function resetAll() {{
  if (confirm('Сбросить все decisions?')) {{
    localStorage.removeItem(KEY);
    applyState();
  }}
}}

function exportCSV() {{
  const state = loadState();
  let csv = 'filename,action,note\\n';
  FILENAMES.forEach(n => {{
    const e = state[n] || {{action:'keep', note:''}};
    csv += `${{n}},${{e.action}},"${{(e.note||'').replace(/"/g,'""')}}"\\n`;
  }});
  const blob = new Blob([csv], {{type:'text/csv'}});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = 'decisions.csv';
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
}}

// Keyboard hotkeys when mouse hovers a frame
let hoveredFrame = null;
document.addEventListener('mouseover', e => {{
  const f = e.target.closest('.frame');
  if (f) hoveredFrame = f;
}});
document.addEventListener('keydown', e => {{
  if (!hoveredFrame) return;
  if (e.target.tagName === 'INPUT') return;
  let action = null;
  if (e.key === 'k' || e.key === 'K') action = 'keep';
  if (e.key === 'd' || e.key === 'D') action = 'drop';
  if (e.key === 'r' || e.key === 'R') action = 'relabel';
  if (action) {{
    const btn = hoveredFrame.querySelector('.actions button.' + action);
    if (btn) setAction(btn, action);
    e.preventDefault();
  }}
}});

applyState();
</script>
</body></html>
""")

    click.echo(f"\n✓ Gallery ready: {html_path}")
    click.echo(f"  Decisions CSV: {decisions_csv}")
    click.echo(f"  Frames: {overlay_dir}")
    click.echo(f"\nWorkflow:")
    click.echo(f"  1. Open {html_path} in browser")
    click.echo(f"  2. Edit {decisions_csv} (action column: keep / drop / relabel)")
    click.echo(f"  3. Run filter_apply_decisions.py with the edited CSV")


if __name__ == "__main__":
    main()
