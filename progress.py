from dataclasses import dataclass
from enum import Enum
from multiprocessing import Manager
from uuid import uuid4


class ProgressState(Enum):
    PENDING = "Pending"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"


@dataclass
class JobProgress:
    state: str
    value: int


class Progress:
    def __init__(self, manager) -> None:
        self.progress_map = manager.dict()
        self.progress_value = 0
        self.job_id = str(uuid4())

    def add_job(self) -> str:
        """
        Add a new job with a unique job id.

        Args: None

        Returns: str(job_id)
        """
        job_id = str(uuid4())
        self.progress_map[job_id] = {
            "state": ProgressState.PENDING.value,
            "value": 0,
        }
        return job_id

    def start_job(self, job_id: str) -> None:
        self.progress_map[job_id] = {
            "state": ProgressState.IN_PROGRESS.value,
            "value": 0,
        }

    def remove_job(self, job_id: str) -> None:
        if job_id in self.progress_map:
            del self.progress_map[job_id]

    def get_progress(self, job_id: str) -> dict | None:
        return self.progress_map.get(job_id)

    def __call__(self, job_id: str, value: int, state: ProgressState) -> None:
        if job_id in self.progress_map:
            self.progress_map[job_id] = {
                "state": state.value,
                "value": value,
            }


manager = Manager()
progress_instance = Progress(manager)
