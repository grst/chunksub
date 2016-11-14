#!/usr/bin/env python
"""
USAGE:
    chunksub --help
    chunksub [-q QUEUE -n NCPUS -w WTIME -m MEM -d WDIR \
-c CONFIG -t TEMPLATE -s CHUNKSIZE -j JOB_DIR -X EXECUTE -b SCHEDULER] \
-N NAME <command> [<arguments>]

GRID-OPTIONS:
    -q QUEUE, --queue QUEUE     Queue name (normal/express/copyq)
    -n NCPUS, --ncpus NCPUS     Processors per node
    -w WTIME, --wtime WTIME     Walltime to request
    -N NAME, --name NAME        Job name (will be basename of chunks & jobs)
    -m MEM, --mem MEM           RAM to request
    -d WDIR, --wdir WDIR        Job's working directory (default: {wdir})

CHUNKSUB-OPTIONS:
    -c CONFIG, --config CONFIG              Path to yaml config file [default: {config}]
    -t TEMPLATE, --template TEMPLATE        Jinja2 template for job file (default: {template})
    -s CHUNKSIZE, --chunksize CHUNKSIZE     Number of lines per chunk (default: {chunksize})
    -j JOB_DIR, --job_dir JOB_DIR           Directory to save the job files. (default: {job_dir})
    -X EXECUTE, --execute EXECUTE           Execute qsub instead of printing the command to STDOUT (default: {execute})
    -b SCHEDULER, --scheduler SCHEDULER     Path to scheduler binary (default: {scheduler})
"""

from __future__ import print_function

from copy import copy
import docopt
import jinja2
import os
from os import path
from sys import stdin, stderr, argv
import pkg_resources
import yaml
from pprint import pprint
from subprocess import call
from shutil import copyfile
import tempfile
import io

# the .chunksub directory, where job templates and default settings live.
CONFIG_DIR = "~/.chunksub"
DEFAULT_CONFIG_FILE = CONFIG_DIR + "/config.yml"

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
    'execute': lambda x: True if str(x).lower() in ['y', 'yes', 'true'] else False,
    'scheduler': str
}


def init():
    """initalize the chunksub directory on the first run."""
    cs_dir = path.expanduser(CONFIG_DIR)
    config_file = path.expanduser(DEFAULT_CONFIG_FILE)
    try:
        if not path.isdir(cs_dir):
            os.mkdir(cs_dir)
            copyfile(pkg_resources.resource_filename(__name__, "default_config.yml"),
                     config_file)
            copyfile(pkg_resources.resource_filename(__name__, "job_templates/default.template"),
                     path.join(cs_dir, "default.template"))
            print("INFO: created config directory {}. You can adjust default "
                  "settings and job templates there. ".format(CONFIG_DIR))
    except IOError as ex:
        print("ERROR: could not create config directory. " + str(ex))


def get_job_template(fname):
    """Create job template with jinja2"""
    fname = path.expanduser(fname)
    with open(fname) as tfh:
        template = tfh.read()
    return jinja2.Template(template)


def load_config(fname):
    """Load config from yaml"""
    fname = path.expanduser(fname)
    try:
        with open(fname) as cfh:
            config = yaml.load(cfh)
    except IOError:
        print("ERROR: non-existant config file", fname, file=stderr)
        exit(1)
    return config



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
        "-b", 'sbatch', \
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
     'scheduler': 'sbatch',
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


def run_job_files(job_files, bin="qsub", execute=True):
    for job_file in job_files:
        if execute:
            call([bin, job_file])
        else:
            print("{} {}".format(bin, job_file))


def save_command_file(path):
    """
    Store the orginal chunksub command as typed in the terminal
    as a script to make it easy to re-execute the command.
    """
    command = " ".join(['"{}"'.format(x) if " " in x else x for x in argv])
    with open(path, 'w') as cmd_file:
        cmd_file.write('#!/bin/bash \n')
        cmd_file.write(command)
        cmd_file.write('\n')


def main():
    """
    Read an argument file, split it into chunks and create a job file
    for each chunk.
    """
    init()
    default_config = load_config(DEFAULT_CONFIG_FILE)
    opts = docopt.docopt(__doc__.format(config=DEFAULT_CONFIG_FILE, **default_config))
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

    # store the original command as script
    save_command_file(path.join(chunksub_dir, "cs_command.sh"))

    # run jobs
    run_job_files(job_files, config['scheduler'], config['execute'])

    config['arg_file'].close()

if __name__ == '__main__':
    main()
