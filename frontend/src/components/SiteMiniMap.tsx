import { MapContainer, TileLayer, Marker } from 'react-leaflet';
import { pinIcon } from '../lib/mapPins';
import 'leaflet/dist/leaflet.css';

interface Props {
  latitude: number;
  longitude: number;
  status: string;
  height?: number | string;
  zoom?: number;
  /** Разрешить перемещение и зум (колесо, drag, кнопки +/-). */
  interactive?: boolean;
}

/** Small location map for detail/expand views. */
export default function SiteMiniMap({
  latitude,
  longitude,
  status,
  height = 220,
  zoom = 15,
  interactive = false,
}: Props) {
  return (
    <div className="rounded-lg overflow-hidden border border-gray-100" style={{ height }}>
      <MapContainer
        // Re-mount when coordinates change — MapContainer ignores center updates.
        key={`${latitude},${longitude}`}
        center={[latitude, longitude]}
        zoom={zoom}
        className="w-full h-full"
        scrollWheelZoom={interactive}
        dragging={interactive}
        zoomControl={interactive}
        // В статичном режиме дабл-клик тоже гасим: раньше он приближал
        // карту, из которой нельзя было отдалиться обратно.
        doubleClickZoom={interactive}
        touchZoom={interactive}
        keyboard={interactive}
        attributionControl={false}
      >
        <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        <Marker position={[latitude, longitude]} icon={pinIcon(status)} />
      </MapContainer>
    </div>
  );
}
