import { MapContainer, Marker, TileLayer, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import { useEffect, useRef } from 'react';
import 'leaflet/dist/leaflet.css';
import pinGreen from '../assets/map-pins/green.svg';

const PIN = L.icon({
  iconUrl: pinGreen,
  iconSize: [54, 61],
  iconAnchor: [27, 53],
});

const DEFAULT_CENTER: [number, number] = [44.952, 34.1];

interface Props {
  latitude: number | null;
  longitude: number | null;
  onChange: (lat: number, lng: number) => void;
  height?: number;
}

function ClickToPick({ onChange }: { onChange: (lat: number, lng: number) => void }) {
  useMapEvents({
    click(e) {
      onChange(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

function CenterOnce({ position }: { position: [number, number] | null }) {
  const map = useMap();
  const centeredRef = useRef(false);
  useEffect(() => {
    // Recenter only on the first time we get a real position (e.g. when initial
    // coords arrive from the parent for the edit form). Subsequent picks must
    // not yank the viewport — the pin moves but the map stays put.
    if (position && !centeredRef.current) {
      map.setView(position);
      centeredRef.current = true;
    }
  }, [map, position]);
  return null;
}

export default function MapPicker({ latitude, longitude, onChange, height = 220 }: Props) {
  const initial: [number, number] =
    latitude != null && longitude != null ? [latitude, longitude] : DEFAULT_CENTER;
  const marker: [number, number] | null =
    latitude != null && longitude != null ? [latitude, longitude] : null;

  return (
    <div>
      <div
        className="rounded-lg overflow-hidden border border-gray-200"
        style={{ height }}
      >
        <MapContainer
          center={initial}
          zoom={13}
          className="w-full h-full"
          scrollWheelZoom
          attributionControl={false}
        >
          <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          <CenterOnce position={marker} />
          <ClickToPick onChange={onChange} />
          {marker && <Marker position={marker} icon={PIN} />}
        </MapContainer>
      </div>
      <p className="text-xs text-gray-500 mt-1">
        {marker
          ? `Координаты: ${marker[0].toFixed(5)}, ${marker[1].toFixed(5)} — кликните по карте, чтобы переместить`
          : 'Кликните по карте, чтобы указать точку'}
      </p>
    </div>
  );
}
