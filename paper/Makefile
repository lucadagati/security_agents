# IEEE Transactions manuscript
MAIN := main
LATEXMK := latexmk
LATEXMK_FLAGS := -pdf -interaction=nonstopmode -halt-on-error

.PHONY: all pdf clean distclean watch

all: pdf

pdf: $(MAIN).pdf

$(MAIN).pdf: $(MAIN).tex sections/*.tex bib/references.bib figures/*.tex
	$(LATEXMK) $(LATEXMK_FLAGS) $(MAIN).tex

watch:
	$(LATEXMK) $(LATEXMK_FLAGS) -pvc $(MAIN).tex

clean:
	$(LATEXMK) -c $(MAIN).tex

distclean:
	$(LATEXMK) -C $(MAIN).tex
	rm -f $(MAIN).bbl $(MAIN).run.xml
