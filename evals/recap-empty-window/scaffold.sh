#!/usr/bin/env bash
# A storefront repo on main whose only activity yesterday, from the git user
# (Jordan Lee, jordan@example.com), is a merge commit bringing in teammate Alice
# Chen's feat/billing-export branch (two of her commits, also from
# yesterday). The user's real work sits outside the window: a commit 3 days
# ago (avatar upload) and one from today (avatar size limit), plus staged,
# uncommitted avatar-crop work. So "yesterday" has nothing for the user to
# report once merges and other authors are excluded.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/../_lib/helpers.sh"

# when DAYS_AGO HOUR MINUTE: local timestamp DAYS_AGO days before today at
# HOUR:MINUTE, so the recap window logic runs against real relative dates.
when() {
    date -v-"$1"d -v"$2"H -v"$3"M -v0S '+%Y-%m-%dT%H:%M:%S' 2>/dev/null \
        || date -d "$(date +%F) $2:$3 $1 days ago" '+%Y-%m-%dT%H:%M:%S'
}

# commit_at TIMESTAMP WHO SUBJECT [BODY]: stage everything and commit it as
# WHO (me = the repo's git user, alice = a teammate) at TIMESTAMP.
commit_at() {
    local ts="$1" who="$2" subject="$3" body="${4:-}" name email
    case "$who" in
        me) name="Jordan Lee"; email="jordan@example.com" ;;
        alice) name="Alice Chen"; email="alice@example.com" ;;
        *) echo "commit_at: unknown author $who" >&2; return 1 ;;
    esac
    git add -A
    local msg=(-m "$subject")
    [ -n "$body" ] && msg+=(-m "$body")
    GIT_AUTHOR_NAME="$name" GIT_AUTHOR_EMAIL="$email" \
    GIT_COMMITTER_NAME="$name" GIT_COMMITTER_EMAIL="$email" \
    GIT_AUTHOR_DATE="$ts" GIT_COMMITTER_DATE="$ts" \
        git commit -q "${msg[@]}"
}

# Backdate eval_repo's root commit so it never lands in a recap window.
backdate_root() {
    local ts; ts="$(when 30 9 0)"
    GIT_COMMITTER_DATE="$ts" git commit -q --amend --no-edit --allow-empty --date "$ts"
}

# A timestamp from today that is never in the future and never yesterday.
today_recent() {
    python3 -c 'import datetime as d; n = d.datetime.now(); m = n.replace(hour=0, minute=0, second=0, microsecond=0); print(max(m + d.timedelta(seconds=30), n - d.timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S"))'
}

eval_repo
backdate_root
eval_node_project storefront
eval_write src/profile/avatar.ts <<'EOF'
export type Avatar = { userId: string; bytes: Uint8Array; contentType: string };

export function acceptAvatar(userId: string, bytes: Uint8Array, contentType: string): Avatar {
  if (!contentType.startsWith("image/")) throw new Error(`avatar: ${contentType} is not an image`);
  return { userId, bytes, contentType };
}
EOF
commit_at "$(when 3 11 0)" me "feat(profile): avatar upload"

git switch -q -c feat/billing-export
eval_write src/billing/invoicePdf.ts <<'EOF'
export function invoicePdf(invoiceId: string, lines: string[]): Uint8Array {
  return new TextEncoder().encode(`%PDF-1.7 invoice ${invoiceId}\n${lines.join("\n")}`);
}
EOF
commit_at "$(when 1 10 0)" alice "feat(billing): export invoices as PDF" "SHOP-212"
python3 - <<'PY'
from pathlib import Path
p = Path("src/billing/invoicePdf.ts")
p.write_text(p.read_text().replace('lines.join("\\n")', 'lines.map((l, i) => (i > 0 && i % 40 === 0 ? `\\f${l}` : l)).join("\\n")'))
PY
commit_at "$(when 1 11 30)" alice "fix(billing): page breaks in long invoices" "SHOP-212"
git switch -q main
ts="$(when 1 16 0)"
GIT_AUTHOR_DATE="$ts" GIT_COMMITTER_DATE="$ts" git merge -q --no-ff feat/billing-export -m "Merge branch 'feat/billing-export'"
git branch -q -D feat/billing-export

python3 - <<'PY'
from pathlib import Path
p = Path("src/profile/avatar.ts")
p.write_text(p.read_text().replace(
    '  if (!contentType.startsWith("image/")) throw new Error(`avatar: ${contentType} is not an image`);\n',
    '  if (!contentType.startsWith("image/")) throw new Error(`avatar: ${contentType} is not an image`);\n'
    '  if (bytes.byteLength > 5 * 1024 * 1024) throw new Error(`avatar: ${bytes.byteLength} bytes is over the 5 MB upload limit`);\n'))
PY
commit_at "$(today_recent)" me "fix(profile): reject avatars over 5 MB"

eval_write src/profile/crop.ts <<'EOF'
export type Crop = { x: number; y: number; size: number };

export function centerCrop(width: number, height: number): Crop {
  const size = Math.min(width, height);
  return { x: (width - size) / 2, y: (height - size) / 2, size };
}
EOF
git add src/profile/crop.ts
