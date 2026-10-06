# Git workflow

- Keep each meaningful change in a separate commit and preserve those commits when merging branches into `main`.
- Use a normal merge for pull requests. Do not use squash merges, `git merge --squash`, or squash/rewrite existing commits unless the user explicitly requests it.
- Use the repository's configured author identity for new commits; do not override it with another email address.
- GitHub commit contributions require commits to reach the default branch and their author email to be associated with the author's GitHub account. Pushing a feature branch alone does not satisfy the default-branch requirement.
