"""Round-two training boundary. No training algorithm is implemented in round one."""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class TrainingSpec:
    dataset_manifest: str
    features: str
    seed: int
    target: str
    split_manifest: str


class Trainer(Protocol):
    def fit(self, spec: TrainingSpec, output_directory: str) -> str:
        """Return path to a model manifest with weights, feature version and metrics."""
        ...
