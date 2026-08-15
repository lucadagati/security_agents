# IEEE Transactions manuscript

LaTeX project for the journal paper:

**Co-Evolutionary Security of Autonomous AI Agents: Emergent Attack and Defense Strategies in Multi-Agent Cyber Environments**

Formatted with [`IEEEtran`](https://ctan.org/pkg/ieeetran) in *journal* mode (IEEE Transactions). Natural target venues:

- IEEE Transactions on Dependable and Secure Computing (TDSC) — add the `compsoc` class option
- IEEE Transactions on Information Forensics and Security (TIFS)
- IEEE Transactions on Artificial Intelligence

The software artefact that implements the framework lives in the parent repository (`../`).

## Build

Requires TeX Live with `IEEEtran`, `pgfplots`, `amsmath`, and `algorithm2e`/`algorithmicx`.

```bash
cd paper
make          # latexmk → main.pdf
make watch    # rebuild on change
make distclean
```

Or:

```bash
pdflatex main && bibtex main && pdflatex main && pdflatex main
```

## Layout

```
main.tex                 entry point (IEEE preamble, title, authors)
sections/                body (one file per section)
figures/                 TikZ/PGF figures included from the body
bib/references.bib       BibTeX database (IEEEtran.bst)
Makefile
```

## Author block

Edit the `\author{...}` and `\thanks{...}` fields in `main.tex` before submission. For TDSC, change the document class to:

```latex
\documentclass[10pt,journal,compsoc]{IEEEtran}
```

## Status of the results

Section~VII currently reports the **1-versus-1 adaptation ladder** (static / episodic / persistent) run on the simulator. The E1--E8 population matrix, LLM baselines (B3--B5 on Ollama/L40), and the Kubernetes cyber range are specified in the methodology and marked as the remaining experimental programme.
