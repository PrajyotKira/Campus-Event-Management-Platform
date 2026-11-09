#!/usr/bin/env bash
# Compile all LaTeX documentation to PDF. Each PDF is written next to its .tex file.
#   report/report.tex             project report
#   report/slides.tex             Beamer presentation
#   docs/user_manual.tex          User Manual
#   docs/installation_guide.tex   Installation & Operations Guide
#   docs/developer_guide.tex      Developer Guide
#   docs/test_report.tex          Test Plan & Report
# Uses latexmk if installed, otherwise pdflatex (run twice so the table of
# contents and page references are filled in). If neither is installed, explains
# how to use Overleaf instead.
#
# Usage:  ./scripts/build_docs.sh
set -euo pipefail

source "$(dirname "$0")/common.sh"
cd "$PROJECT_ROOT"

# folder/name of every document (without .tex)
DOCS="report/report report/slides docs/user_manual docs/installation_guide docs/developer_guide docs/test_report"

# build_one <folder> <name> <command...>: run a LaTeX command inside the document's folder
# (so it finds figures/ and campusdoc.sty) and show the end of the log if it fails.
build_one() {
    local folder="$1" name="$2"
    shift 2
    ( cd "$folder" && "$@" "$name.tex" >/dev/null 2>&1 ) \
        || { echo "ERROR building $folder/$name.tex, last lines of the log:"; tail -n 25 "$folder/$name.log"; exit 1; }
}

if command -v latexmk >/dev/null 2>&1; then
    echo "==> Building with latexmk..."
    for doc in $DOCS; do
        echo "    $doc.tex"
        # -pdf: produce a PDF; -halt-on-error: stop at the first LaTeX error.
        build_one "$(dirname "$doc")" "$(basename "$doc")" \
            latexmk -pdf -interaction=nonstopmode -halt-on-error
    done

elif command -v pdflatex >/dev/null 2>&1; then
    echo "==> Building with pdflatex (2 passes each)..."
    for doc in $DOCS; do
        for pass in 1 2; do
            echo "    $doc.tex (pass $pass)"
            build_one "$(dirname "$doc")" "$(basename "$doc")" \
                pdflatex -interaction=nonstopmode -halt-on-error
        done
    done

else
    echo "No LaTeX installation found (latexmk or pdflatex)."
    echo "Option 1: install MiKTeX (https://miktex.org) or TeX Live, then run this script again."
    echo "Option 2: use Overleaf (https://www.overleaf.com):"
    echo "   - New Project > Upload Project > upload a zip containing the report/ and docs/ folders"
    echo "     side by side (the guides in docs/ use the screenshots in report/figures/)"
    echo "   - Compile each .tex file with pdfLaTeX, then download the PDFs."
    exit 0
fi

echo "Done. PDFs:"
for doc in $DOCS; do
    echo "  $doc.pdf"
done
