from datetime import datetime, timedelta, timezone

import pytest

from terminalweave.core.errors import CapacityError
from terminalweave.rail.blocks import RailBlockPlanner, RailContainer, Wagon
from terminalweave.rail.cutoff import ContainerReadiness, TrainCutoff
from terminalweave.rail.loading import BatchTrainLoader
from terminalweave.rail.tracks import TrackAllocator, TrainMovement, YardTrack

UTC = timezone.utc
DEPARTURE = datetime(2026, 1, 1, 18, 0, tzinfo=UTC)


def test_failed_batch_assignment_leaves_original_wagon_loads_unchanged():
    planner = RailBlockPlanner([Wagon("W1", 30_000.0, 20, "A")])
    containers = [
        RailContainer("C1", "A", 10_000.0, 20, priority=10),
        RailContainer("C2", "A", 20_000.0, 40, priority=0),
    ]
    with pytest.raises(CapacityError):
        planner.assign(containers)
    assert planner.loads[0].containers == []


def test_retry_after_failure_sees_full_capacity():
    planner = RailBlockPlanner([Wagon("W1", 30_000.0, 20, "A")])
    with pytest.raises(CapacityError):
        planner.assign([
            RailContainer("C1", "A", 10_000.0, 20, priority=10),
            RailContainer("C2", "A", 20_000.0, 40, priority=0),
        ])
    result = planner.assign([RailContainer("C1", "A", 10_000.0, 20, priority=10)])
    assert result == {"C1": "W1"}
    assert planner.loads[0].used_weight_kg == 10_000.0


def test_successful_replay_does_not_occupy_capacity_twice():
    planner = RailBlockPlanner([Wagon("W1", 30_000.0, 40, "A")])
    batch = [RailContainer("C1", "A", 10_000.0, 20)]
    first = planner.assign(batch)
    second = planner.assign(batch)
    assert second == first == {"C1": "W1"}
    assert planner.loads[0].used_weight_kg == 10_000.0
    assert planner.loads[0].used_length_ft == 20


def test_track_allocation_replay_keeps_single_track():
    allocator = TrackAllocator([YardTrack("T1", 500.0), YardTrack("T2", 500.0)])
    movement = TrainMovement("TR1", 300.0)
    first = allocator.allocate(movement)
    second = allocator.allocate(movement)
    assert first == second
    assert len(allocator.occupied) == 1


def _loader(track_length=500.0):
    planner = RailBlockPlanner([Wagon("W1", 30_000.0, 40, "A")])
    tracks = TrackAllocator([YardTrack("T1", track_length)])
    cutoff = TrainCutoff("TR1", DEPARTURE, timedelta(hours=2), timedelta(hours=1))
    return BatchTrainLoader(planner, tracks, cutoff)


def _readiness(container_id, ready_at=None):
    ready_at = ready_at or datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    return ContainerReadiness(container_id, ready_at, ready_at)


def test_batch_load_commits_wagons_and_track_together():
    loader = _loader()
    containers = [RailContainer("C1", "A", 10_000.0, 20)]
    result = loader.load(containers, [_readiness("C1")], TrainMovement("TR1", 300.0))
    assert result.assignments == {"C1": "W1"}
    assert result.track_id == "T1"
    assert loader.tracks.occupied == {"T1": "TR1"}


def test_batch_load_replay_returns_same_result_without_double_occupancy():
    loader = _loader()
    containers = [RailContainer("C1", "A", 10_000.0, 20)]
    movement = TrainMovement("TR1", 300.0)
    first = loader.load(containers, [_readiness("C1")], movement)
    second = loader.load(containers, [_readiness("C1")], movement)
    assert second == first
    assert loader.planner.loads[0].used_weight_kg == 10_000.0
    assert loader.tracks.occupied == {"T1": "TR1"}


def test_batch_load_cutoff_failure_leaves_wagons_and_track_untouched():
    loader = _loader()
    containers = [RailContainer("C1", "A", 10_000.0, 20)]
    late = _readiness("C1", ready_at=datetime(2026, 1, 1, 17, 30, tzinfo=UTC))
    with pytest.raises(CapacityError):
        loader.load(containers, [late], TrainMovement("TR1", 300.0))
    assert loader.planner.loads[0].containers == []
    assert loader.tracks.occupied == {}


def test_batch_load_track_failure_leaves_wagons_untouched():
    loader = _loader(track_length=200.0)
    containers = [RailContainer("C1", "A", 10_000.0, 20)]
    with pytest.raises(CapacityError):
        loader.load(containers, [_readiness("C1")], TrainMovement("TR1", 300.0))
    assert loader.planner.loads[0].containers == []
    assert loader.tracks.occupied == {}


def test_batch_load_wagon_failure_leaves_track_untouched():
    loader = _loader()
    containers = [
        RailContainer("C1", "A", 10_000.0, 20, priority=10),
        RailContainer("C2", "A", 25_000.0, 40, priority=0),
    ]
    with pytest.raises(CapacityError):
        loader.load(containers, [_readiness("C1"), _readiness("C2")], TrainMovement("TR1", 300.0))
    assert loader.planner.loads[0].containers == []
    assert loader.tracks.occupied == {}
