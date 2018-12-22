Notes to self about making a release:

1. Make a commit bumping peru/VERSION. Note changes in the commit message.
2. Make a tag pointing to that commit named after the new version.
3. `git push && git push --tags`
4. Copy the commit message to https://groups.google.com/forum/#!forum/peru-tool.
5. `python3 setup.py sdist`
6. `twine upload dist/*`
  - Full instructions here: https://packaging.python.org/tutorials/packaging-projects
7. Bump the AUR package.
  - `git clone ssh+git://aur@aur.archlinux.org/peru`
    - Update the pkgver and pkgrel.
    - Update the package hash with the help of `makepkg -g`.
    - `makepkg -d && makepkg --printsrcinfo > .SRCINFO`
    - Commit and push.
  - `git clone ssh+git://aur@aur.archlinux.org/peru-git`
    - Same procedure, but leave this one alone if it's just a version bump.
8. Poke Sean to update the Ubuntu PPA :)
