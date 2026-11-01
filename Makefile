.PHONY: all data pdf previews clean

all: data pdf previews

data:            ## regenerate JSON, markdown and the typst data file
	python3 tools/build.py
	python3 tools/verify.py

pdf: data        ## typeset the phone PDF
	typst compile build/doc.typ jesus-in-john.pdf

previews: pdf    ## refresh the README preview images
	typst compile --format png --ppi 150 --pages 1 build/doc.typ docs/preview-cover.png
	typst compile --format png --ppi 150 --pages 12 build/doc.typ docs/preview-page.png

clean:
	rm -f jesus-in-john.pdf docs/preview-*.png
