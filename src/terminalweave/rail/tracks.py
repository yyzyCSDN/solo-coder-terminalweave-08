from __future__ import annotations
from dataclasses import dataclass
from terminalweave.core.errors import ValidationError, CapacityError, ConflictError

@dataclass(frozen=True)
class YardTrack:
    track_id: str
    usable_length_m: float
    electrified: bool = False
    service_track: bool = False

    def __post_init__(self):
        if self.usable_length_m <= 0:
            raise ValidationError('track length must be positive')

@dataclass(frozen=True)
class TrainMovement:
    train_id: str
    length_m: float
    needs_electric: bool = False
    needs_service: bool = False

class TrackAllocator:

    def __init__(self, tracks: list[YardTrack]):
        self.tracks = {t.track_id: t for t in tracks}
        self.occupied: dict[str, str] = {}

    @staticmethod
    def _compatible(t: YardTrack, m: TrainMovement) -> bool:
        if t.usable_length_m < m.length_m:
            return False
        if m.needs_electric and (not t.electrified):
            return False
        if m.needs_service and (not t.service_track):
            return False
        return True

    def find_track(self, m: TrainMovement) -> str | None:
        candidates = [(t.usable_length_m - m.length_m, t.track_id) for t in self.tracks.values() if t.track_id not in self.occupied and self._compatible(t, m)]
        if not candidates:
            return None
        return min(candidates)[1]

    def validate(self, m: TrainMovement) -> str:
        """Return the track the movement would get, without occupying it."""
        for track_id, train_id in self.occupied.items():
            if train_id == m.train_id:
                if not self._compatible(self.tracks[track_id], m):
                    raise ConflictError(f'train {m.train_id} already holds incompatible track {track_id}')
                return track_id
        track = self.find_track(m)
        if track is None:
            raise CapacityError('no compatible yard track')
        return track

    def allocate(self, m: TrainMovement) -> str:
        # Idempotent: a train that already holds a track gets the same track
        # back instead of occupying a second one.
        track = self.validate(m)
        self.occupied[track] = m.train_id
        return track

    def release(self, track_id: str) -> str | None:
        return self.occupied.pop(track_id, None)
