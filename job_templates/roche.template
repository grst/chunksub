#!/bin/bash
# Grid engine active comments
# see comparison on https://kb.iu.edu/d/avgl

{% if queue is not none %}
#PBS -q {{ queue }}
#$ -q {{ queue }}
{% endif %}
{% if ncpus is not none %}
#PBS -l nodes=1:ppn={{ ncpus }}
#$ -pe smp {{ ncpus }}
{% endif %}
{% if wtime is not none %}
#PBS -l walltime={{ wtime }}
#$ -l time={{ wtime }}
{% endif %}
{% if name is not none %}
#PBS -N {{ name }}_{{ job_id }}
#$ -N {{ name }}_{{ job_id }}
{% endif %}
{% if mem is not none %}
#PBS -l mem={{ mem }}
#$ -l vf={{ mem }}
{% endif %}
#PBS -e /dev/null
#PBS -o /dev/null

#$ -wd {{ wdir }}
cd {{ wdir }}

ml use /apps64/EasyBuild-Apps/modules/all/
ml load bi-R-3.1.3
ml load Anaconda3 

cat {{ chunk_file}} | xargs -I '{}' {{ command }} > {{ stdout }} 2> {{stderr}}

