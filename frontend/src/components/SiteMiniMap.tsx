import { MapContainer, TileLayer, Marker } from 'react-leaflet';
import { pinIcon } from '../lib/mapPins';
import 'leaflet/dist/leaflet.css';

interface Props {
  latitude: number;
  longitude: number;
  status: string;
  height?: number | string;
  zoom?: number;
}

/** Small read-only location map for detail/expand views. */
export default function SiteMiniMap({
  latitude,
  longitude,
  status,
  height = 220,
  zoom = 15,
}: Props) {
  return (
    <div className="rounded-lg overflow-hidden border border-gray-100" style={{ height }}>
      <MapContainer
        // Re-mount when coordinates change — MapContainer ignores center updates.
        key={`${latitude},${longitude}`}
        center={[latitude, longitude]}
        zoom={zoom}
        className="w-full h-full"
        scrollWheelZoom={false}
        dragging={false}
        zoomControl={false}
        attributionControl={false}
      >
        <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        <Marker position={[latitude, longitude]} icon={pinIcon(status)} />
      </MapContainer>
    </div>
  );
}
