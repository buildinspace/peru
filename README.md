# peru [![Build Status](https://travis-ci.org/buildinspace/peru.svg?branch=master)](https://travis-ci.org/buildinspace/peru) [![Coverage Status](https://img.shields.io/coveralls/buildinspace/peru.svg)](https://coveralls.io/r/buildinspace/peru)

##### Maybe sometimes better than copy-paste.

Peru is a tool for including other people's code in your projects. It's a lot
like [git submodules](http://git-scm.com/book/en/Git-Tools-Submodules), except
that peru stays out of the way of your other tools. You write a `peru.yaml`
file and then call `peru sync` when you need code, either by hand or in your
build scripts. Your projects can live in git, hg, svn, tarballs, whatever. And
your dependencies can too.

![snazzy gif](docs/peru.gif)

## Why?

There are so many tools for grabbing code. [Maven](http://maven.apache.org/)
downloads JARs. The [Go tool](http://golang.org/cmd/go/) clones libraries from
GitHub. [Vundle](https://github.com/gmarik/Vundle.vim) installs your vim
plugins. They each solve the same problem for different languages and tools.
But peru is all about fetching, and that lets us get a few things right:

- **Reproducibility.** When you check out an old version of your code, you can
  get exactly the same dependencies as when you wrote that code.
- **Speed.** Fetches run in parallel, everything is cached, and we use git
  internally for heavy lifting. (See
  [Architecture: Caching](docs/architecture.md#caching).)
- **Dubious features.** Peru can automatically update your `peru.yaml` file
  with the latest versions of your dependencies. Peru can pick specific files
  out of a tree, or mix multiple trees into a single directory.

There's another class of tools, like Google's
[gclient](http://dev.chromium.org/developers/how-tos/depottools) and
[repo](http://source.android.com/source/developing.html), that do fetching as
part of your source control. Those tend to break sweet features like `git
bisect`. Peru leaves your source control the heck alone.

## Installation

Peru supports Linux, Mac, and Windows. It requires **python** (3.3 or later)
and **git**, and optionally **hg** and **svn** if you want fetch from those
types of repos. Use [pip](https://pip.pypa.io/en/latest/) to install it:

```python
pip install peru
```

On Ubuntu, you can install `peru` from [our
PPA](https://launchpad.net/~buildinspace/+archive/ubuntu/peru). On Arch, you
can install `peru-git` [from the
AUR](https://aur.archlinux.org/packages/peru-git/).

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

#### What the heck just happened?

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
    pick: dircolors.ansi-dark

curl module pathogen:
    url: https://codeload.github.com/tpope/vim-pathogen/tar.gz/v2.3
    # Untar the archive after fetching.
    unpack: tar
    # After the unpack, use this subdirectory as the root of the module.
    export: vim-pathogen-2.3/autoload/

git module vim-solarized:
    url: https://github.com/altercation/vim-colors-solarized
    # Always fetch this exact commit, instead of master.
    rev: 7a7e5c8818d717084730133ed6b84a3ffc9d0447
```

The contents of the `dircolors` module are copied to the root of our repo. The
`files` field restricts this to just one file, `dircolors.ansi-dark`.

The `pathogen` module uses the `curl` type instead of `git`, and its URL points
to a tarball. (This is for the sake of an example. In real life you'd probably
use `git` here too.) The `unpack` field means that we get the contents of the
tarball rather than the tarball file itself. Because the module specifies an
`export` directory, it's that directory rather than the whole module that gets
copied to the import path, `.vim/autoload`. The result is that Pathogen's
`autoload` directory gets merged with our own, which is the standard way to
install Pathogen.

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
     pick: dircolors.ansi-dark
+    rev: a5e130c642e45323a22226f331cb60fd37ce564f

 curl module pathogen:
     url: https://codeload.github.com/tpope/vim-pathogen/tar.gz/v2.3
     unpack: tar
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
  - Update module fields with new revision information. For `git`, `hg`, and
    `svn`, this updates the `rev` field. For `curl`, this sets the `sha1`
    field. You can optionally give specific module names as arguments.
- `copy`
  - Make a copy of all the files in a module. Either specify a directory to put
    them in, or peru will create a temp dir for you. You can use this to see
    modules you don't normally import, or to play with different module/rule
    combinations (see "Rules" below).
- `override`
  - Replace the contents of a module with a local directory path, usually a
    clone you've made of the same repo. This lets you test changes to imported
    modules without needing to push your changes upstream or edit `peru.yaml`.

## Module Types

##### git, hg, svn
For cloning repos. These types all provide the same fields:
- `url`: required, any protocol supported by the underlying VCS
- `rev`: optional, the specific revision/branch/tag to fetch
- `reup`: optional, the branch/tag to get the latest rev from when running
  `peru reup`

##### curl
For downloading a file from a URL. This type is powered by Pythons's standard
library, rather than an external program.
- `url`: required, any kind supported by `urllib` (HTTP, FTP, `file://`)
- `filename`: optional, overrides the default filename
- `sha1`: optional, checks that the downloaded file matches the checksum
- `unpack`: optional, `tar` or `zip`

Peru includes a few other types mostly for testing purposes. See `rsync` for an
example implemented in Bash.

## Creating New Module Types
Module type plugins are as-dumb-as-possible scripts that only know how to
sync, and optionally reup. Peru shells out to them and then handles most of
the caching magic itself, though plugins can also do their own caching as
appropriate.  For example, the git and hg plugins keep track of repos they
clone. Peru itself doesn't need to know how to do that. For all the details,
see [Architecture: Plugins](docs/architecture.md#plugins).

## Rules
Some fields (like `url` and `rev`) are specific to certain module types. There
are also fields you can use in any module, which modify the the tree of files
after it's fetched. These made an appearance in the fancy example above:

- <s>`build`: A shell command to run on the fetched files. Fetching happens
  somewhere in outer space (a temporary directory), and this command will be
  run there.</s> [Deprecated for security and portability reasons. This will go
  away soon. The untarring/unzipping use case will be handled with the new
  `unpack` field in the curl type.]
- `copy`: A multimap of source and destination paths to copy. Follows the
  semantics of Python's `shutil.copy2` when the source is a file and
  `shutil.copytree` when the source is a directory.
- `move`: A map of source and destination paths to move. Follows the semantics
  of Python's `shutil.move()`, so for example moving a file into a directory
  will work.
- `executable`: A file or list of files to make executable, as if
  calling `chmod +x`. Also accepts globs.
- `pick`: A file or directory, or a list of files and directories, to include
  in the module. Everything else is dropped, though the root of the module tree
  is not changed. Paths can contain `*` or `**` globs, powered by Python's
  pathlib. Applies before `export`, so paths are always relative to the root of
  the module.
- `export`: A subdirectory that peru should treat as the root of the module
  tree. Everything else is dropped, including parent directories.
- <s>`files`: A file or directory, or a list of files and directories, to
  include in the module. Everything else is dropped, though the root of the
  module tree is not changed. These can have `*` or `**` globs, powered by
  Python's pathlib. Applies after `export`.</s> [Deprecated in favor of a
  consistent set of fields for file manipulation. Use `pick` instead.]

Besides using those fields in your modules, you can also use them in "named
rules", which let you transform one module in multiple ways. For example, say
you want the `asyncio` subdir from the Tulip project, but you also want the
license file somewhere else. Rather than defining the same module twice, you
can use one module and two named rules, like this:

```yaml
imports:
    tulip|asyncio: python/asyncio/
    tulip|license: licenses/

hg module tulip:
    url: https://code.google.com/p/tulip/

rule asyncio:
    export: asyncio/

rule license:
    pick: COPYING
```

As in the example above, named rules are declared a lot like modules and then
used in the `imports` list, with the syntax `module|rule`.  The `|` operator
there works kind of like a shell pipeline, so you can even do twisted things
like `module|rule1|rule2`, with each rule applying to the output tree of the
previous.

## Configuration
- Set `PERU_CACHE` to move peru's cache somewhere besides `.peru/cache`. In
  particular, you can put it somewhere central, like `~/.peru-cache`. This lets
  you run commands like `git clean -dfx` without losing all your cloned repos,
  and it also lets you share clones between projects.
- Set `PERU_DIR` to have peru store all of its state (including the cache, if
  `PERU_CACHE` is not set) somewhere besides `.peru`. You should not share this
  between projects, or peru will get very confused.
- Set `PERU_FILE_NAME` if you absolutely must call your file something weird
  like `peru.yml`.

## Links
- [Discussion and announcements (Google
  Group)](https://groups.google.com/forum/#!forum/peru-tool)
- [Code review (Phabricator)](https://phabricator.buildinspace.com)
- [Architecture doc](docs/architecture.md)
