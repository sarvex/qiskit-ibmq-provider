# This code is part of Qiskit.
#
# (C) Copyright IBM 2019, 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Utility functions for ``IBMQJobManager``."""

import re
from typing import Callable, Any, List, Union
from functools import wraps
from collections import Counter
from concurrent.futures import wait

from qiskit.providers.jobstatus import JobStatus

from .managedjob import ManagedJob

JOB_SET_NAME_FORMATTER = "{}_{}_"
"""Formatter for the name of a job in a job set. The first entry is the job set
name, whereas the second entry is the job's index in the job set."""
JOB_SET_NAME_RE = re.compile(r'(.*)_([0-9]+)_$')
"""Regex used to match the name of a job in a job set. The first captured group is
the job set name, whereas the second captured group is the job's index in the job set."""


def requires_submit(func: Callable) -> Callable:
    """Decorator used by ``ManagedJobSet`` to wait for all jobs to be submitted.

    Args:
        func: Function to be decorated.

    Returns:
        The decorated function.
    """
    @wraps(func)
    def _wrapper(
            job_set: 'ManagedJobSet',   # type: ignore[name-defined]
            *args: Any,
            **kwargs: Any
    ) -> Any:
        """Wrapper function.

        Args:
            job_set: Managed job set.
            args: Arguments to be passed to the decorated function.
            kwargs: Keyword arguments to be passed to the decorated function.

        Returns:
            return value of the decorated function.
        """
        futures = [managed_job.future for managed_job
                   in job_set._managed_jobs if managed_job.future]  # type: ignore[unreachable]
        wait(futures)
        return func(job_set, *args, **kwargs)

    return _wrapper


def format_status_counts(statuses: List[Union[JobStatus, None]]) -> List[str]:
    """Format summary report on job statuses.

    Args:
        statuses: Statuses of the jobs.

    Returns:
        Formatted job status report.
    """
    counts = Counter(statuses)  # type: Counter
    return [
        f"       Total jobs: {len(statuses)}",
        f"  Successful jobs: {counts[JobStatus.DONE]}",
        f"      Failed jobs: {counts[JobStatus.ERROR]}",
        f"   Cancelled jobs: {counts[JobStatus.CANCELLED]}",
        f"     Running jobs: {counts[JobStatus.RUNNING]}",
        f"     Pending jobs: {counts[JobStatus.INITIALIZING] + counts[JobStatus.VALIDATING] + counts[JobStatus.QUEUED]}",
    ]


def format_job_details(
        statuses: List[Union[JobStatus, None]],
        managed_jobs: List[ManagedJob]
) -> List[str]:
    """Format detailed report for jobs.

    Args:
        statuses: Statuses of the jobs.
        managed_jobs: Jobs being managed.

    Returns:
        Formatted job details.format_job_details
    """
    report = []
    for i, mjob in enumerate(managed_jobs):
        report.extend(
            (
                f"  experiments: {mjob.start_index}-{mjob.end_index}",
                f"    job index: {i}",
            )
        )
        if (mjob.job is None) and mjob.future \
                and (not mjob.future.done()):  # type: ignore[unreachable]
            report.append(f"    status: {JobStatus.INITIALIZING.value}")
            continue
        if mjob.submit_error is not None:
            report.append(f"    status: job submit failed: {str(mjob.submit_error)}")
            continue

        job = mjob.job
        report.extend((f"    job ID: {job.job_id()}", f"    name: {job.name()}"))
        status_txt = statuses[i].value if statuses[i] else "Unknown"
        report.append(f"    status: {status_txt}")

        if statuses[i] is JobStatus.QUEUED:
            report.append(f"    queue position: {job.queue_position()}")
        elif statuses[i] is JobStatus.ERROR:
            report.append("    error_message:")
            msg_list = job.error_message().split('\n')
            report.extend(msg.rjust(len(msg)+6) for msg in msg_list)
    return report
