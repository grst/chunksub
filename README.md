# chunksub 
[work in progress]

*"like gnu parallel, only for qsub"*

## Installation
Will end up on PyPI at some point...

## Usage
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
cat accession_numbers | chunksub -N "download_geo" -l 10 ./download_geo.sh
```

