#!/usr/bin/env python
"""
USAGE:
    chunksub --help
    chunksub [-q QUEUE -n NCPUS -w WTIME -m MEM -d WDIR \
-c CONFIG -t TEMPLATE -s CHUNKSIZE -j JOB_DIR -X EXECUTE] \
-N NAME <command> [<arguments>]

GRID-OPTIONS:
    -q QUEUE, --queue QUEUE     Queue name (normal/express/copyq)
    -n NCPUS, --ncpus NCPUS     Processors per node
    -w WTIME, --wtime WTIME     Walltime to request
    -N NAME, --name NAME        Job name (will be basename of chunks & jobs)
    -m MEM, --mem MEM           RAM to request
    -d WDIR, --wdir WDIR        Job's working directory [default: ./]

CHUNKSUB-OPTIONS:
    -c CONFIG, --config CONFIG              Path to yaml config file [default: ~/.chunksub/config]
    -t TEMPLATE, --template TEMPLATE        Jinja2 template for job file (default: integrated template)
    -s CHUNKSIZE, --chunksize CHUNKSIZE     Number of lines per chunk [default: 16]
    -j JOB_DIR, --job_dir JOB_DIR           Directory to save the job files. [default: ./chunksub]
    -X EXECUTE, --execute EXECUTE           Execute qsub instead of printing the command to STDOUT [default: yes]
"""

from __future__ import print_function

from copy import copy
import docopt
import jinja2
import os
from os import path
from sys import stdin, stderr
import pkg_resources
import yaml
from pprint import pprint
from subprocess import call
import tempfile
import io


CONFIG_FIELDS = {
    'queue': str,
    'ncpus': int,
    'wtime': str,
    'name': str,
    'mem': str,
    'wdir': str,
    'template': str,
    'chunksize': int,
    'job_dir': str,
    'execute': lambda x: True if x.lower() in ['y', 'yes', 'true'] else False
}


def get_job_template(fname):
    """Create job template with jinja2"""
    fname = path.expanduser(fname)
    with open(fname) as tfh:
        template = tfh.read()
    return jinja2.Template(template)


def load_config(fname):
    """Load config from yaml"""
    fname = path.expanduser(fname)
    if path.exists(fname):
        try:
            with open(fname) as cfh:
                config = yaml.load(cfh)
        except IOError:
            print("ERROR: non-existant config file", fname, file=stderr)
            exit(1)
        return config
    else:
        return {}


def make_config(opts):
    """
    Parses the CLI and loads the config dict.

    >>> argfile = tempfile.NamedTemporaryFile()
    >>> argv = [ \
        "-q", "the_queue", \
        "-w", "12:13:42", \
        "--ncpus", "8", \
        "-m4G", \
        "--wdir=/tmp/test", \
        "-N", "the_name", \
        "-c", "/tmp/config.yaml", \
        "-t", "/tmp/template.sh", \
        "-s", "16", \
        "--job_dir", "/tmp/job", \
        "-X", 'yes', \
        "echo", \
        argfile.name \
    ]
    >>> opts = docopt.docopt(__doc__, argv = argv)
    >>> pprint(make_config(opts))  # doctest:+ELLIPSIS
    {'arg_file': <_io.TextIOWrapper name='...' mode='r' encoding='UTF-8'>,
     'chunksize': 16,
     'command': 'echo {}',
     'execute': True,
     'job_dir': '/tmp/job',
     'mem': '4G',
     'name': 'the_name',
     'ncpus': 8,
     'queue': 'the_queue',
     'template': '/tmp/template.sh',
     'wdir': '/tmp/test',
     'wtime': '12:13:42'}
    """
    # load config file if specified
    if opts['--config']:
        config_file = opts['--config']
        config = load_config(config_file)
    else:
        config = {}

    # command line options override those from the yaml config
    for cli, cfg in CONFIG_FIELDS.items():
        if opts["--" + cli]:
            config[cli] = opts["--" + cli]

    # the command to execute with qsub
    config['command'] = opts['<command>']
    # append placeholder for xargs if not already in command.
    if '{}' not in config['command']:
        config['command'] += " {}"

    # file containing the argument list
    if opts['<arguments>'] is None:
        config['arg_file'] = stdin
    else:
        config['arg_file'] = open(opts['<arguments>'])

    # sanitize config fields
    for field, sanitiser in CONFIG_FIELDS.items():
        if field not in config:
            config[field] = None
        else:
            config[field] = sanitiser(config[field])

    # force absolute paths
    if config['wdir'].startswith('.'):
        config['wdir'] = path.abspath(config['wdir'])
    if config['job_dir'].startswith('.'):
        config['job_dir'] = path.abspath(config['job_dir'])

    # load default template if not specified
    if config['template'] is None:
        config['template'] = pkg_resources.resource_filename(__name__, "job_template")

    return config


