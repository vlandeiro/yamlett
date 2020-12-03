test:
	pytest

coverage:
	coverage run --source yamlett -m pytest
	coverage report
	coverage html
	open htmlcov/index.html

format:
	black yamlett tests

check-format:
	black --check yamlett tests

lint:
	flake8 yamlett tests

check-lint:
	flake8 yamlett tests --count --select=E9,F63,F7,F82 --show-source --statistics

build:
	poetry build

clean: clean-build clean-pyc clean-test ## remove all build, test, coverage and Python artifacts

clean-build: ## remove build artifacts
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +

clean-pyc: ## remove Python file artifacts
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

clean-test: ## remove test and coverage artifacts
	rm -fr .tox/
	rm -f .coverage
	rm -fr htmlcov/
	rm -fr .pytest_cache
