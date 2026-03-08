#!/usr/bin/env bash
# update-patches.sh — Download AMD ISP4 patch series from lore.kernel.org
# Usage: ./update-patches.sh <cover-letter-message-id>
# Deps:  b4 (dnf install b4), git
#
# Example:
#   ./update-patches.sh 20260302073020.148277-1-Bin.Du@amd.com

set -euo pipefail

REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
PATCHES_DIR="$REPO_ROOT/patches"
SPEC_FILE="$REPO_ROOT/amd-isp4-capture-kmod.spec"
TMPDIR="$(mktemp -d /tmp/update-patches.XXXXXX)"
trap 'rm -rf "$TMPDIR"' EXIT

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <lore-message-id>" >&2
    exit 1
fi
MSGID="${1#<}"; MSGID="${MSGID%>}"

command -v b4 &>/dev/null || { echo "ERROR: install b4 with: sudo dnf install b4" >&2; exit 1; }

echo "==> Checking for newer revisions..."
b4 am --check-newer-revisions "$MSGID" 2>&1 | grep -iE "newer|revision|v[0-9]" || true

echo "==> Downloading patch series: $MSGID"
B4_DIR="$TMPDIR/raw"
mkdir -p "$B4_DIR"
b4 am --no-cover -o "$B4_DIR" "$MSGID"

# b4 >= 0.14 outputs a single .mbx mailbox; older versions output individual .patch files.
# Normalise to individual files using git mailsplit when needed.
MBX=$(ls "$B4_DIR"/*.mbx 2>/dev/null | head -1)
if [[ -n "$MBX" ]]; then
    echo "==> Splitting mailbox into individual messages..."
    SPLIT_DIR="$TMPDIR/split"
    mkdir -p "$SPLIT_DIR"
    git mailsplit -o"$SPLIT_DIR" "$MBX" >/dev/null
    # rename to .patch so the loop below works uniformly
    for f in "$SPLIT_DIR"/[0-9]*; do mv "$f" "${f}.patch"; done
    B4_DIR="$SPLIT_DIR"
fi

PATCH_COUNT=$(ls "$B4_DIR"/*.patch 2>/dev/null | wc -l)
[[ "$PATCH_COUNT" -eq 0 ]] && { echo "ERROR: no patches downloaded" >&2; exit 1; }
echo "==> Downloaded $PATCH_COUNT patch(es)"

echo "==> Stripping email headers (keeping raw diff only)..."
STRIPPED="$TMPDIR/stripped"
mkdir -p "$STRIPPED"
i=0
for src in $(ls "$B4_DIR"/*.patch | sort); do
    subj=$(grep -m1 '^Subject:' "$src" \
           | sed 's/Subject: \[PATCH[^]]*\] //' \
           | tr ' /' '_-' | tr -dc 'A-Za-z0-9_-' | cut -c1-50)
    out=$(printf "%03d_%s.patch" "$i" "$subj")
    if grep -q '^diff --git' "$src"; then
        sed -n '/^diff --git /,$p' "$src" > "$STRIPPED/$out"
        echo "  $out"
        i=$((i + 1))
    else
        echo "  WARNING: no diff in $src, skipping" >&2
    fi
done
FINAL=$(ls "$STRIPPED"/*.patch 2>/dev/null | wc -l)
[[ "$FINAL" -eq 0 ]] && { echo "ERROR: no valid patches after stripping" >&2; exit 1; }

echo ""
echo "Current patches:"
ls "$PATCHES_DIR"/*.patch 2>/dev/null | xargs -I{} basename {} || echo "  (none)"
echo "New patches ($FINAL):"
ls "$STRIPPED"/*.patch | xargs -I{} basename {}

echo ""
read -rp "Replace patches/ with new content? [y/N] " yn
[[ "$yn" != "y" && "$yn" != "Y" ]] && { echo "Aborted."; exit 0; }

rm -f "$PATCHES_DIR"/*.patch
cp "$STRIPPED"/*.patch "$PATCHES_DIR/"

echo ""
echo "==> Next steps:"
echo "  1. Verify patches look correct"
echo "  2. Update Version: in $SPEC_FILE to match the vN series number"
echo "  3. Update the '# Upstream patch series:' comment with:"
echo "     https://lore.kernel.org/linux-media/${MSGID}/"
echo "  4. Add a %changelog entry"
echo "  5. git add patches/ $SPEC_FILE && git commit"
echo "  6. tito tag"
echo "  7. tito build --test --tgz && cp /tmp/tito/*.tar.gz ./amd-isp4-capture-kmod-<N>.tar.gz"
echo "  8. podman exec -i rpmbuilder-akmod-amd-isp4 rpmbuilder"
