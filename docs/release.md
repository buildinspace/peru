Notes to self about making a release:

1. Make a commit bumping peru/VERSION. Note changes in the commit message.
2. Make a tag pointing to that commit named after the new version.
3. `git push && git push --tags`
4. Copy the commit message to https://groups.google.com/forum/#!forum/peru-tool.
5. `python3 setup.py register sdist upload`
6. Bump the AUR package.
  - `git clone ssh+git://aur@aur.archlinux.org/peru-git`
  - `makepkg -d && mksrcinfo`
  - Commit and push.
7. Poke Sean to update the Ubuntu PPA :)
