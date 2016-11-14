reinstall:
	-pip uninstall -y chunksub
	python setup.py sdist
	pip install --user dist/chunksub-0.1.3.tar.gz
	#cd ${HOME}/.chunksub && git co config.yml
