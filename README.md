# chunksub 
*"like gnu parallel, only for qsub"*

## Installation
```
pip install chunksub
```
or use the version from github
```
git clone git@github.com:grst/chunksub.git
cd chunksub
python setup.py install
```

## Usage
Simplest case: 
```
chunksub --name my_job script.sh inputfile.txt
```
where `script.sh` takes one line of `inputfile.txt` as argument. 

A more sophistocated invocation of the `script.sh` is possible: 
```
chunksub --name my_complex_job "scipt.sh -p -s 42 --input {} --verbose" inputfile.txt
```

### Full usage information:
```
USAGE:
    chunksub --help
    chunksub [-q QUEUE -n NCPUS -w WTIME -m MEM -d WDIR -c CONFIG -t TEMPLATE 
        -s CHUNKSIZE -j JOB_DIR -X EXECUTE -b SCHEDULER] -N NAME <command> [<arguments>]
 
GRID-OPTIONS:
    -q QUEUE, --queue QUEUE     Queue name (normal/express/copyq)
    -n NCPUS, --ncpus NCPUS     Processors per node
    -w WTIME, --wtime WTIME     Walltime to request 
    -N NAME, --name NAME        Job name (will be basename of chunks & jobs)
    -m MEM, --mem MEM           RAM to request
    -d WDIR, --wdir WDIR        Job's working directory (default: ./)
 
CHUNKSUB-OPTIONS:
    -c CONFIG, --config CONFIG              Path to yaml config file [default: ~/.chunksub/config.yml]
    -t TEMPLATE, --template TEMPLATE        Jinja2 template for job file (default: ~/.chunksub/roche.template)
    -s CHUNKSIZE, --chunksize CHUNKSIZE     Number of lines per chunk (default: 16) 
    -j JOB_DIR, --job_dir JOB_DIR           Directory to save the job files. (default: ./chunksub)
    -X EXECUTE, --execute EXECUTE           Execute qsub instead of printing the command to STDOUT (default: True) 
    -b SCHEDULER, --scheduler SCHEDULER     Path to scheduler binary (default: sbatch)
```

## Use Case 
Say, we have a list of input arguments that we would like to process,
e.g. [GEO](https://www.ncbi.nlm.nih.gov/geo/) accession numbers.

```
GDS5086
GDS5074
GDS5072
GDS5070
GDS5059
GDS5058
GDS5046
GDS5045
GDS5030
[...]
```

We want to download the gene expression data of the corresponding experiment.
To this end, we have a script `download_geo.sh <ACCESSION>` that downloads and
stores the data for each accession number.

We could use either `xargs` or [`parallel`](https://www.gnu.org/software/parallel/)
for batch processing:

```
cat accession_numbers | xargs ./download_geo.sh
```

But what if we have a `qsub` based High Performance Cluster (HPC)?
This is where chunksub comes into place. It works like xargs and lets
you specify additional parameters that are forwarded to `qsub`:

```
# split the input files in chunks of 10 and submit each chunk to the cluster
cat accession_numbers | chunksub -N "download_geo" --chunksize 10 ./download_geo.sh
```

`chunksub` will create a job file for every chunk, and submit them via `qsub`/`sbatch`. At the moment, SGE, torque and slurm are supported.  

## Advanced Options
### Using the config file
`chunksub` creates the directory `~/.chunksub` on the first run. This directory contains `config.yml`, a configuration file storing 
chunksub's default parameters. The default `config.yml` looks like this

```
wdir: ./
template: ~/.chunksub/default.template
chunksize: 16
job_dir: ./chunksub
execute: yes
scheduler: qsub
```

All options you can specify on command line, you can add to the config file. For example you can add

```
mem: 16G
queue: batch
```

You can also create project-specific config files and load them with the `-c` parameter. 


### Adjusting the template file
On the first run, `chunksub` creates a job template file at `~/.chunksub/default.template`. It should work for most use cases on SGE, torque and slurm clusters. If you need to fine-tune grid options or simply run commands on the chunks in a different way, you can modify the template. There is a collection of template files in [`chunksub/job_templates`](chunksub/job_templates) which you can adjust for your needs. 
