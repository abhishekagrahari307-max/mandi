#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  UP Mandi Dashboard — एक कमांड में GitHub Pages पर deploy
#
#  चलाने का तरीका:
#      bash deploy.sh
#
#  ज़रूरत:  git  +  (gh CLI  या  GitHub token)
# ─────────────────────────────────────────────────────────────
set -euo pipefail

REPO_NAME="${REPO_NAME:-mandi}"

say()  { printf "\n\033[1;36m%s\033[0m\n" "$*"; }
ok()   { printf "\033[1;32m✅ %s\033[0m\n" "$*"; }
die()  { printf "\033[1;31m❌ %s\033[0m\n" "$*" >&2; exit 1; }

cd "$(dirname "$0")"
command -v git >/dev/null || die "git नहीं मिला। पहले git install करें।"

# ── 1. git repo तैयार ────────────────────────────────────────
if [ ! -d .git ]; then
  git init -q -b main
fi
git config user.name  >/dev/null 2>&1 || git config user.name  "Vijay Kumar Traders"
git config user.email >/dev/null 2>&1 || git config user.email "trader@example.com"
git add -A
git diff --staged --quiet || git commit -q -m "🌾 UP Mandi Dashboard"
git branch -M main
ok "लोकल repo तैयार"

# ── 2. GitHub पर भेजें ───────────────────────────────────────
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  say "gh CLI मिला — repo बना रहे हैं..."
  USER=$(gh api user --jq .login)
  gh repo view "$USER/$REPO_NAME" >/dev/null 2>&1 \
    || gh repo create "$REPO_NAME" --public --source=. --remote=origin
  git remote get-url origin >/dev/null 2>&1 \
    || git remote add origin "https://github.com/$USER/$REPO_NAME.git"
  git push -u origin main

  say "GitHub Pages चालू कर रहे हैं..."
  gh api -X POST "repos/$USER/$REPO_NAME/pages" \
     -f 'source[branch]=main' -f 'source[path]=/' >/dev/null 2>&1 \
   || gh api -X PUT "repos/$USER/$REPO_NAME/pages" \
        -f 'source[branch]=main' -f 'source[path]=/' >/dev/null 2>&1 || true

  gh api -X PUT "repos/$USER/$REPO_NAME/actions/permissions/workflow" \
     -f default_workflow_permissions=write >/dev/null 2>&1 || true

else
  say "gh CLI नहीं है — token से भेजते हैं"
  echo "Token यहाँ बनाएँ (scope: repo + workflow):"
  echo "   https://github.com/settings/tokens/new?scopes=repo,workflow&description=mandi"
  echo
  read -rp "GitHub username: " USER
  read -rsp "GitHub token (दिखेगा नहीं): " TOKEN; echo
  [ -n "$USER" ] && [ -n "$TOKEN" ] || die "username/token खाली है"

  curl -s -o /dev/null -H "Authorization: token $TOKEN" \
       -d "{\"name\":\"$REPO_NAME\",\"private\":false}" \
       https://api.github.com/user/repos

  git remote remove origin 2>/dev/null || true
  git remote add origin "https://${USER}:${TOKEN}@github.com/${USER}/${REPO_NAME}.git"
  git push -u origin main

  curl -s -o /dev/null -X POST \
    -H "Authorization: token $TOKEN" -H "Accept: application/vnd.github+json" \
    -d '{"source":{"branch":"main","path":"/"}}' \
    "https://api.github.com/repos/$USER/$REPO_NAME/pages"

  curl -s -o /dev/null -X PUT \
    -H "Authorization: token $TOKEN" -H "Accept: application/vnd.github+json" \
    -d '{"default_workflow_permissions":"write"}' \
    "https://api.github.com/repos/$USER/$REPO_NAME/actions/permissions/workflow"

  # token को remote URL से हटाएँ (सुरक्षा)
  git remote set-url origin "https://github.com/${USER}/${REPO_NAME}.git"
fi

ok "Deploy हो गया!"
echo
echo "   🔗 आपका dashboard (1–2 मिनट में चालू):"
echo "      https://${USER}.github.io/${REPO_NAME}/"
echo
echo "   📱 फोन में खोलकर 'Add to Home Screen' करें"
echo "   🔄 रोज़ सुबह 6 बजे अपने आप update होगा"
echo
