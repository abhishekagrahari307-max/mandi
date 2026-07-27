#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  UP Mandi Dashboard — एक कमांड में GitHub Pages पर deploy
#
#  चलाने का तरीका:
#      gh auth login
#      bash deploy.sh
#
#  ज़रूरत: git + authenticated GitHub CLI (gh)
#  सुरक्षा: यह script कभी token नहीं मांगती या remote URL में नहीं डालती।
# ─────────────────────────────────────────────────────────────
set -euo pipefail

REPO_NAME="${REPO_NAME:-mandi}"
DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"

say()  { printf "\n\033[1;36m%s\033[0m\n" "$*"; }
ok()   { printf "\033[1;32m✅ %s\033[0m\n" "$*"; }
die()  { printf "\033[1;31m❌ %s\033[0m\n" "$*" >&2; exit 1; }

cd "$(dirname "$0")"
command -v git >/dev/null || die "git नहीं मिला। पहले git install करें।"
command -v gh >/dev/null || die "GitHub CLI (gh) नहीं मिला। https://cli.github.com/ से install करें।"
gh auth status >/dev/null 2>&1 || die "GitHub CLI login आवश्यक है। पहले 'gh auth login' चलाएँ।"

# ── 1. Local repository तैयार करें ──────────────────────────
if [ ! -d .git ]; then
  git init -q -b "$DEPLOY_BRANCH"
fi
git config user.name  >/dev/null 2>&1 || git config user.name  "Vijay Kumar Traders"
git config user.email >/dev/null 2>&1 || git config user.email "trader@example.com"
git add -A
git diff --staged --quiet || git commit -q -m "🌾 UP Mandi Dashboard"
ok "लोकल repo तैयार"

# ── 2. GitHub पर सुरक्षित रूप से भेजें ──────────────────────
USER=$(gh api user --jq .login)
TARGET_REPO="$USER/$REPO_NAME"
TARGET_URL="https://github.com/$TARGET_REPO.git"

say "GitHub repository तैयार कर रहे हैं..."
if ! gh repo view "$TARGET_REPO" >/dev/null 2>&1; then
  gh repo create "$REPO_NAME" --public --description "Uttar Pradesh live mandi price dashboard"
fi

if git remote get-url origin >/dev/null 2>&1; then
  CURRENT_ORIGIN=$(git remote get-url origin)
  [ "$CURRENT_ORIGIN" = "$TARGET_URL" ] \
    || die "origin पहले से किसी अन्य repository पर सेट है: $CURRENT_ORIGIN"
else
  git remote add origin "$TARGET_URL"
fi

# Push the current commit without storing a credential in .git/config.
git push -u origin "HEAD:$DEPLOY_BRANCH"

say "GitHub Pages चालू कर रहे हैं..."
gh api -X POST "repos/$TARGET_REPO/pages" \
   -f "source[branch]=$DEPLOY_BRANCH" -f 'source[path]=/' >/dev/null 2>&1 \
 || gh api -X PUT "repos/$TARGET_REPO/pages" \
      -f "source[branch]=$DEPLOY_BRANCH" -f 'source[path]=/' >/dev/null 2>&1 \
 || true

gh api -X PUT "repos/$TARGET_REPO/actions/permissions/workflow" \
   -f default_workflow_permissions=write >/dev/null 2>&1 || true

ok "Deploy हो गया!"
echo
echo "   🔗 आपका dashboard (1–2 मिनट में चालू):"
echo "      https://${USER}.github.io/${REPO_NAME}/"
echo
echo "   📱 फोन में खोलकर 'Add to Home Screen' करें"
echo "   🔄 भाव दिन में 6 बार अपने आप update होंगे"
echo
