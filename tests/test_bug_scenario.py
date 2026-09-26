import pytest

from terminalweave.core.errors import CapacityError
from terminalweave.rail.blocks import RailBlockPlanner, RailContainer, Wagon


def test_failed_batch_assignment_leaves_original_wagon_loads_unchanged():
    planner = RailBlockPlanner([Wagon("W1", 30_000.0, 20, "A")])
    containers = [
        RailContainer("C1", "A", 10_000.0, 20, priority=10),
        RailContainer("C2", "A", 20_000.0, 40, priority=0),
    ]
    with pytest.raises(CapacityError):
        planner.assign(containers)
    assert planner.loads[0].containers == []
