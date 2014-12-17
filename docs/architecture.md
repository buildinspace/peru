# Architecture

When you run `peru sync`, here's what happens:

1. Peru checks the main cache to see whether any modules need to be
   fetched.
2. For modules that aren't already cached, peru executes the plugin
   corresponding to the module's type (git, hg, etc.).
3. These plugin scripts do all the actual work to download files. Each
   job gets a temporary directory where it puts the files it fetches. It
   also gets a persistent, plugin-specific caching directory where it
   can keep clones or whatever else to speed up future fetches.
4. When a plugin job is done, the files that it fetched are read into
   the main cache.
5. When everything is in cache, your `imports` tree is merged together
   and checked out to your project.

And when you run `peru reup`, here's what happens:

1. For each module, peru executes the corresponding plugin script. This
   is a lot like `peru sync` above, but instead of telling the plugins
   to fetch, peru tells them to reup. (Not all plugins support this, but
   the important ones do.)
2. Each job finds the most up-to-date information for its module. The
   git plugin, for example, runs `git fetch` and reads the latest rev of
   the appropriate branch.
3. Each job then writes updated module fields formatted as YAML to a
   temporary file. The git plugin would write something like

   ```yaml
   rev: 381f7c737f5d53cf7915163b583b537f2fd5fc0d
   ```

   to reflect the new value of the `rev` field.
4. Peru reads these new fields when each job finishes and writes them to
   the `peru.yaml` file in your project.

## Plugins

The goal of the plugin interface is that plugins should do as little as
possible. They only download files and new fields, and they don't know
anything about what happens to things after they're fetched.

Most of the builtin plugins are written in Python for portability, but
they don't actually run in the peru process; instead, we run them as
subprocesses. That's partly to enforce a clean separation, and partly to
allow you to write plugins in whatever language you want.

A plugin definition is a directory that contains a `plugin.yaml` file
and at least one executable. The `plugin.yaml` file defines the module
type's fields, and how the executable(s) should be invoked. Here's the
`plugin.yaml` from `peru/resources/plugins/git`:

```yaml
fetch exe: git_plugin.py
reup exe: git_plugin.py
required fields:
    - url
optional fields:
    - rev
    - reup
cache fields:
    - url
```

- The name of the plugin directory determines the name of the module
  type.
- `fetch exe` is required, and it tells peru what to execute when it
  wants the plugin to fetch.
- `reup exe` is optional; it declares that the plugin supports reup and
  how to execute it. This can be the same script as `fetch exe`, as it
  is here, in which case the script should decide what to do based on
  the `PERU_PLUGIN_COMMAND` environment variable described below.
- `required fields` is required, and it tells peru which fields are
  mandatory for a module of this type.
- `optional fields` is optional, and it lists any fields that are
  allowed but not required for a module of this type.
- `cache fields` specifies that the plugin would like a cache directory,
  in addition to its output directory, where it can keep long-lived
  clones and things like that. The list that follows is the set of
  fields that this cache dir should be keyed off of. In this case, if
  two git modules share the same url, they will share the same cache
  dir. (Because there's no reason to clone a repo twice just to get two
  different revs.) Peru guarantees that no two jobs that share the same
  cache dir will ever run at the same time, so plugins don't need to
  worry about locking.

The other part of a plugin definition is the executable script(s). These
are invoked with no arguments, and several environment variables are
defined to tell the plugin what to do:

- `PERU_PLUGIN_COMMAND` is either `fetch` or `reup`, depending on what
  peru needs the plugin to do.
- `PERU_PLUGIN_CACHE` points to the plugin's cache directory. If
  `plugin.yaml` doesn't include `cache fields`, this path will be
  `/dev/null` (or `nul` on Windows).
- `PERU_MODULE_*`: Each module field is provided as a variable of this
  form. For example, the git plugin gets its `url` field as
  `PERU_MODULE_URL`. The variables for optional fields that aren't
  present in the module are defined but empty.
- `PERU_FETCH_DEST` points to the temporary directory where the plugin
  should put the files it downloads. This is only defined for fetch
  jobs.
- `PERU_REUP_OUTPUT` points to the temporary file where the plugin
  should write updated field values, formatted as YAML. This is only
  defined for reup jobs.

Plugins are always invoked with your project root (where your
`peru.yaml` file lives) as the working directory. That means that you
can use relative paths like `url: ../foo` in your `peru.yaml`. But
plugin scripts that want to refer to other files in the plugin folder
need to use paths based on `argv[0]`; simple relative paths won't work
for that.

You can install your own plugins by putting them in one of the directories that
peru searches. On Posix systems, those are:

1. `$XDG_CONFIG_HOME/peru/plugins/` (default `~/.config/peru/plugins/`)
2. `/usr/local/lib/peru/plugins/`
3. `/usr/lib/peru/plugins/`

On Windows, the plugin paths are:

1. `%LOCALAPPDATA%\peru\plugins\`
2. `%PROGRAMFILES%\peru\plugins\`

## Caching

There are two types of caching in peru: plugin caching and the main tree
cache. Both of these live inside the `.peru` directory that peru creates
at the root of your project. We described plugin caching in the section
above; it's the directories that hold plugin-specific things like cloned
repos. Peru itself is totally agnostic about what goes in those
directories.

The tree cache (see `peru/cache.py`) is what peru itself really cares
about. When a plugin is finished fetching files for a module, all those
files are read into the tree cache. And when peru is ready to write out
all your imports, it's the tree cache that's responsible for merging all
those file trees and checking them out to disk.

Under the covers, the tree cache is actually another git repo, which
lives at `.peru/cache/trees`. (Note: This is *totally separate* from the
git *plugin*, which fetches code from other people's repos just like the
rest of the plugins.) If you're familiar with how git does things, it's
a bare repo with only blob and tree objects, no commit objects. Using
git to power our cache helps us get a lot of speed without actually
doing any hard work! When you run `peru sync`, what happens first is
basically a `git status` comparing the last tree peru checked out to
what you have on disk. That's pretty fast even for large trees, and if
the status is clean, peru doesn't have to do anything. Likewise, writing
your imports to disk is basically a `git checkout`.

The cache's export method is where we enforce most of peru's on-disk
behavior. Like git, peru will refuse to overwrite pre-existing or
modified files. Unlike git, peru will restore deleted files without
complaining. Peru keeps track of the last tree it checked out
(`.peru/lastimports`), so it can clean up old files when your imports
change, though it will notice modified files and throw an error.

Modules in the tree cache are keyed off of a hash of all their fields.
So if you happen to have two identical modules that just have different
names, you'll notice that only one of them appears to get fetched; the
second will always be a cache hit. This also helps to understand the
behavior of modules that fetch from `master` or similar, rather than a
fixed rev: Once the module is in cache, it won't be fetched again unless
you either change one of its fields or blow away the whole cache. In the
future we could provide a mechanism to selectively clear the cache for
one module, but for now you can just delete `.peru/cache`. The
association between cache keys and git trees is maintained with a simple
directory of key-value pairs (`.peru/cache/keyval`).

Currently we just call regular command line git to accomplish all of
this. In the future we could switch to libgit2, which might be
substantially faster and cleaner.
