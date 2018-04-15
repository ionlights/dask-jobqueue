import logging
import math
import os

from .core import JobQueueCluster, docstrings

logger = logging.getLogger(__name__)


@docstrings.with_indent(4)
class PBSCluster(JobQueueCluster):
    """ Launch Dask on a PBS cluster

    Parameters
    ----------
    queue : str
        Destination queue for each worker job. Passed to `#PBS -q` option.
    project : str
        Accounting string associated with each worker job. Passed to
        `#PBS -A` option.
    resource_spec : str
        Request resources and specify job placement. Passed to `#PBS -l`
        option.
    walltime : str
        Walltime for each worker job.
    job_extra : list
        List of other PBS options, for example -j oe. Each option will be
        prepended with the #PBS prefix.
    %(JobQueueCluster.parameters)s

    Examples
    --------
    >>> from dask_jobqueue import PBSCluster
    >>> cluster = PBSCluster(queue='regular', project='DaskOnPBS')
    >>> cluster.start_workers(10)  # this may take a few seconds to launch

    >>> from dask.distributed import Client
    >>> client = Client(cluster)

    This also works with adaptive clusters.  This automatically launches and
    kill workers based on load.

    >>> cluster.adapt()

    It is a good practice to define local_directory to your PBS system scratch
    directory, and you should specify resource_spec according to the processes
    and threads asked:

    >>> cluster = PBSCluster(queue='regular', project='DaskOnPBS',
                             local_directory=os.getenv('TMPDIR', '/tmp'),
                             threads=4, processes=6, memory='16GB',
                             resource_spec='select=1:ncpus=24:mem=100GB')
    """

    # Override class variables
    submit_command = 'qsub'
    cancel_command = 'qdel'

    def __init__(self,
                 queue=None,
                 project=None,
                 resource_spec=None,
                 walltime='00:30:00',
                 job_extra=[],
                 **kwargs):

        # Instantiate args and parameters from parent abstract class
        super(PBSCluster, self).__init__(**kwargs)

        # Try to find a project name from environment variable
        project = project or os.environ.get('PBS_ACCOUNT')

        header_lines = []
        # PBS header build
        if self.name is not None:
            header_lines.append('#PBS -N %s' % self.name)
        if queue is not None:
            header_lines.append('#PBS -q %s' % queue)
        if project is not None:
            header_lines.append('#PBS -A %s' % project)
        if resource_spec is None:
            # Compute default resources specifications
            ncpus = self.worker_processes * self.worker_threads
            memory = self.worker_memory * self.worker_processes
            memory_string = pbs_format_bytes_ceil(memory)
            resource_spec = "select=1:ncpus=%d:mem=%s" % (ncpus, memory_string)
            logger.info("Resource specification for PBS not set, "
                        "initializing it to %s" % resource_spec)
        header_lines.append('#PBS -l %s' % resource_spec)
        if walltime is not None:
            header_lines.append('#PBS -l walltime=%s' % walltime)
        header_lines.extend(['#PBS %s' % arg for arg in job_extra])

        # Declare class attribute that shall be overriden
        self.job_header = '\n'.join(header_lines)

        logger.debug("Job script: \n %s" % self.job_script())


def pbs_format_bytes_ceil(n):
    """ Format bytes as text
    PBS expects KiB, MiB or Gib, but names it KB, MB, GB
    Whereas Dask makes the difference between KB and KiB

    >>> pbs_format_bytes_ceil(1)
    '1B'
    >>> pbs_format_bytes_ceil(1234)
    '1234B'
    >>> pbs_format_bytes_ceil(12345678)
    '13MB'
    >>> pbs_format_bytes_ceil(1234567890)
    '1177MB'
    >>> pbs_format_bytes_ceil(15000000000)
    '14GB'
    """
    if n >= 10 * (1024**3):
        return '%dGB' % math.ceil(n / (1024**3))
    if n >= 10 * (1024**2):
        return '%dMB' % math.ceil(n / (1024**2))
    if n >= 10 * 1024:
        return '%dkB' % math.ceil(n / 1024)
    return '%dB' % n