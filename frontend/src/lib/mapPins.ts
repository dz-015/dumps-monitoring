import L from 'leaflet';
import pinGreen from '../assets/map-pins/green.svg';
import pinYellow from '../assets/map-pins/yellow.svg';
import pinRed from '../assets/map-pins/red.svg';

const STATUS_PIN: Record<string, string> = {
  clean: pinGreen,
  overflow: pinYellow,
  contamination: pinRed,
};

const ICON_CACHE: Record<string, L.Icon> = {};

/** Status-coloured map pin, shared by the map page and the mini-maps. */
export function pinIcon(status: string): L.Icon {
  const url = STATUS_PIN[status] ?? pinGreen;
  if (!ICON_CACHE[url]) {
    ICON_CACHE[url] = L.icon({
      iconUrl: url,
      iconSize: [54, 61],
      iconAnchor: [27, 53],
      popupAnchor: [0, -50],
    });
  }
  return ICON_CACHE[url];
}
