# chunksub 
*"like gnu parallel, only for qsub"*

## Installation
Will end up on PyPI at some point...

## Usage
```
USAGE:
    chunksub --help
    chunksub [-q QUEUE -n NCPUS -w WTIME -m MEM -d WDIR -c CONFIG -t TEMPLATE -s CHUNKSIZE -j JOB_DIR -X EXECUTE] -N NAME <command> [<arguments>]

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

`chunksub` will create a job file for every chunk, and submit them via `qsub`. Both SGE and Torque clusters are submitted. 

## Advanced Options
### Creating a config file
Most of the `qsub`-parameters do not change for a certain environment or project. Instead of typing them all over again, you can store them in a configuration file and load it with the `-c` parameter. If no config file is specified, `chunksub` will look at `~/.chunksub/config`

```
project: aa1
queue: normal
ncpus: 16
wtime: 1:00:00
mem: 1G
wdir: .
```

### Adjusting the template file
The integrated template ([`job_template`](job_template)) should work for most use cases on a SGE and torque cluster. If you need to change the way your command is executed of adjust advanced grid options, you can create your own template file and load it with the `-t` parameter.  
