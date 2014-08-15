# peru [![Build Status](https://travis-ci.org/buildinspace/peru.svg?branch=master)](https://travis-ci.org/buildinspace/peru) [![Coverage Status](https://img.shields.io/coveralls/buildinspace/peru.svg)](https://coveralls.io/r/buildinspace/peru)

##### Maybe sometimes better than copy-paste.

Peru is a tool for including other people's code in your projects. It's a lot
like [git submodules](http://git-scm.com/book/en/Git-Tools-Submodules), except
that peru stays out of the way of your other tools. You write a `peru.yaml`
file and then run peru when you feel like it, like in your build scripts or in
your source control hooks. Your projects can live in git, hg, svn, tarballs,
whatever. And your dependencies can too.

## Why?

There are so many tools for grabbing code. [Maven](http://maven.apache.org/)
downloads JARs. The [Go tool](http://golang.org/cmd/go/) clones libraries from
GitHub. [Vundle](https://github.com/gmarik/Vundle.vim) installs your vim
plugins. They each solve the same problem for different languages and tools.
But peru is all about fetching, and that lets us get a few things right:

- **Reproducibility.** When you check out an old version of your code, you can
  get exactly the same dependencies as when you wrote that code.
- **Speed.** Fetches run in parallel, everything is cached, and we use git
  internally for heavy lifting.
- **Dubious features.** Peru can automatically update your `peru.yaml` file
  with the latest versions of your dependencies. Peru can pick specific files
  out of a tree, or mix multiple trees into a single directory.

There's another class of tools, like git submodules and Google's
[Repo](http://source.android.com/source/developing.html), that do fetching as
part of your source control. These tend to break sweet features like `git
bisect`.  Peru leaves your source control the hell alone.

## Installation

Until we make spiffy packages, just clone this repo and use the `peru.sh`
script. If you like, you can symlink that to something like `~/bin/peru`. The
dependencies are just **python3 (>=3.3)** and **git**, though if you're going
to fetch from **hg** or **svn** you'll need those too.

## Getting Started

Here's the peru version of the [first git submodules
example](http://git-scm.com/book/en/Git-Tools-Submodules#Starting-with-Submodules)
from the [Git Book](http://git-scm.com/book). We're going to add the Rack
library to our project. First, create a `peru.yaml` file like this:

```yaml
imports:
    rack_example: rack/  # This is where we want peru to put the module.

git module rack_example:
    url: git://github.com/chneukirchen/rack.git
```

Now run `peru sync`.

#### What the hell just happened?

Peru cloned Rack for you, and imported a copy of it under the `rack` directory.
It also created a magical directory called `.peru` to hold that clone and some
other business. If you're using source control, now would be a good time to put
these directories in your ignore list (like `.gitignore`). You usually don't
want to check them in.

Running `peru clean` will make the imported directory disappear.  Running `peru
sync` again will make it come back, and it'll be a lot faster this time,
because peru caches everything.

## Getting Fancy

For a more involved example, let's use peru to manage some dotfiles. We're big
fans of the [Solarized colorscheme](http://ethanschoonover.com/solarized), and
we want to get it working in both `ls` and `vim`. For `ls` all we need peru to
do is fetch a Solarized dircolors file. (That'll get loaded somewhere like
`.bashrc`, not included in this example.) For `vim` we're going to need the
[Solarized vim plugin](https://github.com/altercation/vim-colors-solarized),
and we also want [Pathogen](https://github.com/tpope/vim-pathogen), which makes
plugin installation much cleaner. Here's the `peru.yaml`:

```yaml
imports:
    # The dircolors file just goes at the root of our project.
    dircolors: ./
    # We're going to merge Pathogen's autoload directory into our own.
    pathogen: .vim/autoload/
    # The Solarized plugin gets its own directory, where Pathogen expects it.
    vim-solarized: .vim/bundle/solarized/

git module dircolors:
    url: https://github.com/seebi/dircolors-solarized
    # Only copy this file. Can be a list of files. Accepts * and ** globs.
    files: dircolors.ansi-dark

curl module pathogen:
    url: https://codeload.github.com/tpope/vim-pathogen/tar.gz/v2.3
    # Run this command after fetching. In this case, it unpacks the archive.
    build: tar xfz vim-pathogen-2.3.tar.gz
    # After the build command, use this subdirectory as the root of the module.
    export: vim-pathogen-2.3/autoload/

git module vim-solarized:
    url: https://github.com/altercation/vim-colors-solarized
    # Always fetch this exact commit, instead of master.
    rev: 7a7e5c8818d717084730133ed6b84a3ffc9d0447
```

The contents of the `dircolors` module are copied to the root of our repo. The
`files` field restricts this to just one file, `dircolors.ansi-dark`.

The `pathogen` module uses the `curl` type instead of `git`. (This is just for
the sake of an example. In real life you'd probably want to use `git` here
too.) Since this `url` is a tarball, we use a `build` command to unpack it
after it's fetched.  The contents of the `pathogen` module are copied into
`.vim/autoload`, and because that module specifies an `export` directory, it's
that directory rather than the whole module that gets copied. The result is
that Pathogen's `autoload` directory gets merged with our own, which is the
standard way to install Pathogen.

The `vim-solarized` module gets copied into its own directory under `bundle`,
which is where Pathogen will look for it. Note that it has an explicit `rev`
field, which tells peru to fetch that exact revision, rather than the the
default branch (`master` in git). That's a **Super Serious Best Practice™**,
because it means your dependencies will always be consistent, even when you
look at commits from a long time ago.

You really want all of your dependencies to have explicit hashes, but editing
those by hand is painful, especially if you have a lot of dependencies.  The
next section is about making that easier.

## Magical Updates

If you run `peru reup`, peru will talk to each of your upstream repos, get
their latest versions, and then edit your `peru.yaml` file with any updates. If
you don't have `peru.yaml` checked into some kind of source control, you should
probably do that first, because the reup will modify it in place. When we reup
the example above, the changes look something like this:

```diff
diff --git a/peru.yaml b/peru.yaml
index 15c758d..7f0e26b 100644
--- a/peru.yaml
+++ b/peru.yaml
@@ -6,12 +6,14 @@ imports:
 git module dircolors:
     url: https://github.com/seebi/dircolors-solarized
     files: dircolors.ansi-dark
+    rev: a5e130c642e45323a22226f331cb60fd37ce564f

 curl module pathogen:
     url: https://codeload.github.com/tpope/vim-pathogen/tar.gz/v2.3
     build: tar xfz v2.3
     export: vim-pathogen-2.3/autoload/
+    sha1: 9c3fd6d9891bfe2cd3ed3ddc9ffe5f3fccb72b6a

 git module vim-solarized:
     url: https://github.com/altercation/vim-colors-solarized
-    rev: 7a7e5c8818d717084730133ed6b84a3ffc9d0447
+    rev: 528a59f26d12278698bb946f8fb82a63711eec21
```

Peru made three changes:
- The `dircolors` module, which didn't have a `rev` before, just got one. By
  default for `git`, this is the current `master`. To change that, you can set
  the `reup` field to the name of a different branch.
- The `pathogen` module got a `sha1` field. Unlike `git`, a `curl` module is
  plain old HTTP, so it's stuck downloading whatever file is at the `url`. But
  it will check this hash after the download is finished, and it will raise an
  error if there's a mismatch.
- The `vim-solarized` module had a hash before, but it's been updated. Again,
  the new value came from `master` by default.

At this point, you'll probably want to make a new commit of `peru.yaml` to
record the version bumps. You can do this every so often to keep your plugins
up to date, and you'll still be able to reach old versions in your history.

## Commands
- `sync`
  - Pull in your imports. `sync` yells at you instead of overwriting existing
    or modified files. Use `--force`/`-f` to tell it you're serious.
- `clean`
  - Remove imported files. Same `--force`/`-f` flag as `sync`.
- `reup`
  - Update plugin fields with new revision information. For `git`, `hg`, and
    `svn`, this updates the `rev` field. For the `curl` plugin, this sets the
    `sha1` field. You can optionally give specific module names as arguments.
- `copy`
  - Make a copy of all the files in a module. Either specify a directory to put
    them in, or peru will create a temp dir for you. This lets you take a look
    at modules you don't import yourself, like nested dependencies.
- `override`
  - Replace the contents of a module with a local directory path, usually a
    clone you've made of the same repo. This lets you test changes to imported
    modules without needing to push your changes upstream or edit `peru.yaml`.
- `build`
  - We're not sure what this does yet.

## Module Types
- `git` `hg` `svn`
  - fields: `url` `[rev]` `[reup]`
- `curl` - actually powered by Python's `urllib`
  - fields: `url` `[filename]` `[sha1]`
- `empty` - when you want a module that just `imports` other modules
- A few others mostly for testing purposes. See `rsync` for an example
  implemented in Bash.

## Creating New Module Types
- Module type plugins are as-dumb-as-possible scripts that only know how to
  fetch, and optionally reup. Peru shells out to them and then handles most of
  the caching magic itself, though plugins can also do their own caching as
  appropriate.  For example, the git and hg plugins keep track of repos they
  clone. Peru itself doesn't need to know how to do that.
- You can supply a path or list of paths to the `plugins:` field to load your
  own plugins.
- Plugins are defined with a complicated, undocumented directory layout that
  changes all the time for no reason.

## Build Commands
- Modules can take a `build` field, which is an arbitrary shell command that
  gets run after they're fetched. This is done "in outer space" and cached, so
  that only the final result makes it into your project.
- Modules can have `imports` of their own, to fetch dependencies for building.
- You can define named rules that take the same general fields as modules, so
  that you can build one module in multiple ways. These use an awkward,
  undocumented syntax.

## Configuration
- Set `PERU_CACHE` to move peru's cache somewhere outside the `.peru`
  directory. In particular, you can put it somewhere central, like
  `~/.peru-cache`. This lets you run commands like `git clean -dfx` without
  losing all your cloned repos, and it also lets you share clones between
  projects. Be careful, though: if you have nondeterministic modules (like
  `git` modules without an explicit `rev`), sharing the cache means that
  commands run in one project can affect others. Consider using the `--exclude`
  argument to `git clean` instead.
- Set `PERU_DIR` to have peru store its state somewhere besides `.peru`. You
  should not share this between projects, or peru will get very confused.
- Set `PERU_FILE_NAME` if you absolutely must call your file something weird
  like `peru.yml`.