def get_file_name(dir, n, ext=None):
    """
    Retrieve full filename for an index number.

    >>> wd = "/tmp/user"
    >>> get_file_name(wd, 5, ext=".job")
    '/tmp/user/0005.job'
    """
    namer = path.join(dir, "{:04d}")
    if ext is not None:
        namer += ext
    return namer.format(n)


def make_chunks(chunksub_dir, arg_fileh, chunk_size):
    """
    Read an argument file and split it into chunks.

    Args:
        chunksub_dir: chunksub working directory. Create the chunk files there.
        arg_fileh: Filehandle of the input file. Will be split into chunks.
        chunk_size: number of lines per output file.

    Yields:
        File name of a chunk file.

    >>> chunksub_dir = "/tmp/chunksub"
    >>> os.makedirs(chunksub_dir, exist_ok=True)
    >>> argfile = io.StringIO("\\n".join(str(x) for x in range(50)))
    >>> files = [file for file in make_chunks(chunksub_dir, argfile, chunk_size=10)]
    >>> files
    ['/tmp/chunksub/0000.chunk', '/tmp/chunksub/0001.chunk', '/tmp/chunksub/0002.chunk', '/tmp/chunksub/0003.chunk', '/tmp/chunksub/0004.chunk']
    >>> all([os.path.isfile(file) for file in files])
    True
    """
    chunk_idx = 0
    chunk_fh = None
    for idx, record in enumerate(arg_fileh):
        if idx % chunk_size == 0:
            if chunk_fh is not None:
                chunk_fh.close()
            chunk_file = get_file_name(chunksub_dir, chunk_idx, ".chunk")
            chunk_fh = open(chunk_file, 'w')
            chunk_idx += 1
            yield chunk_file
        chunk_fh.write(record)


def run_job_files(job_files, execute=True):
    for job_file in job_files:
        if execute:
            call(["qsub", job_file])
        else:
            print("qsub {}".format(job_file))


def main():
    """
    Read an argument file, split it into chunks and create a job file
    for each chunk.
    """
    opts = docopt.docopt(__doc__)
    config = make_config(opts)
    print("CONFIGURATION:")
    pprint(config)
    template = get_job_template(config['template'])

    # make chunksub working directory (create .job and .chunk files there)
    chunksub_dir = path.join(config['wdir'], config['job_dir'], config['name'])
    if not path.isdir(chunksub_dir):
        os.makedirs(chunksub_dir)

    # split argument file into chunks and create job files.
    job_files = []
    for job_id, chunk_file in enumerate(make_chunks(
            chunksub_dir, config['arg_file'], config['chunksize'])):
        this_config = copy(config)
        this_config['chunk_file'] = chunk_file
        this_config['job_id'] = job_id 
        this_config['stdout'] = get_file_name(chunksub_dir, job_id, ".out")
        this_config['stderr'] = get_file_name(chunksub_dir, job_id, ".err")
        job_file = get_file_name(chunksub_dir, job_id, ".job")
        with open(job_file, 'w') as jfh:
            jfh.write(template.render(**this_config) + '\n')
        job_files.append(job_file)

    # run jobs
    run_job_files(job_files, config['execute'])

    config['arg_file'].close()

if __name__ == '__main__':
    main()
