# CI workflows (kept local — PAT lacks the GitHub "workflow" scope)
#
# Two workflow files sit next to this note in .github/workflows/ on the
# maintainer's machine, ready to activate:
#
#   ci.yml            engine tests + lint + dashboard build + windows check
#   docker-publish.yml  build + push api/dashboard images to GHCR on v* tags
#
# To turn CI on: copy both files into .github/workflows/ and push with a
# token that has the workflow scope (Settings ▸ Developer settings ▸ PAT).
#
# An independent template you can drop into ANY project today (no special
# scope needed if you install from git): examples/promptbreaker-example.yml
