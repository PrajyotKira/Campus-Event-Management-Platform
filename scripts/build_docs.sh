#!/usr/bin/env bash
# Compile the LaTeX report and slides in report/ to PDF.
# Uses latexmk if installed, otherwise pdflatex (run twice so the table of
# contents and references are filled in). If neither is installed, explains how
# to use Overleaf instead.
#
# Usage:  ./scripts/build_docs.sh
set -euo pipefail

source "$(dirname "$0")/common.sh"
cd "$PROJECT_ROOT/report"

DOCS="report slides"

if command -v latexmk >/dev/null 2>&1; then
    echo "==> Building with latexmk..."
    for doc in $DOCS; do
        echo "    $doc.tex"
        # -pdf: produce a PDF; -halt-on-error: stop at the first LaTeX error.
        latexmk -pdf -interaction=nonstopmode -halt-on-error "$doc.tex" >/dev/null \
            || { echo "ERROR building $doc.tex, last lines of $doc.log:"; tail -n 25 "$doc.log"; exit 1; }
    done

elif command -v pdflatex >/dev/null 2>&1; then
    echo "==> Building with pdflatex (2 passes each)..."
    for doc in $DOCS; do
        for pass in 1 2; do
            echo "    $doc.tex (pass $pass)"
            pdflatex -interaction=nonstopmode -halt-on-error "$doc.tex" >/dev/null \
                || { echo "ERROR building $doc.tex, last lines of $doc.log:"; tail -n 25 "$doc.log"; exit 1; }
        done
    done

else
    echo "No LaTeX installation found (latexmk or pdflatex)."
    echo "Option 1: install MiKTeX (https://miktex.org) or TeX Live, then run this script again."
    echo "Option 2: use Overleaf (https://www.overleaf.com):"
    echo "   - New Project > Upload Project > upload a zip of the report/ folder"
    echo "     (report.tex, slides.tex and the figures/ folder)"
    echo "   - Compile report.tex and slides.tex with pdfLaTeX, then download the PDFs."
    exit 0
fi

echo "Done: report/report.pdf and report/slides.pdf"
