from distutils.core import setup
from setuptools import find_packages

setup(
    name='chunksub',
    version='0.1.2',
    packages = find_packages(),
    description='Submit jobs in chunks on a qsub-based cluster. *Like `parallel` only for qsub*',
    author='Gregor Sturm',
    author_email='gregor.sturm@cs.tum.edu',
    url='https://github.com/grst/chunksub',  # use the URL to the github repo
    keywords=['bioinformatics', 'sge', 'torque', 'hpc'],  # arbitrary keywords
    license='GPLv3',
    install_requires=[
        'jinja2',
        'pyyaml',
        'docopt'
    ],
    classifiers=[],
    entry_points={
        'console_scripts': ['chunksub=chunksub.chunksub:main'],
    },
    include_package_data=True
)
