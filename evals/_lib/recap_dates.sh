# evals/_lib/recap_dates.sh — commits at real relative dates, for the recap-*
# scaffolds (sourced after helpers.sh). The recap window logic reads dates
# relative to today, so every timestamp here is computed at scaffold time.

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
