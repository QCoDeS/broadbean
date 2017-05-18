# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line.
SPHINXOPTS    =
SPHINXBUILD   = python -msphinx
SPHINXPROJ    = broadbean
SOURCEDIR     = source
BUILDDIR      = build
GH_PAGES_SOURCES = docs broadbean

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile


.PHONY: html
html:
	$(SPHINXBUILD) -b html $(ALLSPHINXOPTS) $(BUILDDIR)/html
	@echo
	@echo "Build finished. The HTML pages are in $(BUILDDIR)/html."


gh-pages:
	git config --global user.email "bot@travics.com"
	git config --global user.name "Documentation Bot"
	git remote add upstream https://${GITHUB_API_KEY}@github.com/QCoDeS/broadbean.git
	git fetch upstream
	git checkout gh-pages
	rm -rf ./*
	git checkout master $(GH_PAGES_SOURCES)
	git reset HEAD
	cd docs/source && make html && \
	mv -fv $(BUILDDIR)/html/* ../
	rm -rf $(GH_PAGES_SOURCES) build
	git add -A
	git commit -m "Generated gh-pages for `git log master -1 --pretty=short \
	--abbrev-commit`" && git push https://${GITHUB_API_KEY}@github.com/QCoDeS/broadbean.git gh-pages ; git checkout master
