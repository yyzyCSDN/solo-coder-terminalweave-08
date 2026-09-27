from __future__ import annotations
from dataclasses import dataclass
from terminalweave.core.errors import CapacityError
from terminalweave.rail.blocks import RailBlockPlanner, RailContainer
from terminalweave.rail.cutoff import CutoffChecker, ContainerReadiness, TrainCutoff
from terminalweave.rail.tracks import TrackAllocator, TrainMovement

@dataclass(frozen=True)
class BatchLoadResult:
    assignments: dict[str, str]
    track_id: str

class BatchTrainLoader:
    """All-or-nothing loading of a container batch onto a train.

    Cutoff readiness, yard-track compatibility and the wagon constraints
    (length, weight, destination) are all validated before anything is
    committed, so a failed batch leaves wagon loads and track occupation
    exactly as they were. Replaying a successful batch returns the same
    result without occupying capacity a second time.
    """

    def __init__(self, planner: RailBlockPlanner, tracks: TrackAllocator, cutoff: TrainCutoff):
        self.planner = planner
        self.tracks = tracks
        self.cutoff = cutoff
        self.checker = CutoffChecker()

    def _check_cutoff(self, containers: list[RailContainer], readiness: list[ContainerReadiness]) -> None:
        ready = {r.container_id: r for r in readiness}
        for container in containers:
            r = ready.get(container.container_id)
            if r is None:
                raise CapacityError(f'no readiness information for {container.container_id}')
            if not self.checker.evaluate(self.cutoff, r)['eligible']:
                raise CapacityError(f'container {container.container_id} misses train cutoff')

    def load(self, containers: list[RailContainer], readiness: list[ContainerReadiness], movement: TrainMovement) -> BatchLoadResult:
        # Validate every constraint first; none of these calls mutates state.
        self._check_cutoff(containers, readiness)
        self.tracks.validate(movement)
        # Wagon assignment is atomic: it raises without touching current loads.
        assignments = self.planner.assign(containers)
        # Already validated above, so this commit cannot fail; it is also
        # idempotent for a train that already holds a track.
        track_id = self.tracks.allocate(movement)
        return BatchLoadResult(assignments, track_id)
