#!/bin/bash

# Install Sphinx if not already installed
pip install sphinx sphinx_rtd_theme

# Build the documentation
cd docs
make html

# Start a simple HTTP server to serve the docs
cd build/html
python -m http.server 8080
